from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import sys
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "data" / "visual_assets"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_PAGE_SIZE = 5
DEFAULT_DOWNLOAD_WORKERS = 6
DEFAULT_MIN_CONFIDENCE_SCORE = 60
PROVIDER_REQUEST_MIN_INTERVAL_SECONDS = {
    "wikimedia_commons": 1.2,
    "openverse": 0.25,
}
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
POSITIVE_IMAGE_KEYWORDS = {
    "champion",
    "champions",
    "campeao",
    "campeoes",
    "winner",
    "winners",
    "trophy",
    "cup",
    "taça",
    "taca",
    "celebration",
    "lift",
    "lifting",
    "final",
}
NEGATIVE_IMAGE_KEYWORDS = {
    "logo",
    "badge",
    "crest",
    "kit",
    "jersey",
    "poster",
    "sticker",
    "video game",
    "wallpaper",
    "render",
}
TEAM_TOKEN_STOPWORDS = {
    "club",
    "clube",
    "de",
    "do",
    "da",
    "del",
    "the",
    "and",
    "fc",
    "cf",
    "sc",
    "ac",
    "cd",
    "fk",
    "sv",
    "ssc",
    "afc",
    "football",
    "futebol",
}
HTTP_USER_AGENT = "football-analytics-champion-assets/1.0"
CATEGORY_NAME = "champions"
HONOR_CODE = "champion"
IMAGE_VARIANT = "trophy-lift"
FILENAME_VERSION = "v01"
WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens"

COMPETITION_SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    "brasileirao_a": (
        "Brasileirão",
        "Campeonato Brasileiro",
        "Brazilian Serie A",
    ),
    "brasileirao_b": (
        "Série B",
        "Campeonato Brasileiro Série B",
        "Brazilian Serie B",
    ),
    "bundesliga": (
        "Bundesliga",
        "German Bundesliga",
    ),
    "champions_league": (
        "Champions League",
        "UEFA Champions League",
    ),
    "copa_do_brasil": (
        "Copa do Brasil",
        "Brazilian Cup",
    ),
    "fifa_world_cup_mens": (
        "FIFA World Cup",
        "World Cup",
        "Copa do Mundo",
    ),
    "la_liga": (
        "La Liga",
        "Spanish La Liga",
    ),
    "libertadores": (
        "Libertadores",
        "Copa Libertadores",
    ),
    "ligue_1": (
        "Ligue 1",
        "French Ligue 1",
    ),
    "premier_league": (
        "Premier League",
        "English Premier League",
    ),
    "primeira_liga": (
        "Primeira Liga",
        "Liga Portugal",
    ),
    "serie_a_it": (
        "Serie A",
        "Serie A Italy",
        "Italian Serie A",
    ),
    "supercopa_do_brasil": (
        "Supercopa do Brasil",
        "Brazilian Super Cup",
    ),
}

CHAMPION_TARGETS_SQL = """
with team_dim as (
    select
        team_id,
        max(team_name) as team_name
    from mart.dim_team
    where team_id is not null
    group by team_id
),
competition_catalog as (
    select
        competition_key,
        max(league_id) as provider_league_id,
        max(league_name) as competition_name
    from raw.competition_leagues
    where competition_key is not null
    group by competition_key
),
editions as (
    select distinct
        competition_key,
        season_label
    from raw.competition_seasons
    where competition_key is not null
      and season_label is not null
),
standings_stage_rank as (
    select
        s.competition_key,
        s.season_label,
        s.stage_id,
        max(ds.stage_name) as stage_name,
        count(distinct s.team_id) as team_count,
        count(distinct s.round_id) as round_count,
        max(coalesce(ds.sort_order, 0)) as stage_sort_order,
        row_number() over (
            partition by s.competition_key, s.season_label
            order by
                count(distinct s.team_id) desc,
                count(distinct s.round_id) desc,
                max(coalesce(ds.sort_order, 0)) desc,
                s.stage_id desc
        ) as stage_rank
    from mart.fact_standings_snapshots s
    left join mart.dim_stage ds
      on ds.stage_sk = s.stage_sk
    group by s.competition_key, s.season_label, s.stage_id
),
standings_final_round as (
    select
        competition_key,
        season_label,
        stage_id,
        max(round_id) as final_round_id
    from mart.fact_standings_snapshots
    group by competition_key, season_label, stage_id
),
standings_final_winner as (
    select distinct on (ssr.competition_key, ssr.season_label)
        ssr.competition_key,
        ssr.season_label,
        s.team_id,
        td.team_name,
        ssr.stage_name
    from standings_stage_rank ssr
    join standings_final_round sfr
      on sfr.competition_key = ssr.competition_key
     and sfr.season_label = ssr.season_label
     and sfr.stage_id = ssr.stage_id
    join mart.fact_standings_snapshots s
      on s.competition_key = ssr.competition_key
     and s.season_label = ssr.season_label
     and s.stage_id = ssr.stage_id
     and s.round_id = sfr.final_round_id
     and s.position = 1
    left join team_dim td
      on td.team_id = s.team_id
    where ssr.stage_rank = 1
    order by
        ssr.competition_key,
        ssr.season_label,
        s.updated_at desc nulls last,
        s.standings_snapshot_id desc
),
tie_stage_rank as (
    select
        t.competition_key,
        t.season_label,
        t.stage_id,
        max(t.stage_name) as stage_name,
        max(coalesce(ds.sort_order, 0)) as stage_sort_order,
        max(coalesce(t.tie_order, 0)) as max_tie_order,
        row_number() over (
            partition by t.competition_key, t.season_label
            order by
                max(coalesce(ds.sort_order, 0)) desc,
                max(coalesce(t.tie_order, 0)) desc,
                t.stage_id desc
        ) as stage_rank
    from mart.fact_tie_results t
    left join mart.dim_stage ds
      on ds.competition_key = t.competition_key
     and ds.season_label = t.season_label
     and ds.stage_id = t.stage_id
    where t.winner_team_id is not null
    group by t.competition_key, t.season_label, t.stage_id
),
tie_final_winner as (
    select distinct on (tsr.competition_key, tsr.season_label)
        tsr.competition_key,
        tsr.season_label,
        t.winner_team_id as team_id,
        coalesce(
            td.team_name,
            case
                when t.winner_team_id = t.home_side_team_id then t.home_side_team_name
                else t.away_side_team_name
            end
        ) as team_name,
        tsr.stage_name
    from tie_stage_rank tsr
    join mart.fact_tie_results t
      on t.competition_key = tsr.competition_key
     and t.season_label = tsr.season_label
     and t.stage_id = tsr.stage_id
    left join team_dim td
      on td.team_id = t.winner_team_id
    where tsr.stage_rank = 1
      and t.winner_team_id is not null
      and coalesce(t.tie_order, 0) = tsr.max_tie_order
    order by
        tsr.competition_key,
        tsr.season_label,
        coalesce(t.last_leg_at, t.first_leg_at) desc nulls last,
        t.tie_id desc
)
select
    e.competition_key,
    cc.provider_league_id,
    cc.competition_name,
    e.season_label,
    coalesce(tfw.team_id, sfw.team_id) as team_id,
    coalesce(tfw.team_name, sfw.team_name) as team_name,
    case
        when tfw.team_id is not null then 'tie_result'
        when sfw.team_id is not null then 'standings'
        else 'unresolved'
    end as champion_source,
    coalesce(tfw.stage_name, sfw.stage_name) as champion_stage_name
from editions e
left join competition_catalog cc
  on cc.competition_key = e.competition_key
left join tie_final_winner tfw
  on tfw.competition_key = e.competition_key
 and tfw.season_label = e.season_label
left join standings_final_winner sfw
  on sfw.competition_key = e.competition_key
 and sfw.season_label = e.season_label
order by e.competition_key, e.season_label
"""


@dataclass(frozen=True)
class ChampionTarget:
    competition_key: str
    provider_league_id: int | None
    competition_name: str
    season_label: str
    season_key: str
    season_display: str
    season_terms: tuple[str, ...]
    team_id: int | str | None
    team_name: str | None
    team_slug: str
    champion_source: str
    champion_stage_name: str | None
    honor_code: str
    image_variant: str
    sequence: int
    asset_id: str
    filename_stem: str


@dataclass(frozen=True)
class SearchCandidate:
    provider: str
    provider_id: str
    title: str | None
    creator: str | None
    license: str | None
    license_url: str | None
    source_url: str
    source_page_url: str | None
    content_type: str | None
    width: int | None
    height: int | None
    search_query: str
    searchable_text: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: SearchCandidate
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SearchResult:
    queries: tuple[str, ...]
    selected: ScoredCandidate | None
    top_candidates: tuple[ScoredCandidate, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class DownloadPlan:
    target: ChampionTarget
    selected: ScoredCandidate
    top_candidates: tuple[ScoredCandidate, ...]
    search_queries: tuple[str, ...]
    search_errors: tuple[str, ...]


@dataclass(frozen=True)
class DownloadResult:
    asset_id: str
    ok: bool
    local_path: str | None
    content_type: str | None
    file_size_bytes: int | None
    error: str | None


def build_world_cup_targets(
    existing_targets_by_edition: dict[tuple[str, str], ChampionTarget],
) -> list[ChampionTarget]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from api.src.routers.world_cup import _build_world_cup_hub_payload

    hub_payload, _ = _build_world_cup_hub_payload()
    targets: list[ChampionTarget] = []

    for edition in hub_payload.get("editions", []):
        season_label = str(edition.get("seasonLabel") or "").strip()
        if not season_label:
            continue

        champion = edition.get("champion") if isinstance(edition.get("champion"), dict) else {}
        team_name = str(champion.get("teamName")).strip() if champion.get("teamName") else None
        team_id = str(champion.get("teamId")).strip() if champion.get("teamId") else None
        team_slug = slugify_ascii(team_name) if team_name else "unresolved"
        existing_target = existing_targets_by_edition.get((WORLD_CUP_COMPETITION_KEY, season_label))
        asset_id = build_asset_id(
            competition_key=WORLD_CUP_COMPETITION_KEY,
            season_key=normalize_season_key(season_label),
            team_slug=team_slug,
        )

        targets.append(
            ChampionTarget(
                competition_key=WORLD_CUP_COMPETITION_KEY,
                provider_league_id=existing_target.provider_league_id if existing_target else None,
                competition_name=(existing_target.competition_name if existing_target else "FIFA Men's World Cup"),
                season_label=season_label,
                season_key=normalize_season_key(season_label),
                season_display=format_season_display(season_label),
                season_terms=build_season_terms(season_label),
                team_id=team_id,
                team_name=team_name,
                team_slug=team_slug,
                champion_source="world_cup_hub" if team_name else "unresolved",
                champion_stage_name=str(edition.get("resolutionType") or "") or None,
                honor_code=HONOR_CODE,
                image_variant=IMAGE_VARIANT,
                sequence=1,
                asset_id=asset_id,
                filename_stem=asset_id,
            )
        )

    return targets


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve campeoes por edicao a partir do Postgres local e baixa imagens abertas "
            "de celebracao/trofeu em data/visual_assets/champions."
        )
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Diretorio raiz do cache local de assets.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Arquivo .env usado como fallback para credenciais locais.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao faz buscas HTTP nem downloads. Apenas resolve o escopo de campeoes.",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Busca candidatos e gera manifesto, mas nao baixa arquivos.",
    )
    parser.add_argument(
        "--competition-keys",
        nargs="+",
        help="Filtra a execucao para competition_keys especificas.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limita a quantidade de edicoes processadas apos filtros.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Quantidade de resultados por query em cada provider.",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help="Numero de downloads paralelos.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout das chamadas HTTP.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Numero maximo de retries por request HTTP.",
    )
    parser.add_argument(
        "--min-confidence-score",
        type=int,
        default=DEFAULT_MIN_CONFIDENCE_SCORE,
        help="Score minimo para baixar automaticamente um candidato.",
    )
    return parser.parse_args()


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
    value = os.getenv(name)
    if value is not None and value != "":
        return value
    value = env_file_values.get(name)
    if value is not None and value != "":
        return value
    return default


def build_pg_dsn(env_file_values: dict[str, str]) -> str:
    user = resolve_setting("POSTGRES_USER", env_file_values, "football")
    password = resolve_setting("POSTGRES_PASSWORD", env_file_values, "football")
    database = resolve_setting("POSTGRES_DB", env_file_values, "football_dw")
    host = resolve_setting("POSTGRES_HOST", env_file_values, "localhost")
    port = resolve_setting("POSTGRES_PORT", env_file_values, "5432")
    if user and password and database:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    dsn = resolve_setting("FOOTBALL_PG_DSN", env_file_values) or resolve_setting("DATABASE_URL", env_file_values)
    if not dsn:
        return "postgresql://football:football@localhost:5432/football_dw"

    normalized = dsn.replace("postgresql+psycopg2://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    parsed = urlparse(normalized)
    hostname = parsed.hostname or "localhost"
    if hostname in {"postgres", "football-postgres"}:
        hostname = "localhost"
    netloc = hostname
    if parsed.username:
        credentials = parsed.username
        if parsed.password:
            credentials = f"{credentials}:{parsed.password}"
        netloc = f"{credentials}@{netloc}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse((parsed.scheme or "postgresql", netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def relpath(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(manifest_path: Path) -> dict[str, dict[str, Any]]:
    if not manifest_path.exists():
        return {}
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        asset_id = entry.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            by_id[asset_id] = entry
    return by_id


def build_category_paths(output_root: Path, category_name: str) -> tuple[Path, Path]:
    category_dir = output_root / category_name
    manifest_path = output_root / "manifests" / f"{category_name}.json"
    category_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return category_dir, manifest_path


def find_existing_asset(category_dir: Path, filename_stem: str) -> Path | None:
    matches = sorted(category_dir.glob(f"{filename_stem}.*"))
    for match in matches:
        if match.is_file() and match.stat().st_size > 0:
            return match
    return None


def infer_extension(*, source_url: str, content_type: str | None) -> str:
    if content_type:
        normalized = content_type.split(";", 1)[0].strip().lower()
        extension = CONTENT_TYPE_EXTENSIONS.get(normalized)
        if extension:
            return extension
    suffix = Path(urlparse(source_url).path).suffix.lower()
    return suffix or ".bin"


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    ascii_text = unicodedata.normalize("NFKD", value)
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def slugify_ascii(value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return "unknown"
    return normalized.replace(" ", "-")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def humanize_competition_key(competition_key: str) -> str:
    return " ".join(part.capitalize() for part in competition_key.split("_"))


def format_season_display(season_label: str) -> str:
    match = re.fullmatch(r"(\d{4})[_/-](\d{2,4})", season_label)
    if not match:
        return season_label.replace("_", "/")
    start_year = match.group(1)
    end_year = match.group(2)
    return f"{start_year}/{end_year}"


def normalize_season_key(season_label: str) -> str:
    match = re.fullmatch(r"(\d{4})[_/-](\d{2,4})", season_label)
    if not match:
        return season_label.replace("/", "-").replace("_", "-")
    start_year = match.group(1)
    end_year = match.group(2)
    if len(end_year) == 2:
        end_year = f"{start_year[:2]}{end_year}"
    return f"{start_year}-{end_year}"


def build_season_terms(season_label: str) -> tuple[str, ...]:
    display = format_season_display(season_label)
    match = re.fullmatch(r"(\d{4})[_/-](\d{2,4})", season_label)
    if not match:
        return (display,)
    start_year = match.group(1)
    end_year = match.group(2)
    if len(end_year) == 2:
        full_end_year = f"{start_year[:2]}{end_year}"
    else:
        full_end_year = end_year
    terms: list[str] = [display, full_end_year, start_year]
    full_display = f"{start_year}/{full_end_year}"
    if full_display not in terms:
        terms.append(full_display)
    ordered: list[str] = []
    for term in terms:
        if term and term not in ordered:
            ordered.append(term)
    return tuple(ordered)


def competition_search_aliases(competition_key: str, competition_name: str) -> tuple[str, ...]:
    aliases = list(COMPETITION_SEARCH_ALIASES.get(competition_key, ()))
    if competition_name and competition_name not in aliases:
        aliases.append(competition_name)
    humanized = humanize_competition_key(competition_key)
    if humanized not in aliases:
        aliases.append(humanized)
    return tuple(aliases)


def team_search_aliases(target: ChampionTarget) -> tuple[str, ...]:
    aliases: list[str] = []

    if target.competition_key == WORLD_CUP_COMPETITION_KEY and isinstance(target.team_id, str):
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))

        from api.src.routers.world_cup_labels import WORLD_CUP_CANONICAL_TEAM_VARIANTS

        for display_team_id, _, team_aliases in WORLD_CUP_CANONICAL_TEAM_VARIANTS:
            if display_team_id != target.team_id:
                continue
            aliases.extend(team_aliases)
            break

    if target.team_name:
        aliases.append(target.team_name)

    ordered: list[str] = []
    for alias in aliases:
        compact = re.sub(r"\s+", " ", alias).strip()
        if compact and compact not in ordered:
            ordered.append(compact)
    return tuple(ordered)


def build_asset_id(competition_key: str, season_key: str, team_slug: str) -> str:
    return "__".join(
        [
            competition_key,
            season_key,
            HONOR_CODE,
            team_slug,
            IMAGE_VARIANT,
            FILENAME_VERSION,
        ]
    )


def build_search_queries(target: ChampionTarget) -> tuple[str, ...]:
    team_aliases = team_search_aliases(target)
    aliases = competition_search_aliases(target.competition_key, target.competition_name)
    focus_term = target.season_terms[1] if len(target.season_terms) > 1 else target.season_terms[0]
    primary_team_alias = team_aliases[0] if team_aliases else target.team_name
    queries = [
        f"{primary_team_alias} {aliases[0]} {focus_term} champion trophy",
        f"{primary_team_alias} {aliases[0]} {focus_term} winner trophy",
        f"{primary_team_alias} {aliases[0]} {focus_term} campeao taca",
    ]
    if target.season_display != focus_term:
        queries.append(f"{primary_team_alias} {aliases[0]} {target.season_display} champion trophy")
    if len(team_aliases) > 1:
        queries.append(f"{team_aliases[1]} {aliases[0]} {focus_term} champion trophy")
    if len(aliases) > 1:
        queries.append(f"{primary_team_alias} {aliases[1]} {focus_term} champion trophy")
    ordered: list[str] = []
    for query in queries:
        compact = re.sub(r"\s+", " ", query).strip()
        if compact and compact not in ordered:
            ordered.append(compact)
    return tuple(ordered)


def tokenize_significant(text: str) -> set[str]:
    return {
        token
        for token in normalize_text(text).split()
        if len(token) >= 3 and token not in TEAM_TOKEN_STOPWORDS
    }


def score_candidate(target: ChampionTarget, candidate: SearchCandidate) -> ScoredCandidate:
    searchable = normalize_text(candidate.searchable_text)
    score = 0
    reasons: list[str] = []

    normalized_content_type = (candidate.content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type and not normalized_content_type.startswith("image/"):
        return ScoredCandidate(candidate=candidate, score=0, reasons=("non_image_content",))

    team_aliases = team_search_aliases(target)
    candidate_tokens = tokenize_significant(candidate.searchable_text)
    team_phrase = next(
        (
            normalized_alias
            for normalized_alias in (normalize_text(alias) for alias in team_aliases)
            if normalized_alias and normalized_alias in searchable
        ),
        None,
    )

    if team_phrase:
        score += 40
        reasons.append("team_exact")
    else:
        best_overlap_ratio = 0.0
        best_overlap_count = 0
        for alias in team_aliases:
            team_tokens = tokenize_significant(alias)
            if not team_tokens:
                continue
            team_overlap = len(team_tokens & candidate_tokens)
            overlap_ratio = team_overlap / len(team_tokens)
            if overlap_ratio > best_overlap_ratio or (
                overlap_ratio == best_overlap_ratio and team_overlap > best_overlap_count
            ):
                best_overlap_ratio = overlap_ratio
                best_overlap_count = team_overlap

        if best_overlap_ratio >= 0.6:
            score += 28
            reasons.append("team_partial_strong")
        elif best_overlap_count > 0:
            score += 16
            reasons.append("team_partial_weak")

    aliases = competition_search_aliases(target.competition_key, target.competition_name)
    alias_hit = False
    for alias in aliases:
        normalized_alias = normalize_text(alias)
        if normalized_alias and normalized_alias in searchable:
            score += 25
            reasons.append("competition_exact")
            alias_hit = True
            break
    if not alias_hit:
        for alias in aliases:
            alias_tokens = tokenize_significant(alias)
            if alias_tokens and len(alias_tokens & candidate_tokens) / len(alias_tokens) >= 0.5:
                score += 16
                reasons.append("competition_partial")
                alias_hit = True
                break

    if any(normalize_text(term) in searchable for term in target.season_terms):
        score += 15
        reasons.append("season_match")

    positive_tokens = {normalize_text(value) for value in POSITIVE_IMAGE_KEYWORDS}
    if any(keyword in searchable for keyword in positive_tokens):
        score += 15
        reasons.append("celebration_keyword")

    negative_tokens = {normalize_text(value) for value in NEGATIVE_IMAGE_KEYWORDS}
    if any(keyword in searchable for keyword in negative_tokens):
        score -= 20
        reasons.append("negative_keyword")

    if candidate.provider == "wikimedia_commons":
        score += 5
        reasons.append("provider_bonus")

    if (candidate.width or 0) * (candidate.height or 0) >= 250_000:
        score += 5
        reasons.append("size_bonus")

    final_score = max(score, 0)
    return ScoredCandidate(candidate=candidate, score=final_score, reasons=tuple(reasons))


def qualifies_for_auto_download(scored: ScoredCandidate, *, min_confidence_score: int) -> bool:
    reasons = set(scored.reasons)
    if scored.score < min_confidence_score:
        return False
    if "negative_keyword" in reasons:
        return False
    if not {"team_exact", "team_partial_strong", "team_partial_weak"} & reasons:
        return False
    if not {"competition_exact", "competition_partial"} & reasons:
        return False
    if "celebration_keyword" not in reasons:
        return False
    return True


class HttpJsonClient:
    def __init__(self, *, timeout_seconds: int, max_retries: int):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.request_counts = Counter()
        self._last_request_started_at: dict[str, float] = {}

    def request_json(self, *, name: str, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request_headers = {"User-Agent": HTTP_USER_AGENT}
        if headers:
            request_headers.update(headers)
        request_obj = Request(url, headers=request_headers)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            min_interval = PROVIDER_REQUEST_MIN_INTERVAL_SECONDS.get(name, 0.0)
            last_started_at = self._last_request_started_at.get(name)
            if min_interval > 0 and last_started_at is not None:
                elapsed = time.perf_counter() - last_started_at
                remaining = min_interval - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            self._last_request_started_at[name] = time.perf_counter()
            self.request_counts["total"] += 1
            self.request_counts[f"provider:{name}"] += 1
            try:
                with urlopen(request_obj, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    last_error = RuntimeError(f"status={exc.code} body={body[:300]}")
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"{name} status={exc.code} body={body[:300]}") from exc
            except URLError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"{name} erro_rede={exc}") from exc
        raise RuntimeError(f"{name} retries_excedidos error={last_error}")


class WikimediaCommonsClient:
    def __init__(self, *, http_client: HttpJsonClient):
        self.http_client = http_client

    def search(self, *, query: str, page_size: int) -> list[SearchCandidate]:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(page_size),
            "prop": "imageinfo|info",
            "iiprop": "url|mime|size|extmetadata",
            "inprop": "url",
            "format": "json",
        }
        url = f"https://commons.wikimedia.org/w/api.php?{urlencode(params)}"
        payload = self.http_client.request_json(name="wikimedia_commons", url=url)
        pages = (payload.get("query") or {}).get("pages") or {}
        candidates: list[SearchCandidate] = []
        for page in pages.values():
            imageinfo = (page.get("imageinfo") or [{}])[0]
            source_url = imageinfo.get("url")
            if not source_url:
                continue
            extmetadata = imageinfo.get("extmetadata") or {}
            searchable_parts = [
                strip_html(page.get("title")),
                strip_html(extmetadata.get("ObjectName", {}).get("value")),
                strip_html(extmetadata.get("ImageDescription", {}).get("value")),
                strip_html(extmetadata.get("Categories", {}).get("value")),
            ]
            candidates.append(
                SearchCandidate(
                    provider="wikimedia_commons",
                    provider_id=str(page.get("pageid") or page.get("title") or source_url),
                    title=strip_html(page.get("title")).removeprefix("File:"),
                    creator=strip_html(extmetadata.get("Artist", {}).get("value")),
                    license=strip_html(extmetadata.get("LicenseShortName", {}).get("value"))
                    or strip_html(extmetadata.get("License", {}).get("value")),
                    license_url=strip_html(extmetadata.get("LicenseUrl", {}).get("value")) or None,
                    source_url=source_url,
                    source_page_url=imageinfo.get("descriptionurl") or page.get("fullurl"),
                    content_type=imageinfo.get("mime"),
                    width=imageinfo.get("width"),
                    height=imageinfo.get("height"),
                    search_query=query,
                    searchable_text=" ".join(part for part in searchable_parts if part),
                )
            )
        return candidates


class OpenverseClient:
    def __init__(self, *, http_client: HttpJsonClient):
        self.http_client = http_client

    def search(self, *, query: str, page_size: int) -> list[SearchCandidate]:
        params = {
            "q": query,
            "page_size": str(page_size),
        }
        url = f"https://api.openverse.org/v1/images/?{urlencode(params)}"
        payload = self.http_client.request_json(name="openverse", url=url)
        rows = payload.get("results") or []
        candidates: list[SearchCandidate] = []
        for row in rows:
            source_url = row.get("url")
            if not source_url:
                continue
            tag_names = " ".join(tag.get("name") for tag in (row.get("tags") or []) if tag.get("name"))
            searchable_parts = [
                row.get("title") or "",
                row.get("creator") or "",
                row.get("attribution") or "",
                tag_names,
            ]
            candidates.append(
                SearchCandidate(
                    provider="openverse",
                    provider_id=str(row.get("id") or source_url),
                    title=row.get("title"),
                    creator=row.get("creator"),
                    license=row.get("license"),
                    license_url=row.get("license_url"),
                    source_url=source_url,
                    source_page_url=row.get("foreign_landing_url") or row.get("detail_url"),
                    content_type=f"image/{row.get('filetype')}" if row.get("filetype") else None,
                    width=row.get("width"),
                    height=row.get("height"),
                    search_query=query,
                    searchable_text=" ".join(part for part in searchable_parts if part),
                )
            )
        return candidates


class AssetDownloader:
    def __init__(self, *, timeout_seconds: int, max_retries: int):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.request_counts = Counter()

    def download(self, *, category_dir: Path, plan: DownloadPlan) -> DownloadResult:
        candidate = plan.selected.candidate
        request_obj = Request(candidate.source_url, headers={"User-Agent": HTTP_USER_AGENT})
        temp_path: Path | None = None
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self.request_counts["total"] += 1
            self.request_counts[f"provider:{candidate.provider}"] += 1
            try:
                with urlopen(request_obj, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                    content_type = response.headers.get_content_type()
                    extension = infer_extension(source_url=candidate.source_url, content_type=content_type)
                    final_path = category_dir / f"{plan.target.filename_stem}{extension}"
                    temp_path = final_path.with_suffix(final_path.suffix + ".tmp")
                    with temp_path.open("wb") as handle:
                        shutil.copyfileobj(response, handle)
                    temp_path.replace(final_path)
                    temp_path = None
                    return DownloadResult(
                        asset_id=plan.target.asset_id,
                        ok=True,
                        local_path=relpath(final_path),
                        content_type=content_type,
                        file_size_bytes=final_path.stat().st_size,
                        error=None,
                    )
            except HTTPError as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    last_error = RuntimeError(f"status={exc.code} body={body[:200]}")
                    time.sleep(2**attempt)
                    continue
                return DownloadResult(
                    asset_id=plan.target.asset_id,
                    ok=False,
                    local_path=None,
                    content_type=None,
                    file_size_bytes=None,
                    error=f"download status={exc.code} body={body[:200]}",
                )
            except URLError as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                return DownloadResult(
                    asset_id=plan.target.asset_id,
                    ok=False,
                    local_path=None,
                    content_type=None,
                    file_size_bytes=None,
                    error=f"download erro_rede={exc}",
                )
            except Exception as exc:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                last_error = exc
                break
        return DownloadResult(
            asset_id=plan.target.asset_id,
            ok=False,
            local_path=None,
            content_type=None,
            file_size_bytes=None,
            error=str(last_error) if last_error else "erro_desconhecido",
        )


def fetch_champion_targets(conn: psycopg.Connection[Any]) -> list[ChampionTarget]:
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(CHAMPION_TARGETS_SQL)
        rows = cursor.fetchall()

    targets: list[ChampionTarget] = []
    seen_editions: set[tuple[str, str]] = set()
    duplicate_editions: set[tuple[str, str]] = set()

    for row in rows:
        competition_key = str(row["competition_key"])
        season_label = str(row["season_label"])
        edition_key = (competition_key, season_label)
        if edition_key in seen_editions:
            duplicate_editions.add(edition_key)
            continue
        seen_editions.add(edition_key)

        team_id = row.get("team_id")
        team_name = row.get("team_name")
        champion_source = str(row.get("champion_source") or "unresolved")

        competition_name = row.get("competition_name") or humanize_competition_key(competition_key)
        season_key = normalize_season_key(season_label)
        team_slug = slugify_ascii(team_name) if team_name else "unresolved"
        asset_id = build_asset_id(competition_key=competition_key, season_key=season_key, team_slug=team_slug)

        targets.append(
            ChampionTarget(
                competition_key=competition_key,
                provider_league_id=int(row["provider_league_id"]) if row.get("provider_league_id") is not None else None,
                competition_name=str(competition_name),
                season_label=season_label,
                season_key=season_key,
                season_display=format_season_display(season_label),
                season_terms=build_season_terms(season_label),
                team_id=int(team_id) if team_id is not None else None,
                team_name=str(team_name) if team_name else None,
                team_slug=team_slug,
                champion_source=champion_source,
                champion_stage_name=row.get("champion_stage_name"),
                honor_code=HONOR_CODE,
                image_variant=IMAGE_VARIANT,
                sequence=1,
                asset_id=asset_id,
                filename_stem=asset_id,
            )
        )

    if duplicate_editions:
        raise RuntimeError(f"Edicoes duplicadas na resolucao de campeoes: {sorted(duplicate_editions)[:10]}")

    targets_by_edition = {
        (target.competition_key, target.season_label): target
        for target in targets
    }

    for target in build_world_cup_targets(targets_by_edition):
        targets_by_edition[(target.competition_key, target.season_label)] = target

    return [
        targets_by_edition[key]
        for key in sorted(targets_by_edition.keys(), key=lambda item: (item[0], item[1]))
    ]


def filter_targets(
    targets: list[ChampionTarget],
    *,
    competition_keys: list[str] | None,
    limit: int | None,
) -> list[ChampionTarget]:
    filtered = targets
    if competition_keys:
        allowed = {value.strip() for value in competition_keys if value.strip()}
        filtered = [target for target in filtered if target.competition_key in allowed]
    if limit is not None and limit > 0:
        filtered = filtered[:limit]
    return filtered


def candidate_to_manifest_payload(scored: ScoredCandidate) -> dict[str, Any]:
    candidate = scored.candidate
    return {
        "provider": candidate.provider,
        "provider_id": candidate.provider_id,
        "score": scored.score,
        "score_reasons": list(scored.reasons),
        "title": candidate.title,
        "creator": candidate.creator,
        "license": candidate.license,
        "license_url": candidate.license_url,
        "source_url": candidate.source_url,
        "source_page_url": candidate.source_page_url,
        "content_type": candidate.content_type,
        "width": candidate.width,
        "height": candidate.height,
        "search_query": candidate.search_query,
    }


def build_cached_entry(
    *,
    target: ChampionTarget,
    existing_file: Path,
    existing_manifest_entry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "asset_id": target.asset_id,
        "competition_key": target.competition_key,
        "provider_league_id": target.provider_league_id,
        "competition_name": target.competition_name,
        "season_label": target.season_label,
        "season_key": target.season_key,
        "team_id": target.team_id,
        "team_name": target.team_name,
        "team_slug": target.team_slug,
        "honor_code": target.honor_code,
        "image_variant": target.image_variant,
        "sequence": target.sequence,
        "champion_source": target.champion_source,
        "champion_stage_name": target.champion_stage_name,
        "status": "cached_local",
        "confidence_score": existing_manifest_entry.get("confidence_score"),
        "search_queries": existing_manifest_entry.get("search_queries") or [],
        "selected_candidate": existing_manifest_entry.get("selected_candidate"),
        "candidates": existing_manifest_entry.get("candidates") or [],
        "local_path": relpath(existing_file),
        "content_type": existing_manifest_entry.get("content_type"),
        "file_size_bytes": existing_file.stat().st_size,
        "last_synced_at": utc_now(),
        "error": None,
        "search_errors": existing_manifest_entry.get("search_errors") or [],
    }


def build_unresolved_entry(target: ChampionTarget) -> dict[str, Any]:
    return {
        "asset_id": target.asset_id,
        "competition_key": target.competition_key,
        "provider_league_id": target.provider_league_id,
        "competition_name": target.competition_name,
        "season_label": target.season_label,
        "season_key": target.season_key,
        "team_id": target.team_id,
        "team_name": target.team_name,
        "team_slug": target.team_slug,
        "honor_code": target.honor_code,
        "image_variant": target.image_variant,
        "sequence": target.sequence,
        "champion_source": target.champion_source,
        "champion_stage_name": target.champion_stage_name,
        "status": "unresolved_target",
        "confidence_score": None,
        "search_queries": [],
        "selected_candidate": None,
        "candidates": [],
        "local_path": None,
        "content_type": None,
        "file_size_bytes": None,
        "last_synced_at": utc_now(),
        "error": "Campeao da edicao ainda nao resolvido no mart local.",
        "search_errors": [],
    }


def search_candidates_for_target(
    *,
    target: ChampionTarget,
    providers: list[Any],
    page_size: int,
    min_confidence_score: int,
) -> SearchResult:
    queries = build_search_queries(target)
    deduped: dict[tuple[str, str], SearchCandidate] = {}
    errors: list[str] = []

    for query in queries:
        for provider in providers:
            try:
                results = provider.search(query=query, page_size=page_size)
            except Exception as exc:
                errors.append(f"{provider.__class__.__name__} query={query!r} error={exc}")
                continue
            for candidate in results:
                dedupe_key = (candidate.provider, candidate.source_url)
                deduped.setdefault(dedupe_key, candidate)

    scored = sorted(
        (score_candidate(target, candidate) for candidate in deduped.values()),
        key=lambda item: (
            item.score,
            1 if item.candidate.provider == "wikimedia_commons" else 0,
            item.candidate.width or 0,
            item.candidate.height or 0,
        ),
        reverse=True,
    )
    selected = scored[0] if scored and qualifies_for_auto_download(scored[0], min_confidence_score=min_confidence_score) else None
    return SearchResult(
        queries=queries,
        selected=selected,
        top_candidates=tuple(scored[:5]),
        errors=tuple(errors),
    )


def build_search_entry(
    *,
    target: ChampionTarget,
    search_result: SearchResult,
    status: str,
    local_path: str | None = None,
    content_type: str | None = None,
    file_size_bytes: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    selected_candidate = (
        candidate_to_manifest_payload(search_result.selected) if search_result.selected is not None else None
    )
    return {
        "asset_id": target.asset_id,
        "competition_key": target.competition_key,
        "provider_league_id": target.provider_league_id,
        "competition_name": target.competition_name,
        "season_label": target.season_label,
        "season_key": target.season_key,
        "team_id": target.team_id,
        "team_name": target.team_name,
        "team_slug": target.team_slug,
        "honor_code": target.honor_code,
        "image_variant": target.image_variant,
        "sequence": target.sequence,
        "champion_source": target.champion_source,
        "champion_stage_name": target.champion_stage_name,
        "status": status,
        "confidence_score": search_result.selected.score if search_result.selected else None,
        "search_queries": list(search_result.queries),
        "selected_candidate": selected_candidate,
        "candidates": [candidate_to_manifest_payload(candidate) for candidate in search_result.top_candidates],
        "local_path": local_path,
        "content_type": content_type,
        "file_size_bytes": file_size_bytes,
        "last_synced_at": utc_now(),
        "error": error,
        "search_errors": list(search_result.errors),
    }


def sync_champion_assets(
    *,
    conn: psycopg.Connection[Any],
    output_root: Path,
    dry_run: bool,
    search_only: bool,
    competition_keys: list[str] | None,
    limit: int | None,
    page_size: int,
    download_workers: int,
    timeout_seconds: int,
    max_retries: int,
    min_confidence_score: int,
) -> dict[str, Any]:
    category_dir, manifest_path = build_category_paths(output_root, CATEGORY_NAME)
    existing_manifest = load_manifest(manifest_path)
    targets = filter_targets(
        fetch_champion_targets(conn),
        competition_keys=competition_keys,
        limit=limit,
    )

    if page_size <= 0:
        raise RuntimeError("--page-size deve ser maior que zero.")

    entries: list[dict[str, Any]] = []
    download_plans: list[DownloadPlan] = []

    if dry_run:
        for target in targets:
            if target.team_name is None or target.champion_source == "unresolved":
                entries.append(build_unresolved_entry(target))
                continue
            entries.append(
                {
                    "asset_id": target.asset_id,
                    "competition_key": target.competition_key,
                    "provider_league_id": target.provider_league_id,
                    "competition_name": target.competition_name,
                    "season_label": target.season_label,
                    "season_key": target.season_key,
                    "team_id": target.team_id,
                    "team_name": target.team_name,
                    "team_slug": target.team_slug,
                    "honor_code": target.honor_code,
                    "image_variant": target.image_variant,
                    "sequence": target.sequence,
                    "champion_source": target.champion_source,
                    "champion_stage_name": target.champion_stage_name,
                    "status": "dry_run_pending",
                    "confidence_score": None,
                    "search_queries": list(build_search_queries(target)),
                    "selected_candidate": None,
                    "candidates": [],
                    "local_path": None,
                    "content_type": None,
                    "file_size_bytes": None,
                    "last_synced_at": utc_now(),
                    "error": None,
                    "search_errors": [],
                }
            )
    else:
        http_client = HttpJsonClient(timeout_seconds=timeout_seconds, max_retries=max_retries)
        providers = [
            WikimediaCommonsClient(http_client=http_client),
            OpenverseClient(http_client=http_client),
        ]

        for target in targets:
            if target.team_name is None or target.champion_source == "unresolved":
                entries.append(build_unresolved_entry(target))
                continue
            existing_file = find_existing_asset(category_dir, target.filename_stem)
            existing_manifest_entry = existing_manifest.get(target.asset_id, {})
            if existing_file is not None:
                entries.append(
                    build_cached_entry(
                        target=target,
                        existing_file=existing_file,
                        existing_manifest_entry=existing_manifest_entry,
                    )
                )
                continue

            search_result = search_candidates_for_target(
                target=target,
                providers=providers,
                page_size=page_size,
                min_confidence_score=min_confidence_score,
            )
            if search_only:
                status = "candidate_only" if search_result.selected else ("search_failed" if search_result.errors else "no_candidate")
                entries.append(build_search_entry(target=target, search_result=search_result, status=status))
                continue

            if search_result.selected is None:
                status = "search_failed" if search_result.errors else "no_candidate"
                entries.append(build_search_entry(target=target, search_result=search_result, status=status))
                continue

            download_plans.append(
                DownloadPlan(
                    target=target,
                    selected=search_result.selected,
                    top_candidates=search_result.top_candidates,
                    search_queries=search_result.queries,
                    search_errors=search_result.errors,
                )
            )

        downloader = AssetDownloader(timeout_seconds=timeout_seconds, max_retries=max_retries)
        if download_plans:
            download_results: dict[str, DownloadResult] = {}
            with ThreadPoolExecutor(max_workers=max(1, download_workers)) as executor:
                future_map = {
                    executor.submit(downloader.download, category_dir=category_dir, plan=plan): plan
                    for plan in download_plans
                }
                for future in as_completed(future_map):
                    plan = future_map[future]
                    download_results[plan.target.asset_id] = future.result()

            for plan in download_plans:
                result = download_results.get(plan.target.asset_id)
                if result is None:
                    entries.append(
                        build_search_entry(
                            target=plan.target,
                            search_result=SearchResult(
                                queries=plan.search_queries,
                                selected=plan.selected,
                                top_candidates=plan.top_candidates,
                                errors=plan.search_errors,
                            ),
                            status="download_failed",
                            error="resultado de download ausente",
                        )
                    )
                    continue

                entries.append(
                    build_search_entry(
                        target=plan.target,
                        search_result=SearchResult(
                            queries=plan.search_queries,
                            selected=plan.selected,
                            top_candidates=plan.top_candidates,
                            errors=plan.search_errors,
                        ),
                        status="downloaded" if result.ok else "download_failed",
                        local_path=result.local_path,
                        content_type=result.content_type,
                        file_size_bytes=result.file_size_bytes,
                        error=result.error,
                    )
                )

    status_counts = Counter(entry["status"] for entry in entries)
    summary = {
        "category": CATEGORY_NAME,
        "targets_total": len(targets),
        "dry_run_total": status_counts.get("dry_run_pending", 0),
        "cached_local_total": status_counts.get("cached_local", 0),
        "downloaded_total": status_counts.get("downloaded", 0),
        "candidate_only_total": status_counts.get("candidate_only", 0),
        "no_candidate_total": status_counts.get("no_candidate", 0),
        "unresolved_target_total": status_counts.get("unresolved_target", 0),
        "search_failed_total": status_counts.get("search_failed", 0),
        "download_failed_total": status_counts.get("download_failed", 0),
        "assets_present_total": status_counts.get("cached_local", 0) + status_counts.get("downloaded", 0),
        "manifest_path": relpath(manifest_path),
        "category_dir": relpath(category_dir),
        "min_confidence_score": min_confidence_score,
    }

    manifest_payload = {
        "category": CATEGORY_NAME,
        "generated_at": utc_now(),
        "summary": summary,
        "entries": sorted(
            entries,
            key=lambda entry: (
                entry["competition_key"],
                entry["season_label"],
                entry["team_name"] or "",
            ),
        ),
    }
    write_json(manifest_path, manifest_payload)
    return {
        "summary": summary,
        "entries": manifest_payload["entries"],
    }


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root).resolve()
    env_file_values = load_env_file(Path(args.env_file).resolve())
    pg_dsn = build_pg_dsn(env_file_values)

    started_at = time.perf_counter()
    with psycopg.connect(pg_dsn) as conn:
        result = sync_champion_assets(
            conn=conn,
            output_root=output_root,
            dry_run=args.dry_run,
            search_only=args.search_only,
            competition_keys=args.competition_keys,
            limit=args.limit,
            page_size=args.page_size,
            download_workers=args.download_workers,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            min_confidence_score=args.min_confidence_score,
        )

    summary_payload = {
        "generated_at": utc_now(),
        "dry_run": args.dry_run,
        "search_only": args.search_only,
        "output_root": relpath(output_root),
        "summary": result["summary"],
        "total_seconds": round(time.perf_counter() - started_at, 2),
    }
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
