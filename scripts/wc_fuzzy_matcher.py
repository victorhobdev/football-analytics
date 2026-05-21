from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.src.db.client import db_client

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
TARGET_SQL = """
    select wc_player_id
    from raw.wc_player_identity_map
    where match_confidence = 'none'
      and blocked_reason = 'no_candidate_found'
"""


def _to_optional_int(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    normalized = str(value).strip()
    if normalized == "":
        return None

    return int(normalized)


def _normalize_name(value: str) -> str:
    text = value.translate(SPECIAL_TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("-", " ").replace("'", " ").replace("’", " ").replace(".", " ")
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_name(value: str) -> list[str]:
    return [token for token in _normalize_name(value).split(" ") if token]


def _is_abbreviated(tokens: list[str]) -> bool:
    return any(len(token) == 1 for token in tokens)


def _load_target_ids() -> set[int]:
    rows = db_client.fetch_all(TARGET_SQL)
    return {int(row["wc_player_id"]) for row in rows}


def _load_wc_players(json_path: Path, target_ids: set[int]) -> list[dict[str, object]]:
    with json_path.open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    targets: list[dict[str, object]] = []
    seen_ids: set[int] = set()
    for player in payload.get("players", []):
        wc_player_id = _to_optional_int(player.get("wc_player_id"))
        if wc_player_id is None or wc_player_id not in target_ids:
            continue

        seen_ids.add(wc_player_id)
        targets.append(player)

    if seen_ids != target_ids:
        missing_ids = sorted(target_ids - seen_ids)
        raise RuntimeError(
            "Reconciliation map is missing sanitized DB targets. "
            f"missing_wc_player_ids={missing_ids[:5]}"
        )

    return targets


def _load_manifest_candidates(manifest_path: Path) -> tuple[list[dict[str, object]], dict[str, set[int]]]:
    with manifest_path.open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    entries = payload.get("entries", [])
    candidates: list[dict[str, object]] = []
    by_last_token: dict[str, set[int]] = defaultdict(set)
    for entry in entries:
        entity_name = str(entry.get("entity_name") or "").strip()
        local_path = str(entry.get("local_path") or "").strip()
        entity_id = _to_optional_int(entry.get("entity_id"))
        if entity_id is None or entity_name == "" or local_path == "":
            continue

        tokens = _tokenize_name(entity_name)
        candidate = {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "tokens": tokens,
            "normalized_name": " ".join(tokens),
            "compact_name": "".join(tokens),
            "local_path": local_path,
        }
        candidate_index = len(candidates)
        candidates.append(candidate)
        if tokens:
            by_last_token[tokens[-1]].add(candidate_index)

    return candidates, by_last_token


def _score_candidate(target: dict[str, object], candidate: dict[str, object]) -> dict[str, object] | None:
    target_tokens = target["tokens"]
    candidate_tokens = candidate["tokens"]
    if not target_tokens or not candidate_tokens:
        return None

    target_last = target_tokens[-1]
    exact_norm = target["normalized_name"] == candidate["normalized_name"]
    same_last = target_last == candidate_tokens[-1]
    first_compatible = target_tokens[0] == candidate_tokens[0] or (
        len(candidate_tokens[0]) == 1 and candidate_tokens[0] == target_tokens[0][0]
    )

    if not exact_norm and not (same_last and first_compatible):
        return None

    ratio = _sequence_ratio(target["normalized_name"], candidate["normalized_name"])
    compact_ratio = _sequence_ratio(target["compact_name"], candidate["compact_name"])
    best_ratio = max(ratio, compact_ratio)
    score = round(best_ratio * 80)
    signals: list[str] = []

    if exact_norm:
        score += 30
        signals.append("normalized_name_match")
    if same_last:
        score += 12
        signals.append("same_last_token")
    if target_tokens[0] == candidate_tokens[0]:
        score += 8
        signals.append("same_first_token")
    elif first_compatible:
        score += 8
        signals.append("initial_compatible")
    if _is_abbreviated(target_tokens) or _is_abbreviated(candidate_tokens):
        score -= 10
        signals.append("name_abbreviated")

    score = max(0, min(84, score))
    if score < 60:
        return None

    return {
        "entity_id": candidate["entity_id"],
        "entity_name": candidate["entity_name"],
        "local_path": candidate["local_path"],
        "score": score,
        "best_ratio": round(best_ratio, 4),
        "signals": signals,
    }


def _sequence_ratio(left: str, right: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, left, right).ratio()


def _build_candidates_for_target(
    target: dict[str, object],
    candidates: list[dict[str, object]],
    by_last_token: dict[str, set[int]],
) -> list[dict[str, object]]:
    candidate_indices = set(by_last_token.get(target["tokens"][-1], set()))
    for index, candidate in enumerate(candidates):
        if candidate["normalized_name"] == target["normalized_name"]:
            candidate_indices.add(index)

    scored_candidates = [
        _score_candidate(target, candidates[index])
        for index in candidate_indices
    ]
    scored_candidates = [candidate for candidate in scored_candidates if candidate is not None]
    scored_candidates.sort(
        key=lambda candidate: (candidate["score"], candidate["best_ratio"]),
        reverse=True,
    )

    if len(scored_candidates) > 1:
        top_score = int(scored_candidates[0]["score"])
        second_score = int(scored_candidates[1]["score"])
        if top_score - second_score <= 3:
            rescored: list[dict[str, object]] = []
            for candidate in scored_candidates:
                adjusted_score = max(0, int(candidate["score"]) - 20)
                if adjusted_score < 60:
                    continue
                rescored.append(
                    {
                        **candidate,
                        "score": adjusted_score,
                        "signals": [*candidate["signals"], "multiple_candidates"],
                    }
                )
            scored_candidates = sorted(
                rescored,
                key=lambda candidate: (candidate["score"], candidate["best_ratio"]),
                reverse=True,
            )

    return scored_candidates[:3]


def _build_report_rows(
    wc_players: list[dict[str, object]],
    candidates: list[dict[str, object]],
    by_last_token: dict[str, set[int]],
) -> tuple[list[dict[str, object]], Counter]:
    summary: Counter = Counter()
    report_rows: list[dict[str, object]] = []

    for player in wc_players:
        era_category = str(player.get("era_category") or "").strip()
        if era_category not in {"modern", "transition"}:
            continue

        target = {
            "wc_player_id": _to_optional_int(player.get("wc_player_id")),
            "player_name": str(player.get("player_name") or "").strip(),
            "team_display_name": str(player.get("team_display_name") or "").strip(),
            "editions": player.get("editions") or [],
            "era_category": era_category,
        }
        target["tokens"] = _tokenize_name(target["player_name"])
        target["normalized_name"] = " ".join(target["tokens"])
        target["compact_name"] = "".join(target["tokens"])

        ranked_candidates = _build_candidates_for_target(target, candidates, by_last_token)
        if ranked_candidates:
            top_candidate = ranked_candidates[0]
            signals = set(top_candidate["signals"])
            if "multiple_candidates" in signals:
                status = "ambiguous"
            elif int(top_candidate["score"]) >= 75:
                status = "strong"
            else:
                status = "review"

            report_rows.append(
                {
                    **target,
                    "status": status,
                    "top_score": top_candidate["score"],
                    "candidates": ranked_candidates,
                }
            )
            summary["with_candidate"] += 1
            summary[f"status_{status}"] += 1
        else:
            summary["without_candidate"] += 1

        summary[f"era_{era_category}"] += 1

    report_rows.sort(
        key=lambda row: (_status_order(row["status"]), int(row["top_score"]), row["player_name"]),
        reverse=True,
    )
    return report_rows, summary


def _status_order(status: str) -> int:
    order = {"strong": 3, "review": 2, "ambiguous": 1}
    return order.get(status, 0)


def _render_report(
    report_rows: list[dict[str, object]],
    summary: Counter,
    manifest_candidates_total: int,
    generated_at: str,
) -> str:
    strong_rows = [row for row in report_rows if row["status"] == "strong"]
    review_rows = [row for row in report_rows if row["status"] == "review"]
    ambiguous_rows = [row for row in report_rows if row["status"] == "ambiguous"]

    lines = [
        "# Fuzzy Match Report",
        "",
        f"- Gerado em: `{generated_at}`",
        "- Escopo do banco: `raw.wc_player_identity_map` com `match_confidence='none'` e `blocked_reason='no_candidate_found'`",
        "- Fonte de candidatos: `data/visual_assets/manifests/players.json` (`entries` com `local_path` presente)",
        "- Escrita em banco: nenhuma. Este relatório é somente leitura.",
        "",
        "## Resumo",
        f"- Alvos auditados no banco: `{summary['era_modern'] + summary['era_transition']}`",
        f"- Era `modern`: `{summary['era_modern']}`",
        f"- Era `transition`: `{summary['era_transition']}`",
        f"- Candidatos utilizáveis no manifest: `{manifest_candidates_total}`",
        f"- Alvos com pelo menos 1 candidato conservador: `{summary['with_candidate']}`",
        f"- Alvos sem candidato seguro: `{summary['without_candidate']}`",
        f"- Casos `strong` (`score >= 75`, sem ambiguidade): `{summary['status_strong']}`",
        f"- Casos `review` (`60-74`, sem ambiguidade): `{summary['status_review']}`",
        f"- Casos `ambiguous` (empate após penalidade): `{summary['status_ambiguous']}`",
        "",
        "## Heurística usada",
        "- Normalização forte de nome: acentos, hífens, apóstrofos, pontos e transliterações (`ð -> d`, `ø -> o`, etc.).",
        "- Um candidato só entra se houver `normalized_name_match` ou coincidência de sobrenome com primeiro nome ou inicial compatível.",
        "- Quando mais de um candidato fica a até 3 pontos do topo, aplica-se penalidade de ambiguidade (`multiple_candidates = -20`).",
        "- Sem fonte real de nacionalidade/data de nascimento/era no manifest, o score desta fase é deliberadamente conservador e não promove nada automaticamente.",
        "",
        "## Limitações",
        "- O manifest não contém nacionalidade nem janela temporal; esta fase não consegue validar `nationality_match` ou `era_overlap`.",
        "- O recorte `transition` tende a ser mais ruidoso; os casos dessa era seguem úteis para triagem, não para promoção automática.",
        "- Casos sem candidato no relatório permanecem em `none + no_candidate_found` até nova fonte de identidade.",
        "",
        "## Casos Strong",
        "",
    ]
    lines.extend(_render_case_blocks(strong_rows))
    lines.extend(
        [
            "",
            "## Casos Review",
            "",
        ]
    )
    lines.extend(_render_case_blocks(review_rows))
    lines.extend(
        [
            "",
            "## Casos Ambiguous",
            "",
        ]
    )
    lines.extend(_render_case_blocks(ambiguous_rows))
    lines.extend(
        [
            "",
            "## Sem candidato seguro",
            "",
            f"- Total: `{summary['without_candidate']}`",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_case_blocks(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- Nenhum caso nesta faixa."]

    blocks: list[str] = []
    for row in rows:
        editions = ", ".join(str(edition) for edition in row["editions"])
        blocks.extend(
            [
                f"### {row['player_name']}",
                f"- `wc_player_id`: `{row['wc_player_id']}`",
                f"- Seleção: `{row['team_display_name']}`",
                f"- Edições: `{editions}`",
                f"- Era: `{row['era_category']}`",
                f"- Status do relatório: `{row['status']}`",
                "",
                "| score | entity_id | entity_name | signals | asset |",
                "|---|---:|---|---|---|",
            ]
        )
        for candidate in row["candidates"]:
            signals = ", ".join(candidate["signals"])
            blocks.append(
                f"| `{candidate['score']}` | `{candidate['entity_id']}` | `{candidate['entity_name']}` | `{signals}` | `{candidate['local_path']}` |"
            )
        blocks.append("")

    return blocks


def run(json_path: Path, manifest_path: Path, output_path: Path) -> Path:
    target_ids = _load_target_ids()
    wc_players = _load_wc_players(json_path, target_ids)
    manifest_candidates, by_token = _load_manifest_candidates(manifest_path)
    report_rows, summary = _build_report_rows(wc_players, manifest_candidates, by_token)

    report = _render_report(
        report_rows=report_rows,
        summary=summary,
        manifest_candidates_total=len(manifest_candidates),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "targets": summary["era_modern"] + summary["era_transition"],
                "with_candidate": summary["with_candidate"],
                "without_candidate": summary["without_candidate"],
                "status_strong": summary["status_strong"],
                "status_review": summary["status_review"],
                "status_ambiguous": summary["status_ambiguous"],
                "output_path": str(output_path),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a conservative fuzzy report for unresolved World Cup player identities.",
    )
    parser.add_argument(
        "--json-path",
        default="data/visual_assets/wc_pipeline/wc_reconciliation_map.json",
        help="Path to wc_reconciliation_map.json",
    )
    parser.add_argument(
        "--manifest-path",
        default="data/visual_assets/manifests/players.json",
        help="Path to players manifest",
    )
    parser.add_argument(
        "--output-path",
        default="docs/fuzzy_match_report.md",
        help="Where to write the markdown report",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path).resolve()
    manifest_path = Path(args.manifest_path).resolve()
    output_path = Path(args.output_path).resolve()

    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    run(json_path=json_path, manifest_path=manifest_path, output_path=output_path)


if __name__ == "__main__":
    main()
