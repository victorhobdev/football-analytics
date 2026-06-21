from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from _repo_root import resolve_repo_root


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_DATASET_ROOT = Path(r"D:\open-data")
DEFAULT_SUMMARY_JSON = ROOT / "platform" / "reports" / "quality" / "statsbomb_open_data_ingestion_summary.json"
DEFAULT_SUMMARY_MD = ROOT / "platform" / "reports" / "quality" / "statsbomb_open_data_ingestion_summary.md"

SOURCE_NAME = "statsbomb_open_data"
SOURCE_KIND = "open_dataset"
USAGE_SCOPE = "research_attribution_required"
LICENSE_SUMMARY = "StatsBomb Open Data - attribution required per upstream README"
TERMS_SUMMARY = (
    "If research or analysis based on this data is published, shared, or distributed, "
    "the source must be stated as StatsBomb and the logo used per upstream media pack."
)

SPLIT_YEAR_KEYS = {
    "premier_league",
    "champions_league",
    "la_liga",
    "serie_a_it",
    "bundesliga",
    "ligue_1",
    "primeira_liga",
}

COMPETITION_KEY_MAP = {
    "1. Bundesliga": "bundesliga",
    "Champions League": "champions_league",
    "FIFA World Cup": "fifa_world_cup_mens",
    "La Liga": "la_liga",
    "Ligue 1": "ligue_1",
    "Premier League": "premier_league",
    "Serie A": "serie_a_it",
}

TEAM_TOKEN_STOPWORDS = {
    "ac",
    "afc",
    "athletic",
    "atletico",
    "cf",
    "club",
    "de",
    "del",
    "deportivo",
    "fc",
    "fk",
    "football",
    "rc",
    "sc",
    "sd",
    "stade",
    "sporting",
    "sv",
    "the",
    "ud",
    "union",
    "wfc",
    "olympique",
}


@dataclass(frozen=True)
class LocalMatch:
    match_id: int
    competition_key: str
    season_label: str
    match_date: date | None
    home_team_id: int | None
    home_team_name: str | None
    away_team_id: int | None
    away_team_name: str | None
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class MatchResolution:
    status: str
    canonical_competition_key: str | None
    season_label: str | None
    local_match_id: int | None
    confidence: float | None
    reason: str
    evidence: dict[str, Any]


@dataclass
class SourceState:
    wc_loaded_match_map: dict[int, int | None]
    local_matches_exact: dict[tuple[Any, ...], list[LocalMatch]]
    local_matches_loose: dict[tuple[Any, ...], list[LocalMatch]]
    local_match_by_score: dict[tuple[Any, ...], list[LocalMatch]]
    local_competition_seasons: set[tuple[str, str]]
    local_players_by_match_team_name: dict[tuple[int, int, str], set[tuple[int, str]]]
    existing_match_map: dict[int, int]
    existing_team_map: dict[int, int]
    existing_player_map: dict[int, int]


@dataclass
class Summary:
    started_at: str
    dataset_root: str
    files_seen: int = 0
    files_hashed: int = 0
    competitions_loaded: int = 0
    matches_loaded: int = 0
    match_status_counts: Counter[str] | None = None
    team_identity_counts: Counter[str] | None = None
    player_identity_counts: Counter[str] | None = None
    lineups_loaded: int = 0
    lineup_quarantined: int = 0
    events_loaded: int = 0
    events_quarantined: int = 0
    events_skipped_wc: int = 0
    three_sixty_frames_loaded: int = 0
    three_sixty_freeze_rows_loaded: int = 0
    orphans_reconstructed: int = 0
    orphans_partial_competition: int = 0
    orphans_unresolved: int = 0
    orphan_events_promoted: int = 0
    orphan_lineups_promoted: int = 0
    parse_failed_files: list[dict[str, Any]] | None = None
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.match_status_counts = Counter()
        self.team_identity_counts = Counter()
        self.player_identity_counts = Counter()
        self.parse_failed_files = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingestao idempotente do StatsBomb Open Data com deduplicacao contra "
            "SportMonks/camada canonica e exclusao da Copa ja carregada."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--summary-md", default=str(DEFAULT_SUMMARY_MD))
    parser.add_argument(
        "--phase",
        choices=("all", "matches", "lineups", "events", "three-sixty", "recover-orphans"),
        default="all",
        help="Permite executar apenas parte da carga para piloto ou retomada.",
    )
    parser.add_argument(
        "--max-match-files",
        type=int,
        default=0,
        help="Limite de arquivos de matches para piloto. Use 0 para sem limite.",
    )
    parser.add_argument(
        "--max-event-files",
        type=int,
        default=0,
        help="Limite de arquivos de events/lineups/three-sixty para piloto. Use 0 para sem limite.",
    )
    parser.add_argument("--skip-hash", action="store_true", help="Nao calcula SHA-256 dos arquivos no manifest.")
    parser.add_argument("--dry-run", action="store_true", help="Executa analise e gera relatorio sem escrever no banco.")
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_run_id() -> str:
    return utc_now().strftime("%Y-%m-%dT%H%M%SZ")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_setting(name: str, env_values: dict[str, str], default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return env_values.get(name, default)


def resolve_pg_dsn(env_values: dict[str, str]) -> str:
    dsn = (
        resolve_setting("FOOTBALL_PG_DSN", env_values)
        or resolve_setting("DATABASE_URL", env_values)
        or "postgresql://football:football@localhost:5432/football_dw"
    )
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg2://")
    if dsn.startswith("postgresql+psycopg://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg://")
    if "@postgres:" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres:", "@localhost:")
    if "@postgres/" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres/", "@localhost/")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    return dsn


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def simplify_team_name(value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    tokens = [
        token
        for token in normalized.split()
        if token not in TEAM_TOKEN_STOPWORDS and not token.isdigit()
    ]
    return " ".join(tokens) if tokens else normalized


def canonical_competition_key(competition_name: str | None) -> str | None:
    if not competition_name:
        return None
    return COMPETITION_KEY_MAP.get(competition_name.strip())


def format_season_label(competition_key: str | None, season_name: str | None) -> str | None:
    if not season_name:
        return None
    text = season_name.strip()
    if competition_key in SPLIT_YEAR_KEYS:
        match = re.fullmatch(r"(\d{4})/(\d{4})", text)
        if match:
            return f"{match.group(1)}_{match.group(2)[2:]}"
        return text.replace("/", "_")
    return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_dataset_path(dataset_root: Path, path: Path) -> str:
    return path.relative_to(dataset_root).as_posix()


def register_source(conn: psycopg.Connection[Any], dataset_root: Path) -> None:
    conn.execute(
        """
        insert into control.external_data_sources (
          source_name,
          source_kind,
          source_root,
          license_summary,
          attribution_required,
          usage_scope,
          terms_summary
        )
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (source_name) do update set
          source_kind = excluded.source_kind,
          source_root = excluded.source_root,
          license_summary = excluded.license_summary,
          attribution_required = excluded.attribution_required,
          usage_scope = excluded.usage_scope,
          terms_summary = excluded.terms_summary,
          updated_at = now()
        """,
        (
            SOURCE_NAME,
            SOURCE_KIND,
            str(dataset_root),
            LICENSE_SUMMARY,
            True,
            USAGE_SCOPE,
            TERMS_SUMMARY,
        ),
    )


def upsert_manifest(
    conn: psycopg.Connection[Any],
    *,
    relative_path: str,
    detected_entity: str,
    provider_match_id: int | None,
    file_size_bytes: int,
    sha256: str,
    load_status: str,
    parse_error: str | None = None,
) -> None:
    conn.execute(
        """
        insert into control.external_file_manifest (
          source_name,
          relative_path,
          detected_entity,
          provider_match_id,
          file_size_bytes,
          sha256,
          load_status,
          parse_error
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_name, relative_path) do update set
          detected_entity = excluded.detected_entity,
          provider_match_id = excluded.provider_match_id,
          file_size_bytes = excluded.file_size_bytes,
          sha256 = excluded.sha256,
          load_status = excluded.load_status,
          parse_error = excluded.parse_error,
          ingested_at = now(),
          updated_at = now()
        """,
        (
            SOURCE_NAME,
            relative_path,
            detected_entity,
            provider_match_id,
            file_size_bytes,
            sha256,
            load_status,
            parse_error,
        ),
    )


def preload_source_state(conn: psycopg.Connection[Any]) -> SourceState:
    wc_rows = conn.execute(
        """
        select source_match_id, max(fixture_id) as fixture_id
        from raw.wc_match_events
        where source_name = %s
        group by source_match_id
        """,
        (SOURCE_NAME,),
    ).fetchall()
    wc_loaded_match_map = {
        as_int(row["source_match_id"]): as_int(row["fixture_id"])
        for row in wc_rows
        if as_int(row["source_match_id"]) is not None
    }

    match_rows = conn.execute(
        """
        select
          fm.match_id,
          fm.competition_key,
          fm.season_label,
          fm.date_day,
          fm.home_team_id,
          home_team.team_name as home_team_name,
          fm.away_team_id,
          away_team.team_name as away_team_name,
          fm.home_goals,
          fm.away_goals
        from mart.fact_matches fm
        left join mart.dim_team home_team
          on home_team.team_id = fm.home_team_id
        left join mart.dim_team away_team
          on away_team.team_id = fm.away_team_id
        """
    ).fetchall()

    local_matches_exact: dict[tuple[Any, ...], list[LocalMatch]] = defaultdict(list)
    local_matches_loose: dict[tuple[Any, ...], list[LocalMatch]] = defaultdict(list)
    local_match_by_score: dict[tuple[Any, ...], list[LocalMatch]] = defaultdict(list)
    local_competition_seasons: set[tuple[str, str]] = set()

    for row in match_rows:
        local = LocalMatch(
            match_id=int(row["match_id"]),
            competition_key=row["competition_key"],
            season_label=row["season_label"],
            match_date=row.get("date_day"),
            home_team_id=as_int(row.get("home_team_id")),
            home_team_name=row.get("home_team_name"),
            away_team_id=as_int(row.get("away_team_id")),
            away_team_name=row.get("away_team_name"),
            home_score=as_int(row.get("home_goals")),
            away_score=as_int(row.get("away_goals")),
        )
        local_competition_seasons.add((local.competition_key, local.season_label))
        strict_key = (
            local.competition_key,
            local.season_label,
            local.match_date,
            normalize_text(local.home_team_name),
            normalize_text(local.away_team_name),
            local.home_score,
            local.away_score,
        )
        loose_key = (
            local.competition_key,
            local.season_label,
            local.match_date,
            simplify_team_name(local.home_team_name),
            simplify_team_name(local.away_team_name),
            local.home_score,
            local.away_score,
        )
        score_key = (
            local.competition_key,
            local.season_label,
            local.match_date,
            local.home_score,
            local.away_score,
        )
        local_matches_exact[strict_key].append(local)
        local_matches_loose[loose_key].append(local)
        local_match_by_score[score_key].append(local)

    player_rows = conn.execute(
        """
        select distinct match_id, team_id, player_id, player_name
        from mart.fact_fixture_lineups
        where player_id is not null and player_name is not null and team_id is not null
        """
    ).fetchall()
    local_players_by_match_team_name: dict[tuple[int, int, str], set[tuple[int, str]]] = defaultdict(set)
    for row in player_rows:
        name_key = normalize_text(row["player_name"])
        if not name_key:
            continue
        local_players_by_match_team_name[(int(row["match_id"]), int(row["team_id"]), name_key)].add(
            (int(row["player_id"]), row["player_name"])
        )

    provider_rows = conn.execute(
        """
        select entity_type, source_id, canonical_id
        from raw.provider_entity_map
        where provider = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    existing_match_map: dict[int, int] = {}
    existing_team_map: dict[int, int] = {}
    existing_player_map: dict[int, int] = {}
    for row in provider_rows:
        source_id = as_int(row["source_id"])
        canonical_id = as_int(row["canonical_id"])
        if source_id is None or canonical_id is None:
            continue
        if row["entity_type"] == "match":
            existing_match_map[source_id] = canonical_id
        elif row["entity_type"] == "team":
            existing_team_map[source_id] = canonical_id
        elif row["entity_type"] == "player":
            existing_player_map[source_id] = canonical_id

    return SourceState(
        wc_loaded_match_map=wc_loaded_match_map,
        local_matches_exact=local_matches_exact,
        local_matches_loose=local_matches_loose,
        local_match_by_score=local_match_by_score,
        local_competition_seasons=local_competition_seasons,
        local_players_by_match_team_name=local_players_by_match_team_name,
        existing_match_map=existing_match_map,
        existing_team_map=existing_team_map,
        existing_player_map=existing_player_map,
    )


def resolve_match_identity(match_row: dict[str, Any], state: SourceState) -> MatchResolution:
    source_match_id = as_int(match_row.get("match_id"))
    competition = match_row.get("competition") or {}
    season = match_row.get("season") or {}
    comp_name = competition.get("competition_name")
    canonical_key = canonical_competition_key(comp_name)
    season_label = format_season_label(canonical_key, season.get("season_name"))
    match_date = as_date(match_row.get("match_date"))
    home_name = match_row.get("home_team", {}).get("home_team_name")
    away_name = match_row.get("away_team", {}).get("away_team_name")
    home_score = as_int(match_row.get("home_score"))
    away_score = as_int(match_row.get("away_score"))

    if source_match_id is not None and source_match_id in state.existing_match_map:
        local_match_id = state.existing_match_map[source_match_id]
        return MatchResolution(
            status="linked_to_sportmonks",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=local_match_id,
            confidence=1.0,
            reason="provider_entity_map_existing_match",
            evidence={"local_match_id": local_match_id},
        )

    if source_match_id is not None and source_match_id in state.wc_loaded_match_map:
        return MatchResolution(
            status="already_loaded_wc",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=state.wc_loaded_match_map[source_match_id],
            confidence=1.0,
            reason="raw_wc_match_events_existing_match",
            evidence={"wc_fixture_id": state.wc_loaded_match_map[source_match_id]},
        )

    if canonical_key is None or season_label is None or match_date is None:
        return MatchResolution(
            status="new_external_match",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=None,
            confidence=0.0,
            reason="competition_not_in_canonical_core",
            evidence={},
        )

    exact_key = (
        canonical_key,
        season_label,
        match_date,
        normalize_text(home_name),
        normalize_text(away_name),
        home_score,
        away_score,
    )
    exact_candidates = state.local_matches_exact.get(exact_key, [])
    if len(exact_candidates) == 1:
        candidate = exact_candidates[0]
        return MatchResolution(
            status="linked_to_sportmonks",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=candidate.match_id,
            confidence=1.0,
            reason="exact_competition_season_date_teams_score",
            evidence={"local_match_id": candidate.match_id},
        )
    if len(exact_candidates) > 1:
        return MatchResolution(
            status="ambiguous_match",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=None,
            confidence=0.0,
            reason="multiple_exact_candidates",
            evidence={"candidate_match_ids": [candidate.match_id for candidate in exact_candidates]},
        )

    loose_key = (
        canonical_key,
        season_label,
        match_date,
        simplify_team_name(home_name),
        simplify_team_name(away_name),
        home_score,
        away_score,
    )
    loose_candidates = state.local_matches_loose.get(loose_key, [])
    if len(loose_candidates) == 1:
        candidate = loose_candidates[0]
        return MatchResolution(
            status="linked_to_sportmonks",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=candidate.match_id,
            confidence=0.95,
            reason="loose_team_name_match",
            evidence={"local_match_id": candidate.match_id},
        )
    if len(loose_candidates) > 1:
        return MatchResolution(
            status="ambiguous_match",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=None,
            confidence=0.0,
            reason="multiple_loose_candidates",
            evidence={"candidate_match_ids": [candidate.match_id for candidate in loose_candidates]},
        )

    overlapping_core = (canonical_key, season_label) in state.local_competition_seasons
    score_candidates = state.local_match_by_score.get(
        (canonical_key, season_label, match_date, home_score, away_score),
        []
    )
    if overlapping_core:
        if len(score_candidates) == 1:
            return MatchResolution(
                status="ambiguous_match",
                canonical_competition_key=canonical_key,
                season_label=season_label,
                local_match_id=None,
                confidence=0.0,
                reason="overlapping_core_needs_manual_team_confirmation",
                evidence={"candidate_match_id": score_candidates[0].match_id},
            )
        return MatchResolution(
            status="ambiguous_match",
            canonical_competition_key=canonical_key,
            season_label=season_label,
            local_match_id=None,
            confidence=0.0,
            reason="overlapping_core_without_unique_match_resolution",
            evidence={"candidate_match_ids": [candidate.match_id for candidate in score_candidates]},
        )

    return MatchResolution(
        status="new_external_match",
        canonical_competition_key=canonical_key,
        season_label=season_label,
        local_match_id=None,
        confidence=0.0,
        reason="canonical_competition_outside_core_window",
        evidence={},
    )


def merge_identity(
    existing: dict[int, dict[str, Any]],
    source_id: int,
    *,
    source_name: str | None,
    identity_status: str,
    local_id: int | None,
    confidence: float | None,
    resolution_reason: str,
    evidence: dict[str, Any],
) -> None:
    current = existing.get(source_id)
    if current is None:
        existing[source_id] = {
            "source_name": source_name,
            "identity_status": identity_status,
            "local_id": local_id,
            "confidence": confidence,
            "resolution_reason": resolution_reason,
            "evidence": evidence,
        }
        return
    current_local_id = current.get("local_id")
    if (
        current_local_id is not None
        and local_id is not None
        and current_local_id != local_id
    ):
        current["identity_status"] = "ambiguous_conflict"
        current["local_id"] = None
        current["confidence"] = 0.0
        current["resolution_reason"] = "conflicting_local_ids_across_matches"
        current["evidence"] = {
            "previous_local_id": current_local_id,
            "conflicting_local_id": local_id,
            "previous_evidence": current.get("evidence"),
            "conflicting_evidence": evidence,
        }
        return

    precedence = {
        "linked_to_sportmonks": 4,
        "already_loaded_wc": 3,
        "ambiguous_conflict": 3,
        "ambiguous_player": 2,
        "ambiguous_match": 2,
        "unresolved": 1,
    }
    if precedence.get(identity_status, 0) >= precedence.get(current["identity_status"], 0):
        existing[source_id] = {
            "source_name": source_name or current.get("source_name"),
            "identity_status": identity_status,
            "local_id": local_id if local_id is not None else current_local_id,
            "confidence": confidence,
            "resolution_reason": resolution_reason,
            "evidence": evidence,
        }


def upsert_provider_entity_map(conn: psycopg.Connection[Any], entity_type: str, source_id: int, canonical_id: int) -> None:
    conn.execute(
        """
        insert into raw.provider_entity_map (provider, entity_type, source_id, canonical_id)
        values (%s, %s, %s, %s)
        on conflict (provider, entity_type, source_id) do update set
          canonical_id = excluded.canonical_id,
          updated_at = now()
        """,
        (SOURCE_NAME, entity_type, str(source_id), str(canonical_id)),
    )


def load_competition_seasons(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    summary: Summary,
    skip_hash: bool,
) -> list[dict[str, Any]]:
    path = dataset_root / "data" / "competitions.json"
    rows = read_json_file(path)
    sha = "skipped" if skip_hash else sha256_file(path)
    summary.files_seen += 1
    if not skip_hash:
        summary.files_hashed += 1
    relative_path = relative_dataset_path(dataset_root, path)

    conn.execute("delete from raw.statsbomb_competition_seasons where source_name = %s", (SOURCE_NAME,))
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy raw.statsbomb_competition_seasons (
              source_name,
              competition_id,
              season_id,
              competition_name,
              country_name,
              competition_gender,
              competition_youth,
              competition_international,
              season_name,
              match_updated,
              match_updated_360,
              match_available,
              match_available_360,
              payload
            ) from stdin
            """
        ) as copy:
            for row in rows:
                copy.write_row(
                    (
                        SOURCE_NAME,
                        as_int(row.get("competition_id")),
                        as_int(row.get("season_id")),
                        row.get("competition_name"),
                        row.get("country_name"),
                        row.get("competition_gender"),
                        row.get("competition_youth"),
                        row.get("competition_international"),
                        row.get("season_name"),
                        as_datetime(row.get("match_updated")),
                        as_datetime(row.get("match_updated_360")),
                        as_datetime(row.get("match_available")),
                        as_datetime(row.get("match_available_360")),
                        Jsonb(row),
                    )
                )
    upsert_manifest(
        conn,
        relative_path=relative_path,
        detected_entity="competition_seasons",
        provider_match_id=None,
        file_size_bytes=path.stat().st_size,
        sha256=sha,
        load_status="loaded",
    )
    summary.competitions_loaded = len(rows)
    return rows


def write_match_identities(
    conn: psycopg.Connection[Any],
    match_rows: list[tuple[Any, ...]],
    identity_rows: list[tuple[Any, ...]],
    team_identity: dict[int, dict[str, Any]],
    summary: Summary,
) -> None:
    team_provider_mappings: list[tuple[int, int]] = []
    conn.execute("delete from raw.statsbomb_matches where source_name = %s", (SOURCE_NAME,))
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy raw.statsbomb_matches (
              source_name,
              match_id,
              competition_id,
              season_id,
              canonical_competition_key,
              season_label,
              match_date,
              kick_off,
              home_team_id,
              home_team_name,
              away_team_id,
              away_team_name,
              home_score,
              away_score,
              match_status,
              match_status_360,
              competition_stage_id,
              competition_stage_name,
              match_week,
              stadium_id,
              stadium_name,
              referee_id,
              referee_name,
              local_match_id,
              identity_status,
              identity_confidence,
              identity_reason,
              metadata,
              payload
            ) from stdin
            """
        ) as copy:
            for row in match_rows:
                copy.write_row(row)

    conn.execute("delete from mart.stg_statsbomb_match_identity where source_name = %s", (SOURCE_NAME,))
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy mart.stg_statsbomb_match_identity (
              source_name,
              source_match_id,
              canonical_competition_key,
              season_label,
              match_date,
              source_home_team_id,
              source_home_team_name,
              source_away_team_id,
              source_away_team_name,
              source_home_score,
              source_away_score,
              identity_status,
              confidence,
              local_match_id,
              resolution_reason,
              evidence
            ) from stdin
            """
        ) as copy:
            for row in identity_rows:
                copy.write_row(row)

    conn.execute("delete from mart.stg_statsbomb_team_identity where source_name = %s", (SOURCE_NAME,))
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy mart.stg_statsbomb_team_identity (
              source_name,
              source_team_id,
              source_team_name,
              identity_status,
              confidence,
              local_team_id,
              resolution_reason,
              evidence
            ) from stdin
            """
        ) as copy:
            for source_team_id, identity in sorted(team_identity.items()):
                copy.write_row(
                    (
                        SOURCE_NAME,
                        source_team_id,
                        identity.get("source_name"),
                        identity["identity_status"],
                        identity.get("confidence"),
                        identity.get("local_id"),
                        identity.get("resolution_reason"),
                        Jsonb(identity.get("evidence") or {}),
                    )
                )
                if identity["identity_status"] == "linked_to_sportmonks" and identity.get("local_id") is not None:
                    team_provider_mappings.append((source_team_id, int(identity["local_id"])))
                summary.team_identity_counts[identity["identity_status"]] += 1
    for source_team_id, local_team_id in team_provider_mappings:
        upsert_provider_entity_map(conn, "team", source_team_id, local_team_id)


def load_matches(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    state: SourceState,
    summary: Summary,
    *,
    max_match_files: int,
    skip_hash: bool,
    dry_run: bool,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    match_root = dataset_root / "data" / "matches"
    competition_seasons = load_competition_seasons(conn, dataset_root, summary, skip_hash) if not dry_run else read_json_file(dataset_root / "data" / "competitions.json")
    _ = competition_seasons

    match_rows: list[tuple[Any, ...]] = []
    identity_rows: list[tuple[Any, ...]] = []
    team_identity: dict[int, dict[str, Any]] = {}
    all_matches: list[dict[str, Any]] = []
    files_processed = 0

    for competition_dir in sorted(path for path in match_root.iterdir() if path.is_dir()):
        for match_file in sorted(competition_dir.glob("*.json")):
            if max_match_files > 0 and files_processed >= max_match_files:
                break
            files_processed += 1
            summary.files_seen += 1
            file_hash = "skipped" if skip_hash else sha256_file(match_file)
            if not skip_hash:
                summary.files_hashed += 1
            relative_path = relative_dataset_path(dataset_root, match_file)
            rows = read_json_file(match_file)
            for row in rows:
                resolution = resolve_match_identity(row, state)
                summary.match_status_counts[resolution.status] += 1
                match_id = as_int(row.get("match_id"))
                competition = row.get("competition") or {}
                season = row.get("season") or {}
                home_team = row.get("home_team") or {}
                away_team = row.get("away_team") or {}
                stage = row.get("competition_stage") or {}
                stadium = row.get("stadium") or {}
                referee = row.get("referee") or {}
                metadata = row.get("metadata") or {}
                match_rows.append(
                    (
                        SOURCE_NAME,
                        match_id,
                        as_int(competition.get("competition_id")),
                        as_int(season.get("season_id")),
                        resolution.canonical_competition_key,
                        resolution.season_label,
                        as_date(row.get("match_date")),
                        row.get("kick_off"),
                        as_int(home_team.get("home_team_id")),
                        home_team.get("home_team_name"),
                        as_int(away_team.get("away_team_id")),
                        away_team.get("away_team_name"),
                        as_int(row.get("home_score")),
                        as_int(row.get("away_score")),
                        row.get("match_status"),
                        row.get("match_status_360"),
                        as_int(stage.get("id")),
                        stage.get("name"),
                        as_int(row.get("match_week")),
                        as_int(stadium.get("id")),
                        stadium.get("name"),
                        as_int(referee.get("id")),
                        referee.get("name"),
                        resolution.local_match_id,
                        resolution.status,
                        resolution.confidence,
                        resolution.reason,
                        Jsonb(metadata),
                        Jsonb(row),
                    )
                )
                identity_rows.append(
                    (
                        SOURCE_NAME,
                        match_id,
                        resolution.canonical_competition_key,
                        resolution.season_label,
                        as_date(row.get("match_date")),
                        as_int(home_team.get("home_team_id")),
                        home_team.get("home_team_name"),
                        as_int(away_team.get("away_team_id")),
                        away_team.get("away_team_name"),
                        as_int(row.get("home_score")),
                        as_int(row.get("away_score")),
                        resolution.status,
                        resolution.confidence,
                        resolution.local_match_id,
                        resolution.reason,
                        Jsonb(resolution.evidence),
                    )
                )
                if resolution.status == "linked_to_sportmonks" and match_id is not None and resolution.local_match_id is not None:
                    state.existing_match_map[match_id] = resolution.local_match_id
                    upsert_provider_entity_map(conn, "match", match_id, resolution.local_match_id)

                    local_candidates = state.local_matches_exact.get(
                        (
                            resolution.canonical_competition_key,
                            resolution.season_label,
                            as_date(row.get("match_date")),
                            normalize_text(home_team.get("home_team_name")),
                            normalize_text(away_team.get("away_team_name")),
                            as_int(row.get("home_score")),
                            as_int(row.get("away_score")),
                        ),
                        [],
                    )
                    if len(local_candidates) == 1:
                        local = local_candidates[0]
                        source_home_team_id = as_int(home_team.get("home_team_id"))
                        source_away_team_id = as_int(away_team.get("away_team_id"))
                        if source_home_team_id is not None and local.home_team_id is not None:
                            merge_identity(
                                team_identity,
                                source_home_team_id,
                                source_name=home_team.get("home_team_name"),
                                identity_status="linked_to_sportmonks",
                                local_id=local.home_team_id,
                                confidence=1.0,
                                resolution_reason="home_team_from_linked_match",
                                evidence={"local_match_id": local.match_id},
                            )
                            state.existing_team_map[source_home_team_id] = local.home_team_id
                        if source_away_team_id is not None and local.away_team_id is not None:
                            merge_identity(
                                team_identity,
                                source_away_team_id,
                                source_name=away_team.get("away_team_name"),
                                identity_status="linked_to_sportmonks",
                                local_id=local.away_team_id,
                                confidence=1.0,
                                resolution_reason="away_team_from_linked_match",
                                evidence={"local_match_id": local.match_id},
                            )
                            state.existing_team_map[source_away_team_id] = local.away_team_id
                else:
                    source_home_team_id = as_int(home_team.get("home_team_id"))
                    source_away_team_id = as_int(away_team.get("away_team_id"))
                    if source_home_team_id is not None:
                        merge_identity(
                            team_identity,
                            source_home_team_id,
                            source_name=home_team.get("home_team_name"),
                            identity_status="unresolved",
                            local_id=state.existing_team_map.get(source_home_team_id),
                            confidence=1.0 if source_home_team_id in state.existing_team_map else 0.0,
                            resolution_reason="no_linked_match_context",
                            evidence={},
                        )
                    if source_away_team_id is not None:
                        merge_identity(
                            team_identity,
                            source_away_team_id,
                            source_name=away_team.get("away_team_name"),
                            identity_status="unresolved",
                            local_id=state.existing_team_map.get(source_away_team_id),
                            confidence=1.0 if source_away_team_id in state.existing_team_map else 0.0,
                            resolution_reason="no_linked_match_context",
                            evidence={},
                        )

                all_matches.append(row)
            if not dry_run:
                upsert_manifest(
                    conn,
                    relative_path=relative_path,
                    detected_entity="matches",
                    provider_match_id=None,
                    file_size_bytes=match_file.stat().st_size,
                    sha256=file_hash,
                    load_status="loaded",
                )
        if max_match_files > 0 and files_processed >= max_match_files:
            break

    if not dry_run:
        write_match_identities(conn, match_rows, identity_rows, team_identity, summary)
        summary.matches_loaded = len(match_rows)
    return state.existing_team_map.copy(), state.existing_player_map.copy(), all_matches


def resolve_player_identity(
    state: SourceState,
    *,
    local_match_id: int | None,
    local_team_id: int | None,
    source_player_id: int | None,
    source_player_name: str | None,
) -> tuple[int | None, str, str, float]:
    if source_player_id is None:
        return None, "unresolved", "missing_source_player_id", 0.0
    if source_player_id in state.existing_player_map:
        return state.existing_player_map[source_player_id], "linked_to_sportmonks", "provider_entity_map_existing_player", 1.0
    if local_match_id is None or local_team_id is None:
        return None, "unresolved", "no_linked_match_team_context", 0.0

    normalized = normalize_text(source_player_name)
    if not normalized:
        return None, "unresolved", "missing_player_name", 0.0

    candidates = state.local_players_by_match_team_name.get((local_match_id, local_team_id, normalized), set())
    if len(candidates) == 1:
        local_player_id, _ = next(iter(candidates))
        return local_player_id, "linked_to_sportmonks", "exact_match_team_player_name", 0.95
    if len(candidates) > 1:
        return None, "ambiguous_player", "multiple_local_players_same_name", 0.0
    return None, "unresolved", "no_local_player_name_match", 0.0


def write_player_identity_rows(conn: psycopg.Connection[Any], player_identity: dict[int, dict[str, Any]], summary: Summary) -> None:
    player_provider_mappings: list[tuple[int, int]] = []
    conn.execute("delete from mart.stg_statsbomb_player_identity where source_name = %s", (SOURCE_NAME,))
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy mart.stg_statsbomb_player_identity (
              source_name,
              source_player_id,
              source_player_name,
              identity_status,
              confidence,
              local_player_id,
              resolution_reason,
              evidence
            ) from stdin
            """
        ) as copy:
            for source_player_id, identity in sorted(player_identity.items()):
                copy.write_row(
                    (
                        SOURCE_NAME,
                        source_player_id,
                        identity.get("source_name"),
                        identity["identity_status"],
                        identity.get("confidence"),
                        identity.get("local_id"),
                        identity.get("resolution_reason"),
                        Jsonb(identity.get("evidence") or {}),
                    )
                )
                if identity["identity_status"] == "linked_to_sportmonks" and identity.get("local_id") is not None:
                    player_provider_mappings.append((source_player_id, int(identity["local_id"])))
                summary.player_identity_counts[identity["identity_status"]] += 1
    for source_player_id, local_player_id in player_provider_mappings:
        upsert_provider_entity_map(conn, "player", source_player_id, local_player_id)


def load_lineups(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    state: SourceState,
    summary: Summary,
    *,
    max_event_files: int,
    skip_hash: bool,
    dry_run: bool,
) -> None:
    lineups_root = dataset_root / "data" / "lineups"
    match_state_rows = conn.execute(
        """
        select match_id, local_match_id, identity_status
        from raw.statsbomb_matches
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    match_state_map = {
        int(row["match_id"]): {
            "local_match_id": as_int(row["local_match_id"]),
            "identity_status": row["identity_status"],
        }
        for row in match_state_rows
    }

    team_rows = conn.execute(
        """
        select source_team_id, local_team_id, identity_status
        from mart.stg_statsbomb_team_identity
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    team_map = {
        int(row["source_team_id"]): as_int(row["local_team_id"])
        for row in team_rows
        if row["identity_status"] == "linked_to_sportmonks" and as_int(row["local_team_id"]) is not None
    }

    player_identity: dict[int, dict[str, Any]] = {}
    files_processed = 0
    for lineup_file in sorted(lineups_root.glob("*.json")):
        if max_event_files > 0 and files_processed >= max_event_files:
            break
        files_processed += 1
        summary.files_seen += 1
        file_hash = "skipped" if skip_hash else sha256_file(lineup_file)
        if not skip_hash:
            summary.files_hashed += 1
        relative_path = relative_dataset_path(dataset_root, lineup_file)
        match_id = as_int(lineup_file.stem)
        match_state = match_state_map.get(match_id)
        if match_state is None:
            rows = read_json_file(lineup_file)
            if not dry_run:
                conn.execute("delete from raw.statsbomb_quarantine_lineups where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
                with conn.cursor() as cur:
                    with cur.copy(
                        """
                        copy raw.statsbomb_quarantine_lineups (
                          source_name,
                          match_id,
                          source_team_id,
                          source_player_id,
                          quarantine_reason,
                          payload
                        ) from stdin
                        """
                    ) as copy:
                        for team_entry in rows:
                            team_id = as_int(team_entry.get("team_id"))
                            for player in team_entry.get("lineup") or []:
                                copy.write_row(
                                    (
                                        SOURCE_NAME,
                                        match_id,
                                        team_id,
                                        as_int(player.get("player_id")),
                                        "missing_match_metadata",
                                        Jsonb({"team": team_entry, "player": player}),
                                    )
                                )
                                summary.lineup_quarantined += 1
                upsert_manifest(
                    conn,
                    relative_path=relative_path,
                    detected_entity="lineups",
                    provider_match_id=match_id,
                    file_size_bytes=lineup_file.stat().st_size,
                    sha256=file_hash,
                    load_status="quarantined_missing_match_metadata",
                )
            continue

        rows = read_json_file(lineup_file)
        lineup_rows: list[tuple[Any, ...]] = []
        for team_entry in rows:
            source_team_id = as_int(team_entry.get("team_id"))
            source_team_name = team_entry.get("team_name")
            local_match_id = match_state.get("local_match_id")
            local_team_id = team_map.get(source_team_id)
            for player in team_entry.get("lineup") or []:
                source_player_id = as_int(player.get("player_id"))
                source_player_name = player.get("player_name")
                local_player_id, player_status, player_reason, player_confidence = resolve_player_identity(
                    state,
                    local_match_id=local_match_id,
                    local_team_id=local_team_id,
                    source_player_id=source_player_id,
                    source_player_name=source_player_name,
                )
                if source_player_id is not None:
                    merge_identity(
                        player_identity,
                        source_player_id,
                        source_name=source_player_name,
                        identity_status=player_status,
                        local_id=local_player_id,
                        confidence=player_confidence,
                        resolution_reason=player_reason,
                        evidence={"match_id": match_id, "source_team_id": source_team_id, "local_match_id": local_match_id, "local_team_id": local_team_id},
                    )
                    if player_status == "linked_to_sportmonks" and local_player_id is not None:
                        state.existing_player_map[source_player_id] = local_player_id
                lineup_rows.append(
                    (
                        SOURCE_NAME,
                        match_id,
                        source_team_id,
                        source_team_name,
                        source_player_id,
                        source_player_name,
                        as_int(player.get("jersey_number")),
                        (player.get("country") or {}).get("name"),
                        local_match_id,
                        local_team_id,
                        local_player_id,
                        match_state.get("identity_status"),
                        player_status,
                        player_reason,
                        player_confidence,
                        Jsonb({"team": team_entry, "player": player}),
                    )
                )

        if not dry_run:
            conn.execute("delete from raw.statsbomb_lineups where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
            with conn.cursor() as cur:
                with cur.copy(
                    """
                    copy raw.statsbomb_lineups (
                      source_name,
                      match_id,
                      source_team_id,
                      source_team_name,
                      source_player_id,
                      source_player_name,
                      jersey_number,
                      country_name,
                      local_match_id,
                      local_team_id,
                      local_player_id,
                      match_identity_status,
                      player_identity_status,
                      player_identity_reason,
                      player_identity_confidence,
                      payload
                    ) from stdin
                    """
                ) as copy:
                    for row in lineup_rows:
                        copy.write_row(row)
                        summary.lineups_loaded += 1
            upsert_manifest(
                conn,
                relative_path=relative_path,
                detected_entity="lineups",
                provider_match_id=match_id,
                file_size_bytes=lineup_file.stat().st_size,
                sha256=file_hash,
                load_status="loaded",
            )

    if not dry_run:
        write_player_identity_rows(conn, player_identity, summary)


def extract_event_fields(event: dict[str, Any]) -> tuple[Any, ...]:
    event_type = event.get("type") or {}
    play_pattern = event.get("play_pattern") or {}
    possession_team = event.get("possession_team") or {}
    team = event.get("team") or {}
    player = event.get("player") or {}
    return (
        event.get("id"),
        as_int(event.get("index")),
        as_int(event.get("period")),
        event.get("timestamp"),
        as_int(event.get("minute")),
        event.get("second"),
        event_type.get("name"),
        as_int(event.get("possession")),
        as_int(possession_team.get("id")),
        possession_team.get("name"),
        play_pattern.get("name"),
        as_int(team.get("id")),
        team.get("name"),
        as_int(player.get("id")),
        player.get("name"),
    )


def load_events(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    state: SourceState,
    summary: Summary,
    *,
    max_event_files: int,
    skip_hash: bool,
    dry_run: bool,
) -> None:
    events_root = dataset_root / "data" / "events"
    match_state_rows = conn.execute(
        """
        select match_id, local_match_id, identity_status
        from raw.statsbomb_matches
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    match_state_map = {
        int(row["match_id"]): {
            "local_match_id": as_int(row["local_match_id"]),
            "identity_status": row["identity_status"],
        }
        for row in match_state_rows
    }

    team_rows = conn.execute(
        """
        select source_team_id, local_team_id, identity_status
        from mart.stg_statsbomb_team_identity
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    team_map = {
        int(row["source_team_id"]): as_int(row["local_team_id"])
        for row in team_rows
        if row["identity_status"] == "linked_to_sportmonks" and as_int(row["local_team_id"]) is not None
    }

    player_rows = conn.execute(
        """
        select source_player_id, local_player_id, identity_status
        from mart.stg_statsbomb_player_identity
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    player_map = {
        int(row["source_player_id"]): as_int(row["local_player_id"])
        for row in player_rows
        if row["identity_status"] == "linked_to_sportmonks" and as_int(row["local_player_id"]) is not None
    }

    files_processed = 0
    for event_file in sorted(events_root.glob("*.json")):
        if max_event_files > 0 and files_processed >= max_event_files:
            break
        files_processed += 1
        summary.files_seen += 1
        file_hash = "skipped" if skip_hash else sha256_file(event_file)
        if not skip_hash:
            summary.files_hashed += 1
        relative_path = relative_dataset_path(dataset_root, event_file)
        match_id = as_int(event_file.stem)
        match_state = match_state_map.get(match_id)
        if match_state is None:
            rows = read_json_file(event_file)
            if not dry_run:
                conn.execute("delete from raw.statsbomb_quarantine_events where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
                with conn.cursor() as cur:
                    with cur.copy(
                        """
                        copy raw.statsbomb_quarantine_events (
                          source_name,
                          match_id,
                          event_id,
                          quarantine_reason,
                          payload
                        ) from stdin
                        """
                    ) as copy:
                        for event in rows:
                            copy.write_row(
                                (
                                    SOURCE_NAME,
                                    match_id,
                                    event.get("id"),
                                    "missing_match_metadata",
                                    Jsonb(event),
                                )
                            )
                            summary.events_quarantined += 1
                upsert_manifest(
                    conn,
                    relative_path=relative_path,
                    detected_entity="events",
                    provider_match_id=match_id,
                    file_size_bytes=event_file.stat().st_size,
                    sha256=file_hash,
                    load_status="quarantined_missing_match_metadata",
                )
            continue

        if match_state["identity_status"] == "already_loaded_wc":
            if not dry_run:
                upsert_manifest(
                    conn,
                    relative_path=relative_path,
                    detected_entity="events",
                    provider_match_id=match_id,
                    file_size_bytes=event_file.stat().st_size,
                    sha256=file_hash,
                    load_status="already_loaded_wc",
                )
            summary.events_skipped_wc += 1
            continue

        rows = read_json_file(event_file)
        event_rows: list[tuple[Any, ...]] = []
        for event in rows:
            (
                event_id,
                event_index,
                period,
                event_timestamp,
                minute,
                second,
                event_type,
                possession,
                possession_team_id,
                possession_team_name,
                play_pattern,
                source_team_id,
                source_team_name,
                source_player_id,
                source_player_name,
            ) = extract_event_fields(event)
            local_team_id = team_map.get(source_team_id) if source_team_id is not None else None
            local_player_id = player_map.get(source_player_id) if source_player_id is not None else None
            player_identity_status = (
                "linked_to_sportmonks" if source_player_id is not None and source_player_id in player_map else "unresolved"
            )
            event_rows.append(
                (
                    SOURCE_NAME,
                    match_id,
                    event_id,
                    event_index,
                    period,
                    event_timestamp,
                    minute,
                    second,
                    event_type,
                    possession,
                    possession_team_id,
                    possession_team_name,
                    play_pattern,
                    source_team_id,
                    source_team_name,
                    source_player_id,
                    source_player_name,
                    match_state.get("local_match_id"),
                    local_team_id,
                    local_player_id,
                    match_state.get("identity_status"),
                    player_identity_status,
                    Jsonb(event),
                )
            )

        if not dry_run:
            conn.execute("delete from raw.statsbomb_events where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
            with conn.cursor() as cur:
                with cur.copy(
                    """
                    copy raw.statsbomb_events (
                      source_name,
                      match_id,
                      event_id,
                      event_index,
                      period,
                      event_timestamp,
                      minute,
                      second,
                      event_type,
                      possession,
                      possession_team_id,
                      possession_team_name,
                      play_pattern,
                      source_team_id,
                      source_team_name,
                      source_player_id,
                      source_player_name,
                      local_match_id,
                      local_team_id,
                      local_player_id,
                      match_identity_status,
                      player_identity_status,
                      payload
                    ) from stdin
                    """
                ) as copy:
                    for row in event_rows:
                        copy.write_row(row)
                        summary.events_loaded += 1
            upsert_manifest(
                conn,
                relative_path=relative_path,
                detected_entity="events",
                provider_match_id=match_id,
                file_size_bytes=event_file.stat().st_size,
                sha256=file_hash,
                load_status="loaded",
            )


def load_three_sixty(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    summary: Summary,
    *,
    max_event_files: int,
    skip_hash: bool,
    dry_run: bool,
) -> None:
    frames_root = dataset_root / "data" / "three-sixty"
    match_state_rows = conn.execute(
        """
        select match_id, local_match_id
        from raw.statsbomb_matches
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    match_state_map = {
        int(row["match_id"]): as_int(row["local_match_id"])
        for row in match_state_rows
    }

    files_processed = 0
    for frame_file in sorted(frames_root.glob("*.json")):
        if max_event_files > 0 and files_processed >= max_event_files:
            break
        files_processed += 1
        summary.files_seen += 1
        file_hash = "skipped" if skip_hash else sha256_file(frame_file)
        if not skip_hash:
            summary.files_hashed += 1
        relative_path = relative_dataset_path(dataset_root, frame_file)
        match_id = as_int(frame_file.stem)
        try:
            rows = read_json_file(frame_file)
        except json.JSONDecodeError as exc:
            summary.parse_failed_files.append(
                {"relative_path": relative_path, "message": str(exc)}
            )
            if not dry_run:
                upsert_manifest(
                    conn,
                    relative_path=relative_path,
                    detected_entity="three_sixty",
                    provider_match_id=match_id,
                    file_size_bytes=frame_file.stat().st_size,
                    sha256=file_hash,
                    load_status="parse_failed",
                    parse_error=str(exc),
                )
            continue

        frame_rows: list[tuple[Any, ...]] = []
        freeze_rows: list[tuple[Any, ...]] = []
        local_match_id = match_state_map.get(match_id)
        for row in rows:
            event_uuid = row.get("event_uuid")
            frame_rows.append(
                (
                    SOURCE_NAME,
                    match_id,
                    event_uuid,
                    local_match_id,
                    Jsonb(row.get("visible_area")),
                    Jsonb(row),
                )
            )
            for freeze_index, freeze_row in enumerate(row.get("freeze_frame") or []):
                location = freeze_row.get("location") or [None, None]
                freeze_rows.append(
                    (
                        SOURCE_NAME,
                        match_id,
                        event_uuid,
                        freeze_index,
                        freeze_row.get("teammate"),
                        freeze_row.get("actor"),
                        freeze_row.get("keeper"),
                        location[0] if len(location) > 0 else None,
                        location[1] if len(location) > 1 else None,
                    )
                )

        if not dry_run:
            conn.execute("delete from raw.statsbomb_three_sixty_freeze_frame where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
            conn.execute("delete from raw.statsbomb_three_sixty_frames where source_name = %s and match_id = %s", (SOURCE_NAME, match_id))
            with conn.cursor() as cur:
                with cur.copy(
                    """
                    copy raw.statsbomb_three_sixty_frames (
                      source_name,
                      match_id,
                      event_uuid,
                      local_match_id,
                      visible_area,
                      payload
                    ) from stdin
                    """
                ) as copy:
                    for frame_row in frame_rows:
                        copy.write_row(frame_row)
                        summary.three_sixty_frames_loaded += 1
                with cur.copy(
                    """
                    copy raw.statsbomb_three_sixty_freeze_frame (
                      source_name,
                      match_id,
                      event_uuid,
                      freeze_frame_index,
                      teammate,
                      actor,
                      keeper,
                      location_x,
                      location_y
                    ) from stdin
                    """
                ) as copy:
                    for freeze_row in freeze_rows:
                        copy.write_row(freeze_row)
                        summary.three_sixty_freeze_rows_loaded += 1
            upsert_manifest(
                conn,
                relative_path=relative_path,
                detected_entity="three_sixty",
                provider_match_id=match_id,
                file_size_bytes=frame_file.stat().st_size,
                sha256=file_hash,
                load_status="loaded",
            )


def reconstruct_orphan_match(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Deriva metadata deterministica de uma partida a partir do payload de events.

    O StatsBomb Open Data publica events/lineups de algumas partidas sem o
    arquivo matches/*.json correspondente. Esses orfaos entram em quarentena na
    carga normal porque falta metadata (data, competicao, placar). Esta funcao
    reconstrói o que é deterministico a partir do proprio payload de events:

    - home/away team  : primeiro/segundo evento "Starting XI"
    - home/away score : contagem de Shot com outcome=Goal por time

    Nao inventa match_date (nao existe no payload). A competicao/season é
    atribuida depois por contiguidade de match_id em assign_orphan_competition.
    """
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    for event in events:
        if (event.get("type") or {}).get("name") == "Starting XI":
            team = event.get("team") or {}
            team_name = team.get("name")
            team_id = as_int(team.get("id"))
            if home_team_name is None:
                home_team_name = team_name
                home_team_id = team_id
            elif away_team_name is None and team_name != home_team_name:
                away_team_name = team_name
                away_team_id = team_id
                break

    home_score = 0
    away_score = 0
    for event in events:
        if (event.get("type") or {}).get("name") != "Shot":
            continue
        if (event.get("shot", {}).get("outcome", {}) or {}).get("name") != "Goal":
            continue
        scoring_team = (event.get("team") or {}).get("name")
        if scoring_team == home_team_name:
            home_score += 1
        elif scoring_team == away_team_name:
            away_score += 1

    return {
        "home_team_id": home_team_id,
        "home_team_name": home_team_name,
        "away_team_id": away_team_id,
        "away_team_name": away_team_name,
        "home_score": home_score,
        "away_score": away_score,
    }


def assign_orphan_competition(
    match_id: int,
    team_names: set[str],
    season_spans: dict[tuple[int, int], tuple[int, int]],
    season_team_rosters: dict[tuple[int, int], set[str]],
    season_labels: dict[tuple[int, int], tuple[str | None, str | None]],
) -> tuple[int | None, int | None, str | None, str | None, str]:
    """Atribui competicao/season a um match_id orfao por contiguidade de ID.

    Retorna (competition_id, season_id, canonical_competition_key, season_label,
    reason). Prioriza a season cujo range de match_id CONTENHA o orfao e cujos
    times todos existam naquela season. Se apenas a competicao for derivavel
    (times casam mas season e ambigua ou inexistente), retorna competicao com
    season_id=None -> status parcial.
    """
    # Seasons cujo range de match_id contem o orfao e cujo team-set bate.
    contained_team_match = [
        season
        for season, (lo, hi) in season_spans.items()
        if lo <= match_id <= hi
        and team_names
        and team_names.issubset(season_team_rosters.get(season, set()))
    ]
    if len(contained_team_match) == 1:
        season = contained_team_match[0]
        comp_key, season_label = season_labels[season]
        return season[0], season[1], comp_key, season_label, "id_range_and_team_roster_contained"

    # Fallback: competicao cujo team-set contem todos os times (season ambigua).
    team_match_seasons = [
        season
        for season, roster in season_team_rosters.items()
        if team_names and team_names.issubset(roster)
    ]
    if len(team_match_seasons) >= 1:
        seasons_by_comp: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for season in team_match_seasons:
            seasons_by_comp[season[0]].append(season)
        # Competicao unica mesmo com varias seasons possiveis.
        if len(seasons_by_comp) == 1:
            comp_id = next(iter(seasons_by_comp))
            comp_key, _ = season_labels[(comp_id, team_match_seasons[0][1])]
            return comp_id, None, comp_key, None, "competition_derived_season_ambiguous"
        # Competicoes distintas: nao atribui nada com seguranca.
        comps = sorted({s[0] for s in team_match_seasons})
        return None, None, None, None, f"ambiguous_competitions_{comps}"

    return None, None, None, None, "no_team_roster_match"


def recover_orphans(
    conn: psycopg.Connection[Any],
    dataset_root: Path,
    summary: Summary,
    *,
    skip_hash: bool,
    dry_run: bool,
) -> None:
    """Promove partidas orfas da quarentena para raw.statsbomb_* com metadata reconstruida.

    Orfaos = partidas com events/lineups no dataset mas sem arquivo matches/*.json.
    A metadata (times, placar) e reconstruida do payload de events; competicao/season
    e atribuida por contiguidade de match_id contra as seasons ja carregadas.
    Tudo entra como identity_status='orphan_metadata_reconstructed' (ou _partial),
    distinto das cargas normais, e nunca duplica PK (source_name, match_id).
    """
    events_root = dataset_root / "data" / "events"
    lineups_root = dataset_root / "data" / "lineups"

    # Seasons ja carregadas: id-range + team roster + labels.
    season_rows = conn.execute(
        """
        select competition_id, season_id, match_id,
               home_team_name, away_team_name,
               canonical_competition_key, season_label
        from raw.statsbomb_matches
        where source_name = %s and competition_id is not null and season_id is not null
        """,
        (SOURCE_NAME,),
    ).fetchall()
    season_spans: dict[tuple[int, int], tuple[int, int]] = {}
    season_team_rosters: dict[tuple[int, int], set[str]] = defaultdict(set)
    season_labels: dict[tuple[int, int], tuple[str | None, str | None]] = {}
    for row in season_rows:
        season = (int(row["competition_id"]), int(row["season_id"]))
        mid = as_int(row["match_id"])
        if mid is not None:
            lo, hi = season_spans.get(season, (mid, mid))
            season_spans[season] = (min(lo, mid), max(hi, mid))
        for name in (row.get("home_team_name"), row.get("away_team_name")):
            if name:
                season_team_rosters[season].add(name)
        season_labels.setdefault(
            season,
            (row.get("canonical_competition_key"), row.get("season_label")),
        )

    # IDs com metadata (presentes em raw.statsbomb_matches) e com WC (nao duplicar).
    loaded_ids = {int(row["match_id"]) for row in season_rows}
    wc_rows = conn.execute(
        """
        select distinct source_match_id
        from raw.wc_match_events
        where source_name = %s
        """,
        (SOURCE_NAME,),
    ).fetchall()
    wc_ids = {as_int(row["source_match_id"]) for row in wc_rows if as_int(row["source_match_id"]) is not None}

    # Orfaos = arquivos de events cujo match_id nao tem metadata nem WC.
    orphan_files = sorted(
        events_root.glob("*.json"),
        key=lambda p: as_int(p.stem) or 0,
    )

    match_rows: list[tuple[Any, ...]] = []
    promoted_match_ids: set[int] = set()
    partial_match_ids: set[int] = set()
    skipped_ids: list[int] = []

    for event_file in orphan_files:
        match_id = as_int(event_file.stem)
        if match_id is None or match_id in loaded_ids or match_id in wc_ids:
            continue
        summary.files_seen += 1
        file_hash = "skipped" if skip_hash else sha256_file(event_file)
        if not skip_hash:
            summary.files_hashed += 1
        relative_path_events = relative_dataset_path(dataset_root, event_file)

        try:
            events = read_json_file(event_file)
        except json.JSONDecodeError as exc:
            summary.parse_failed_files.append({"relative_path": relative_path_events, "message": str(exc)})
            skipped_ids.append(match_id)
            continue

        recon = reconstruct_orphan_match(events)
        if not recon["home_team_name"] or not recon["away_team_name"]:
            summary.orphans_unresolved += 1
            skipped_ids.append(match_id)
            continue

        team_names = {recon["home_team_name"], recon["away_team_name"]}
        comp_id, season_id, comp_key, season_label, reason = assign_orphan_competition(
            match_id,
            team_names,
            season_spans,
            season_team_rosters,
            season_labels,
        )

        if season_id is not None:
            status = "orphan_metadata_reconstructed"
            confidence = 1.0
            summary.orphans_reconstructed += 1
            promoted_match_ids.add(match_id)
        elif comp_id is not None:
            status = "orphan_metadata_reconstructed_partial"
            confidence = 0.5
            summary.orphans_partial_competition += 1
            partial_match_ids.add(match_id)
            # Sentinel para respeitar NOT NULL — season desconhecida e impossível
            # derivar do payload de events sem data.
            season_id = 0
            season_label = "unknown"
        else:
            summary.orphans_unresolved += 1
            skipped_ids.append(match_id)
            continue

        match_rows.append(
            (
                SOURCE_NAME,
                match_id,
                comp_id,
                season_id,
                comp_key,
                season_label,
                None,  # match_date: nao existe no payload, fica NULL
                None,  # kick_off
                recon["home_team_id"],
                recon["home_team_name"],
                recon["away_team_id"],
                recon["away_team_name"],
                recon["home_score"],
                recon["away_score"],
                None,  # match_status
                None,  # match_status_360
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,  # local_match_id: orfao, sem match canonico
                status,
                confidence,
                reason,
                Jsonb({"reconstructed_from": "events_payload", "method": "starting_xi_and_shot_goals"}),
                Jsonb(
                    {
                        "reconstructed": True,
                        "home_team_name": recon["home_team_name"],
                        "away_team_name": recon["away_team_name"],
                        "home_score": recon["home_score"],
                        "away_score": recon["away_score"],
                        "competition_id": comp_id,
                        "season_id": season_id,
                    }
                ),
            )
        )

        if not dry_run:
            # Manifest dos events como recovered_orphan.
            upsert_manifest(
                conn,
                relative_path=relative_path_events,
                detected_entity="events",
                provider_match_id=match_id,
                file_size_bytes=event_file.stat().st_size,
                sha256=file_hash,
                load_status="recovered_orphan",
            )

    if dry_run or not match_rows:
        return

    # 1. Inserir/reconstruir matches orfaos (upsert idempotente por PK).
    with conn.cursor() as cur:
        with cur.copy(
            """
            copy raw.statsbomb_matches (
              source_name, match_id, competition_id, season_id,
              canonical_competition_key, season_label, match_date, kick_off,
              home_team_id, home_team_name, away_team_id, away_team_name,
              home_score, away_score, match_status, match_status_360,
              competition_stage_id, competition_stage_name, match_week,
              stadium_id, stadium_name, referee_id, referee_name,
              local_match_id, identity_status, identity_confidence,
              identity_reason, metadata, payload
            ) from stdin
            """
        ) as copy:
            for row in match_rows:
                copy.write_row(row)

    promoted_all = promoted_match_ids | partial_match_ids

    # 2. Mover events da quarentena para raw.statsbomb_events.
    for match_id in sorted(promoted_all):
        quarantined = conn.execute(
            """
            select event_id, payload
            from raw.statsbomb_quarantine_events
            where source_name = %s and match_id = %s
            """,
            (SOURCE_NAME, match_id),
        ).fetchall()
        if not quarantined:
            continue
        event_rows: list[tuple[Any, ...]] = []
        for row in quarantined:
            payload = row["payload"] or {}
            extracted = extract_event_fields(payload)
            (
                event_id,
                event_index,
                period,
                event_timestamp,
                minute,
                second,
                event_type,
                possession,
                possession_team_id,
                possession_team_name,
                play_pattern,
                source_team_id,
                source_team_name,
                source_player_id,
                source_player_name,
            ) = extracted
            event_rows.append(
                (
                    SOURCE_NAME,
                    match_id,
                    event_id,
                    event_index,
                    period,
                    event_timestamp,
                    minute,
                    second,
                    event_type,
                    possession,
                    possession_team_id,
                    possession_team_name,
                    play_pattern,
                    source_team_id,
                    source_team_name,
                    source_player_id,
                    source_player_name,
                    None,  # local_match_id
                    None,  # local_team_id
                    None,  # local_player_id
                    "orphan_metadata_reconstructed",
                    "unresolved",
                    Jsonb(payload),
                )
            )
        conn.execute(
            "delete from raw.statsbomb_events where source_name = %s and match_id = %s",
            (SOURCE_NAME, match_id),
        )
        with conn.cursor() as cur:
            with cur.copy(
                """
                copy raw.statsbomb_events (
                  source_name, match_id, event_id, event_index, period,
                  event_timestamp, minute, second, event_type, possession,
                  possession_team_id, possession_team_name, play_pattern,
                  source_team_id, source_team_name, source_player_id,
                  source_player_name, local_match_id, local_team_id,
                  local_player_id, match_identity_status, player_identity_status,
                  payload
                ) from stdin
                """
            ) as copy:
                for row in event_rows:
                    copy.write_row(row)
                    summary.orphan_events_promoted += 1
        conn.execute(
            "delete from raw.statsbomb_quarantine_events where source_name = %s and match_id = %s",
            (SOURCE_NAME, match_id),
        )

    # 3. Mover lineups da quarentina para raw.statsbomb_lineups.
    for match_id in sorted(promoted_all):
        lineup_file = lineups_root / f"{match_id}.json"
        if not lineup_file.exists():
            continue
        rows = read_json_file(lineup_file)
        lineup_rows: list[tuple[Any, ...]] = []
        for team_entry in rows:
            source_team_id = as_int(team_entry.get("team_id"))
            source_team_name = team_entry.get("team_name")
            for player in team_entry.get("lineup") or []:
                lineup_rows.append(
                    (
                        SOURCE_NAME,
                        match_id,
                        source_team_id,
                        source_team_name,
                        as_int(player.get("player_id")),
                        player.get("player_name"),
                        as_int(player.get("jersey_number")),
                        (player.get("country") or {}).get("name"),
                        None,
                        None,
                        None,
                        "orphan_metadata_reconstructed",
                        "unresolved",
                        "no_linked_match_context",
                        0.0,
                        Jsonb({"team": team_entry, "player": player}),
                    )
                )
        conn.execute(
            "delete from raw.statsbomb_lineups where source_name = %s and match_id = %s",
            (SOURCE_NAME, match_id),
        )
        with conn.cursor() as cur:
            with cur.copy(
                """
                copy raw.statsbomb_lineups (
                  source_name, match_id, source_team_id, source_team_name,
                  source_player_id, source_player_name, jersey_number,
                  country_name, local_match_id, local_team_id, local_player_id,
                  match_identity_status, player_identity_status,
                  player_identity_reason, player_identity_confidence, payload
                ) from stdin
                """
            ) as copy:
                for row in lineup_rows:
                    copy.write_row(row)
                    summary.orphan_lineups_promoted += 1
        conn.execute(
            "delete from raw.statsbomb_quarantine_lineups where source_name = %s and match_id = %s",
            (SOURCE_NAME, match_id),
        )
        upsert_manifest(
            conn,
            relative_path=relative_dataset_path(dataset_root, lineup_file),
            detected_entity="lineups",
            provider_match_id=match_id,
            file_size_bytes=lineup_file.stat().st_size,
            sha256="skipped" if skip_hash else sha256_file(lineup_file),
            load_status="recovered_orphan",
        )


def write_summary_files(summary: Summary, json_path: Path, md_path: Path) -> None:
    payload = {
        "started_at": summary.started_at,
        "dataset_root": summary.dataset_root,
        "files_seen": summary.files_seen,
        "files_hashed": summary.files_hashed,
        "competitions_loaded": summary.competitions_loaded,
        "matches_loaded": summary.matches_loaded,
        "match_status_counts": dict(summary.match_status_counts or {}),
        "team_identity_counts": dict(summary.team_identity_counts or {}),
        "player_identity_counts": dict(summary.player_identity_counts or {}),
        "lineups_loaded": summary.lineups_loaded,
        "lineup_quarantined": summary.lineup_quarantined,
        "events_loaded": summary.events_loaded,
        "events_quarantined": summary.events_quarantined,
        "events_skipped_wc": summary.events_skipped_wc,
        "three_sixty_frames_loaded": summary.three_sixty_frames_loaded,
        "three_sixty_freeze_rows_loaded": summary.three_sixty_freeze_rows_loaded,
        "orphans_reconstructed": summary.orphans_reconstructed,
        "orphans_partial_competition": summary.orphans_partial_competition,
        "orphans_unresolved": summary.orphans_unresolved,
        "orphan_events_promoted": summary.orphan_events_promoted,
        "orphan_lineups_promoted": summary.orphan_lineups_promoted,
        "parse_failed_files": summary.parse_failed_files,
        "elapsed_seconds": round(summary.elapsed_seconds, 3),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# StatsBomb Open Data ingestion summary",
        "",
        f"- started_at: `{summary.started_at}`",
        f"- dataset_root: `{summary.dataset_root}`",
        f"- files_seen: `{summary.files_seen}`",
        f"- files_hashed: `{summary.files_hashed}`",
        f"- competitions_loaded: `{summary.competitions_loaded}`",
        f"- matches_loaded: `{summary.matches_loaded}`",
        f"- lineups_loaded: `{summary.lineups_loaded}`",
        f"- lineup_quarantined: `{summary.lineup_quarantined}`",
        f"- events_loaded: `{summary.events_loaded}`",
        f"- events_quarantined: `{summary.events_quarantined}`",
        f"- events_skipped_wc: `{summary.events_skipped_wc}`",
        f"- three_sixty_frames_loaded: `{summary.three_sixty_frames_loaded}`",
        f"- three_sixty_freeze_rows_loaded: `{summary.three_sixty_freeze_rows_loaded}`",
        f"- orphans_reconstructed: `{summary.orphans_reconstructed}`",
        f"- orphans_partial_competition: `{summary.orphans_partial_competition}`",
        f"- orphans_unresolved: `{summary.orphans_unresolved}`",
        f"- orphan_events_promoted: `{summary.orphan_events_promoted}`",
        f"- orphan_lineups_promoted: `{summary.orphan_lineups_promoted}`",
        f"- elapsed_seconds: `{round(summary.elapsed_seconds, 3)}`",
        "",
        "## Match identity status",
        "",
    ]
    for key, value in sorted((summary.match_status_counts or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Team identity status", ""])
    for key, value in sorted((summary.team_identity_counts or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Player identity status", ""])
    for key, value in sorted((summary.player_identity_counts or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    if summary.parse_failed_files:
        lines.extend(["", "## Parse failures", ""])
        for row in summary.parse_failed_files:
            lines.append(f"- `{row['relative_path']}`: `{row['message']}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> int:
    args = parse_args()
    start = perf_counter()
    dataset_root = Path(args.dataset_root).resolve()
    if not dataset_root.exists():
        raise RuntimeError(f"Dataset root not found: {dataset_root}")

    env_values = load_env_file(Path(args.env_file))
    dsn = resolve_pg_dsn(env_values)
    summary = Summary(started_at=utc_now().isoformat(), dataset_root=str(dataset_root))

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.autocommit = False
        state = preload_source_state(conn)
        if not args.dry_run:
            register_source(conn, dataset_root)
            conn.commit()

        if args.phase in {"all", "matches"}:
            state.existing_team_map, state.existing_player_map, _ = load_matches(
                conn,
                dataset_root,
                state,
                summary,
                max_match_files=args.max_match_files,
                skip_hash=args.skip_hash,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                conn.commit()

        if args.phase in {"all", "lineups"}:
            load_lineups(
                conn,
                dataset_root,
                state,
                summary,
                max_event_files=args.max_event_files,
                skip_hash=args.skip_hash,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                conn.commit()

        if args.phase in {"all", "events"}:
            load_events(
                conn,
                dataset_root,
                state,
                summary,
                max_event_files=args.max_event_files,
                skip_hash=args.skip_hash,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                conn.commit()

        if args.phase in {"all", "three-sixty"}:
            load_three_sixty(
                conn,
                dataset_root,
                summary,
                max_event_files=args.max_event_files,
                skip_hash=args.skip_hash,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                conn.commit()

        if args.phase in {"all", "recover-orphans"}:
            recover_orphans(
                conn,
                dataset_root,
                summary,
                skip_hash=args.skip_hash,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                conn.commit()

    summary.elapsed_seconds = perf_counter() - start
    write_summary_files(summary, Path(args.summary_json), Path(args.summary_md))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
