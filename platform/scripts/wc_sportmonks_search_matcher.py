from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from _repo_root import resolve_repo_root
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT_DIR = resolve_repo_root()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.src.db.client import db_client


DEFAULT_JSON_PATH = ROOT_DIR / "data" / "visual_assets" / "wc_pipeline" / "wc_reconciliation_map.json"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
DEFAULT_MANIFEST_PATH = ROOT_DIR / "data" / "visual_assets" / "manifests" / "players.json"
DEFAULT_WC_PLAYERS_CSV_PATH = (
    ROOT_DIR
    / "data"
    / "snapshots"
    / "world-cup"
    / "fjelstul-worldcup"
    / "f41e9437a007498bdbf3751305818101f96cb6fb"
    / "data-csv"
    / "players.csv"
)
DEFAULT_REPORT_PATH = ROOT_DIR / "docs" / "sportmonks_birthdate_player_match_report.md"

SPECIAL_TRANSLITERATION = str.maketrans(
    {
        "ð": "d",
        "Ð": "d",
        "þ": "th",
        "Þ": "th",
        "ø": "o",
        "Ø": "o",
        "ł": "l",
        "Ł": "l",
        "ß": "ss",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
    }
)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Busca candidatos de identidade na API SportMonks usando nome + birth_date "
            "da fonte Copa Fjelstul. Nao escreve no banco."
        )
    )
    parser.add_argument("--json-path", default=str(DEFAULT_JSON_PATH), help="Artefato de reconciliacao da Copa.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Arquivo .env com API_KEY_SPORTMONKS.")
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Manifest base de players para marcar se o candidato ja tem asset local.",
    )
    parser.add_argument(
        "--wc-players-csv-path",
        default=str(DEFAULT_WC_PLAYERS_CSV_PATH),
        help="CSV Fjelstul players.csv com birth_date da Copa.",
    )
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Arquivo markdown de saida.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="Timeout HTTP por request.")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries para requests HTTP.")
    parser.add_argument(
        "--scope",
        choices=("no-candidate", "unconfirmed", "all"),
        default="unconfirmed",
        help=(
            "no-candidate: none + no_candidate_found; "
            "unconfirmed: todos que nao sao confirmed; "
            "all: todos os 498 registros do crosswalk."
        ),
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def resolve_setting(name: str, env_file_values: dict[str, str], default: str | None = None) -> str | None:
    import os

    value = os.getenv(name)
    if value:
        return value
    value = env_file_values.get(name)
    if value:
        return value
    return default


def _normalize_name(value: str | None) -> str:
    text = (value or "").translate(SPECIAL_TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("-", " ").replace("'", " ").replace("’", " ").replace(".", " ")
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_name(value: str | None) -> list[str]:
    return [token for token in _normalize_name(value).split(" ") if token]


def _sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _load_target_rows(scope: str) -> list[dict[str, object]]:
    if scope == "no-candidate":
        where_sql = "match_confidence = 'none' and blocked_reason = 'no_candidate_found'"
    elif scope == "unconfirmed":
        where_sql = "match_confidence <> 'confirmed'"
    else:
        where_sql = "1=1"

    return db_client.fetch_all(
        f"""
        select
            wc_player_id,
            sportmonks_player_id,
            match_confidence,
            blocked_reason,
            match_score,
            match_method,
            audited_by
        from raw.wc_player_identity_map
        where {where_sql}
        order by wc_player_id
        """
    )


def _load_source_player_ids(target_ids: set[int]) -> dict[int, set[str]]:
    if not target_ids:
        return {}

    rows = db_client.fetch_all(
        """
        select player_id as wc_player_id, source_player_id
        from raw.wc_squads
        where player_id = any(%s)
          and source_player_id is not null
        union
        select player_id as wc_player_id, source_player_id
        from raw.wc_goals
        where player_id = any(%s)
          and source_player_id is not null
        """,
        [sorted(target_ids), sorted(target_ids)],
    )

    source_ids_by_wc_id: dict[int, set[str]] = {}
    for row in rows:
        wc_player_id = int(row["wc_player_id"])
        source_player_id = str(row["source_player_id"]).strip()
        if not source_player_id:
            continue
        source_ids_by_wc_id.setdefault(wc_player_id, set()).add(source_player_id)
    return source_ids_by_wc_id


def _load_fjelstul_players(path: Path) -> dict[str, dict[str, str]]:
    players: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as file_obj:
        for row in csv.DictReader(file_obj):
            player_id = str(row.get("player_id") or "").strip()
            if player_id:
                players[player_id] = row
    return players


def _source_full_name(row: dict[str, str] | None) -> str | None:
    if not row:
        return None
    given_name = str(row.get("given_name") or "").strip()
    family_name = str(row.get("family_name") or "").strip()
    parts = [
        part
        for part in (given_name, family_name)
        if part and part.casefold() != "not applicable"
    ]
    return " ".join(parts) or family_name or None


def _load_wc_players(
    *,
    json_path: Path,
    target_rows: list[dict[str, object]],
    source_ids_by_wc_id: dict[int, set[str]],
    source_players: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    target_by_id = {int(row["wc_player_id"]): row for row in target_rows}
    target_ids = set(target_by_id)
    wc_players = []
    seen_ids: set[int] = set()

    for player in payload.get("players", []):
        wc_player_id = int(player["wc_player_id"])
        if wc_player_id not in target_ids:
            continue

        source_ids = sorted(source_ids_by_wc_id.get(wc_player_id, set()))
        source_rows = [source_players[source_id] for source_id in source_ids if source_id in source_players]
        birth_dates = sorted({str(row.get("birth_date") or "").strip() for row in source_rows if row.get("birth_date")})
        source_names = sorted(
            {
                name
                for row in source_rows
                if (name := _source_full_name(row))
            }
        )

        enriched = {
            **player,
            "source_player_ids": source_ids,
            "source_birth_dates": birth_dates,
            "source_names": source_names,
            "current_crosswalk": target_by_id[wc_player_id],
        }
        seen_ids.add(wc_player_id)
        wc_players.append(enriched)

    missing_ids = sorted(target_ids - seen_ids)
    if missing_ids:
        raise RuntimeError(f"wc_reconciliation_map.json sem entradas para ids do banco: {missing_ids[:10]}")
    return wc_players


def _load_manifest_entries(manifest_path: Path) -> dict[int, dict[str, object]]:
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries_by_id: dict[int, dict[str, object]] = {}
    for entry in payload.get("entries", []):
        entity_id = entry.get("entity_id")
        if isinstance(entity_id, int):
            entries_by_id[entity_id] = entry
    return entries_by_id


def _load_dim_player_ids() -> set[int]:
    rows = db_client.fetch_all("select player_id from mart.dim_player where player_id is not null")
    return {int(row["player_id"]) for row in rows}


class SportMonksSearchClient:
    def __init__(self, *, base_url: str, api_token: str, timeout_seconds: int, max_retries: int):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.request_count = 0
        self.cache: dict[str, list[dict[str, object]]] = {}

    def search(self, query: str) -> list[dict[str, object]]:
        normalized_query = query.strip()
        if not normalized_query:
            return []
        cache_key = normalized_query.casefold()
        if cache_key in self.cache:
            return self.cache[cache_key]

        endpoint = f"/players/search/{quote(normalized_query)}"
        params = {"api_token": self.api_token, "per_page": 50}
        url = f"{self.base_url}{endpoint}?{urlencode(params)}"
        request_obj = Request(url, headers={"User-Agent": "football-analytics-sportmonks-search/1.0"})
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self.request_count += 1
            try:
                with urlopen(request_obj, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    data = payload.get("data") or []
                    if isinstance(data, dict):
                        data = [data]
                    rows = [row for row in data if isinstance(row, dict)]
                    self.cache[cache_key] = rows
                    return rows
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    last_error = RuntimeError(f"status={exc.code} body={body[:200]}")
                    continue
                raise RuntimeError(f"SportMonks search query={query!r} status={exc.code} body={body[:200]}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"SportMonks search query={query!r} erro_rede={exc}") from exc

        raise RuntimeError(f"SportMonks search query={query!r} retries_excedidos error={last_error}")


def _build_queries(player: dict[str, object]) -> list[str]:
    raw_queries: list[str] = []
    player_name = str(player.get("player_name") or "").strip()
    if player_name:
        raw_queries.append(player_name)

    for source_name in player.get("source_names") or []:
        raw_queries.append(str(source_name))

    for name in [player_name, *(str(item) for item in (player.get("source_names") or []))]:
        tokens = _tokenize_name(name)
        if len(tokens) >= 2:
            raw_queries.append(f"{tokens[0]} {tokens[-1]}")
            raw_queries.append(tokens[-1])
        elif len(tokens) == 1:
            raw_queries.append(tokens[0])

    queries: list[str] = []
    seen: set[str] = set()
    for query in raw_queries:
        normalized_query = query.strip()
        if not normalized_query:
            continue
        key = normalized_query.casefold()
        if key in seen:
            continue
        seen.add(key)
        queries.append(normalized_query)
    return queries


def _candidate_name_variants(candidate: dict[str, object]) -> list[str]:
    variants: list[str] = []
    for key in ("display_name", "name", "common_name"):
        value = str(candidate.get(key) or "").strip()
        if value:
            variants.append(value)
    firstname = str(candidate.get("firstname") or "").strip()
    lastname = str(candidate.get("lastname") or "").strip()
    full_name = " ".join(part for part in (firstname, lastname) if part)
    if full_name:
        variants.append(full_name)

    deduped: list[str] = []
    seen: set[str] = set()
    for value in variants:
        normalized = _normalize_name(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def _name_score(player: dict[str, object], candidate: dict[str, object]) -> tuple[int, list[str], float]:
    target_names = [str(player.get("player_name") or "").strip()]
    target_names.extend(str(item).strip() for item in (player.get("source_names") or []))
    target_names = [name for name in target_names if name]
    target_token_sets = [_tokenize_name(name) for name in target_names if _tokenize_name(name)]
    target_norms = {_normalize_name(name) for name in target_names if _normalize_name(name)}

    candidate_variants = _candidate_name_variants(candidate)
    candidate_token_sets = [_tokenize_name(name) for name in candidate_variants if _tokenize_name(name)]
    candidate_norms = {_normalize_name(name) for name in candidate_variants if _normalize_name(name)}

    score = 0
    signals: list[str] = []
    best_ratio = 0.0

    for target_norm in target_norms:
        for candidate_norm in candidate_norms:
            best_ratio = max(best_ratio, _sequence_ratio(target_norm, candidate_norm))

    if target_norms & candidate_norms:
        score += 45
        signals.append("exact_normalized_name")

    for target_tokens in target_token_sets:
        for candidate_tokens in candidate_token_sets:
            if not target_tokens or not candidate_tokens:
                continue
            if target_tokens[-1] == candidate_tokens[-1]:
                score = max(score, score + 15 if "last_token_match" not in signals else score)
                if "last_token_match" not in signals:
                    signals.append("last_token_match")
            if target_tokens[0] == candidate_tokens[0]:
                if "first_token_match" not in signals:
                    score += 10
                    signals.append("first_token_match")
            elif len(candidate_tokens[0]) == 1 and candidate_tokens[0] == target_tokens[0][0]:
                if "initial_compatible" not in signals:
                    score += 5
                    signals.append("initial_compatible")
            if all(token in candidate_tokens for token in target_tokens):
                if "all_target_tokens_present" not in signals:
                    score += 30
                    signals.append("all_target_tokens_present")
            if all(token in target_tokens for token in candidate_tokens):
                if "candidate_tokens_present_in_target" not in signals:
                    score += 15
                    signals.append("candidate_tokens_present_in_target")

    if best_ratio >= 0.86 and "high_name_similarity" not in signals:
        score += 20
        signals.append("high_name_similarity")
    elif best_ratio >= 0.72 and "moderate_name_similarity" not in signals:
        score += 10
        signals.append("moderate_name_similarity")

    return min(score, 100), signals, round(best_ratio, 4)


def _score_candidate(player: dict[str, object], candidate: dict[str, object]) -> dict[str, object] | None:
    candidate_id = candidate.get("id")
    if candidate_id is None:
        return None

    source_birth_dates = [str(item) for item in (player.get("source_birth_dates") or []) if item]
    candidate_dob = str(candidate.get("date_of_birth") or "").strip()
    name_score, name_signals, best_ratio = _name_score(player, candidate)

    signals: list[str] = []
    score = name_score
    birthdate_status = "missing_source_or_candidate_birthdate"

    if source_birth_dates and candidate_dob:
        if candidate_dob in source_birth_dates:
            score += 80
            signals.append("date_of_birth_exact_match")
            birthdate_status = "exact"
        elif any(candidate_dob[:4] == source_birth_date[:4] for source_birth_date in source_birth_dates):
            score += 20
            signals.append("birth_year_match_only")
            birthdate_status = "year_only"
        else:
            signals.append("date_of_birth_conflict")
            birthdate_status = "conflict"
            if name_score < 95:
                return None
            score -= 40

    signals.extend(name_signals)

    if birthdate_status == "missing_source_or_candidate_birthdate" and name_score < 85:
        return None
    if birthdate_status == "year_only" and name_score < 70:
        return None
    if birthdate_status == "exact" and name_score < 20:
        return None
    if score < 70:
        return None

    return {
        "sportmonks_player_id": int(candidate_id),
        "display_name": candidate.get("display_name"),
        "full_name": candidate.get("name"),
        "common_name": candidate.get("common_name"),
        "date_of_birth": candidate_dob or None,
        "source_birth_dates": source_birth_dates,
        "image_path": candidate.get("image_path"),
        "score": min(score, 140),
        "name_score": name_score,
        "best_name_ratio": best_ratio,
        "birthdate_status": birthdate_status,
        "signals": signals,
    }


def _classify_candidates(candidates: list[dict[str, object]]) -> tuple[str, list[dict[str, object]]]:
    if not candidates:
        return "none", []

    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get("birthdate_status") == "exact",
            int(item["score"]),
            float(item["best_name_ratio"]),
            -int(item["sportmonks_player_id"]),
        ),
        reverse=True,
    )

    if len(ordered) > 1 and int(ordered[0]["score"]) - int(ordered[1]["score"]) <= 5:
        return "ambiguous", ordered[:3]

    top = ordered[0]
    if top.get("birthdate_status") == "exact" and int(top["name_score"]) >= 20:
        return "strong", ordered[:3]
    if top.get("birthdate_status") == "year_only" and int(top["name_score"]) >= 75:
        return "review", ordered[:3]
    if int(top["score"]) >= 110:
        return "review", ordered[:3]
    return "none", []


def _build_report(
    *,
    report_path: Path,
    scope: str,
    player_rows: list[dict[str, object]],
    classification_counts: Counter,
    request_count: int,
    cache_size: int,
    unsupported_birthdate_filter: bool,
) -> None:
    lines: list[str] = [
        "# SportMonks Birthdate Player Match Report",
        "",
        f"- Gerado em: `{utc_now()}`",
        f"- Escopo: `{scope}`",
        "- Fonte Copa: Fjelstul `players.csv.birth_date` via `raw.wc_squads/source_player_id` e `raw.wc_goals/source_player_id`",
        "- Fonte SportMonks: API Pro `GET /players/search/{query}`",
        "- Escrita em banco: nenhuma. Este relatório é somente leitura.",
        f"- Filtro direto por data de nascimento na SportMonks: `{'indisponivel' if unsupported_birthdate_filter else 'nao testado'}`",
        "",
        "## Resumo",
        f"- Alvos processados: `{len(player_rows)}`",
        f"- Casos `strong`: `{classification_counts.get('strong', 0)}`",
        f"- Casos `review`: `{classification_counts.get('review', 0)}`",
        f"- Casos `ambiguous`: `{classification_counts.get('ambiguous', 0)}`",
        f"- Sem candidato útil: `{classification_counts.get('none', 0)}`",
        f"- Sem birth_date Copa: `{classification_counts.get('missing_source_birthdate', 0)}`",
        f"- Queries únicas à API: `{cache_size}`",
        f"- Requests HTTP à API: `{request_count}`",
        "",
        "## Casos Strong",
        "",
    ]

    for status in ("strong", "review", "ambiguous"):
        if status != "strong":
            lines.extend([f"## Casos {status.title()}", ""])
        rows = [row for row in player_rows if row["status"] == status]
        if not rows:
            lines.append("- Nenhum caso nesta faixa.")
            lines.append("")
            continue

        for row in rows:
            lines.extend(
                [
                    f"### {row['player_name']}",
                    f"- `wc_player_id`: `{row['wc_player_id']}`",
                    f"- Estado atual: `{row['current_confidence']}` / `{row.get('current_method') or 'n/d'}`",
                    f"- Seleção: `{row['team_display_name']}`",
                    f"- Edições: `{', '.join(row['editions']) or 'n/d'}`",
                    f"- Era: `{row['era_category']}`",
                    f"- `source_player_ids`: `{', '.join(row['source_player_ids']) or 'n/d'}`",
                    f"- `birth_date` Copa: `{', '.join(row['source_birth_dates']) or 'n/d'}`",
                    f"- Queries: `{', '.join(row['queries'])}`",
                    f"- Status do relatório: `{row['status']}`",
                    "",
                    "| score | name_score | birthdate | sportmonks_player_id | display_name | full_name | SportMonks DOB | sinais | asset_manifest | image_path |",
                    "|---:|---:|---|---:|---|---|---|---|---|---|",
                ]
            )
            for candidate in row["candidates"]:
                lines.append(
                    "| "
                    f"`{candidate['score']}` | "
                    f"`{candidate['name_score']}` | "
                    f"`{candidate['birthdate_status']}` | "
                    f"`{candidate['sportmonks_player_id']}` | "
                    f"{candidate.get('display_name') or 'n/d'} | "
                    f"{candidate.get('full_name') or 'n/d'} | "
                    f"{candidate.get('date_of_birth') or 'n/d'} | "
                    f"`{', '.join(candidate.get('signals') or [])}` | "
                    f"{candidate.get('asset_manifest') or 'n/d'} | "
                    f"{candidate.get('image_path') or 'n/d'} |"
                )
            lines.append("")

    no_candidate_rows = [row for row in player_rows if row["status"] == "none"]
    lines.extend(["## Sem candidato útil", "", f"- Total: `{len(no_candidate_rows)}`"])
    if no_candidate_rows:
        lines.extend(
            [
                "",
                "| jogador Copa | wc_player_id | estado atual | seleção | edições | birth_date Copa | queries |",
                "|---|---:|---|---|---|---|---|",
            ]
        )
        for row in no_candidate_rows:
            lines.append(
                "| "
                f"{row['player_name']} | "
                f"`{row['wc_player_id']}` | "
                f"`{row['current_confidence']}` / `{row.get('current_method') or 'n/d'}` | "
                f"{row['team_display_name']} | "
                f"{', '.join(row['editions']) or 'n/d'} | "
                f"{', '.join(row['source_birth_dates']) or 'n/d'} | "
                f"`{', '.join(row['queries'])}` |"
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    env_file_values = load_env_file(Path(args.env_file).resolve())
    api_token = resolve_setting("API_KEY_SPORTMONKS", env_file_values)
    api_base_url = resolve_setting("SPORTMONKS_BASE_URL", env_file_values, "https://api.sportmonks.com/v3/football")
    if not api_token:
        raise SystemExit("API_KEY_SPORTMONKS nao encontrada no ambiente nem no .env.")

    target_rows = _load_target_rows(scope=args.scope)
    target_ids = {int(row["wc_player_id"]) for row in target_rows}
    source_ids_by_wc_id = _load_source_player_ids(target_ids)
    source_players = _load_fjelstul_players(Path(args.wc_players_csv_path).resolve())
    wc_players = _load_wc_players(
        json_path=Path(args.json_path).resolve(),
        target_rows=target_rows,
        source_ids_by_wc_id=source_ids_by_wc_id,
        source_players=source_players,
    )
    manifest_entries = _load_manifest_entries(Path(args.manifest_path).resolve())
    dim_player_ids = _load_dim_player_ids()
    client = SportMonksSearchClient(
        base_url=api_base_url or "",
        api_token=api_token,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
    )

    report_rows: list[dict[str, object]] = []
    classification_counts: Counter = Counter()

    for player in wc_players:
        wc_player_id = int(player["wc_player_id"])
        queries = _build_queries(player)
        deduped_candidates: dict[int, dict[str, object]] = {}

        if not player.get("source_birth_dates"):
            classification_counts["missing_source_birthdate"] += 1

        for query in queries:
            try:
                api_rows = client.search(query)
            except Exception:
                api_rows = []
            for candidate in api_rows:
                scored = _score_candidate(player, candidate)
                if scored is None:
                    continue
                candidate_id = int(scored["sportmonks_player_id"])
                current = deduped_candidates.get(candidate_id)
                if current is None or int(scored["score"]) > int(current["score"]):
                    manifest_entry = manifest_entries.get(candidate_id)
                    deduped_candidates[candidate_id] = {
                        **scored,
                        "candidate_in_dim_player": candidate_id in dim_player_ids,
                        "asset_manifest": manifest_entry.get("local_path") if manifest_entry else None,
                    }

        status, top_candidates = _classify_candidates(list(deduped_candidates.values()))
        classification_counts[status] += 1
        current_crosswalk = player["current_crosswalk"]
        report_rows.append(
            {
                "wc_player_id": wc_player_id,
                "player_name": str(player.get("player_name") or "").strip(),
                "team_display_name": str(player.get("team_display_name") or "").strip(),
                "editions": [str(item) for item in player.get("editions") or []],
                "era_category": str(player.get("era_category") or "").strip(),
                "source_player_ids": [str(item) for item in player.get("source_player_ids") or []],
                "source_birth_dates": [str(item) for item in player.get("source_birth_dates") or []],
                "status": status,
                "queries": queries,
                "current_confidence": current_crosswalk["match_confidence"],
                "current_method": current_crosswalk.get("match_method"),
                "candidates": top_candidates,
            }
        )

    _build_report(
        report_path=Path(args.report_path).resolve(),
        scope=args.scope,
        player_rows=report_rows,
        classification_counts=classification_counts,
        request_count=client.request_count,
        cache_size=len(client.cache),
        unsupported_birthdate_filter=True,
    )

    summary = {
        "generated_at": utc_now(),
        "scope": args.scope,
        "targets_total": len(report_rows),
        "strong_total": classification_counts.get("strong", 0),
        "review_total": classification_counts.get("review", 0),
        "ambiguous_total": classification_counts.get("ambiguous", 0),
        "none_total": classification_counts.get("none", 0),
        "missing_source_birthdate_total": classification_counts.get("missing_source_birthdate", 0),
        "api_unique_queries_total": len(client.cache),
        "api_requests_total": client.request_count,
        "report_path": str(Path(args.report_path).resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
