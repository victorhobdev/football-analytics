from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from _repo_root import resolve_repo_root
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
SUMMARY_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_sources_summary.json"
MIGRATION_PATH = ROOT / "db" / "migrations" / "20260424150000_external_coach_coupling.sql"
ALIAS_MIGRATION_PATH = ROOT / "db" / "migrations" / "20260425160000_coach_identity_alias_layer.sql"
REPORT_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_coupling_report.md"
SUMMARY_JSON_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_coupling_summary.json"
PROMOTABLE_CSV_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_coupling_promotable_candidates.csv"
CONFLICTS_CSV_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_coupling_conflicts.csv"
COVERAGE_CSV_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_coupling_coverage.csv"

WINDOW_START = date(2020, 1, 1)
PRODUCT_MAX_CUTOFF = date(2025, 12, 31)
INVALID_NAMES = {"", "not applicable", "unknown", "n a", "na", "none", "null", "sem nome"}


@dataclass(frozen=True)
class LocalTeam:
    team_id: int
    team_name: str
    norm: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class TeamAlias:
    team_id: int
    team_name: str
    alias_source: str
    external_team_id: str | None
    alias_name: str | None
    alias_norm: str
    confidence: float


@dataclass(frozen=True)
class CoachAliasIndex:
    by_identity_id: dict[int, int]
    by_source_person: dict[tuple[str, str], int]
    by_name: dict[str, list[int]]


@dataclass(frozen=True)
class MatchTeam:
    match_id: int
    team_id: int
    match_date: date
    competition_key: str | None
    season: int | None


@dataclass(frozen=True)
class ExistingAssignment:
    match_id: int
    team_id: int
    match_date: date
    coach_identity_id: int | None
    coach_name: str | None
    coach_norm: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acopla fontes externas de tecnicos em staging, sem promover dados para "
            "coach_tenure ou fact_coach_match_assignment."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--facts-path", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--apply-schema", action="store_true")
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--limit", type=int, default=0, help="Limite para smoke test. 0 = sem limite.")
    parser.add_argument(
        "--confirmation-team-id",
        type=int,
        default=1024,
        help="Time usado apenas na amostra de validacao do relatorio. 0 desativa.",
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
        key, value = line.split("=", 1)
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_setting(name: str, env_values: dict[str, str], default: str | None = None) -> str | None:
    return os.getenv(name) or env_values.get(name) or default


def resolve_pg_dsn(env_values: dict[str, str]) -> str:
    dsn = (
        resolve_setting("FOOTBALL_PG_DSN", env_values)
        or resolve_setting("DATABASE_URL", env_values)
        or "postgresql://football:football@localhost:5432/football_dw"
    )
    dsn = dsn.replace("postgresql+psycopg2://", "postgresql://")
    dsn = dsn.replace("postgres+psycopg2://", "postgresql://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    if "@postgres:" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres:", "@localhost:")
    if "@postgres/" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres/", "@localhost:5432/")
    return dsn


def product_cutoff(env_values: dict[str, str]) -> date:
    raw = resolve_setting("PRODUCT_DATA_CUTOFF", env_values, PRODUCT_MAX_CUTOFF.isoformat())
    try:
        cutoff = date.fromisoformat(str(raw))
    except ValueError:
        cutoff = PRODUCT_MAX_CUTOFF
    return min(cutoff, PRODUCT_MAX_CUTOFF)


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("external_coach_coupling_%Y%m%dT%H%M%SZ")


def normalize(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower().strip()
    return re.sub(r"\s+", " ", text)


def tokens(value: str) -> frozenset[str]:
    stop = {
        "club",
        "clube",
        "de",
        "da",
        "do",
        "dos",
        "das",
        "football",
        "futebol",
        "futbol",
        "fc",
        "cf",
        "ac",
        "sc",
        "ec",
        "afc",
        "association",
        "associacao",
        "regatas",
        "sociedade",
        "esporte",
        "sport",
        "sports",
        "team",
        "national",
        "selection",
        "selecao",
    }
    return frozenset(token for token in value.split() if token not in stop and len(token) > 2)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


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


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw_payload": value}
    return {}


def source_tier(source: str) -> str:
    if source == "wikidata_P286_team_to_person":
        return "strong"
    if source == "wikidata_P6087_person_to_team":
        return "medium"
    if source == "mediawiki_infobox_en":
        return "supporting"
    if source == "dbpedia_managerClub":
        return "weak"
    return "context"


def source_weight(source: str) -> float:
    return {
        "wikidata_P286_team_to_person": 0.95,
        "wikidata_P6087_person_to_team": 0.82,
        "mediawiki_infobox_en": 0.55,
        "dbpedia_managerClub": 0.35,
    }.get(source, 0.20)


def role_candidate(source_role: str | None, source: str, payload: dict[str, Any]) -> str:
    role = normalize(source_role)
    text = normalize(" ".join(str(payload.get(key, "")) for key in ("role", "position", "title", "raw_line")))
    merged = f"{role} {text}"
    if any(term in merged for term in ("assistant", "auxiliar", "assistente")):
        return "assistant_candidate"
    if any(term in merged for term in ("interim", "caretaker", "interino")):
        return "interim_head_coach_candidate"
    if role in {"head coach", "head_coach", "manager"}:
        return "head_coach_candidate"
    if source in {"wikidata_P286_team_to_person", "wikidata_P6087_person_to_team"} and role:
        return "head_coach_candidate"
    return "unknown_role"


def is_estimated_date(source: str, source_role: str | None, start: date | None, end: date | None) -> bool:
    if source.startswith("mediawiki") or source_role == "raw_text_candidate":
        return True
    if start and start.month == 1 and start.day == 1 and source != "wikidata_P286_team_to_person":
        return True
    if end and end.month == 12 and end.day == 31 and source.startswith("mediawiki"):
        return True
    return False


def candidate_key(source: str, external_person_id: str | None, coach_norm: str) -> str:
    if source.startswith("wikidata") and external_person_id:
        return f"wikidata:{external_person_id}"
    if source.startswith("dbpedia") and external_person_id:
        return f"dbpedia:{external_person_id}"
    if external_person_id:
        return f"{source}:{external_person_id}"
    return f"name:{coach_norm}"


def valid_coach_name(name: str | None) -> bool:
    norm = normalize(name)
    return norm not in INVALID_NAMES and len(norm) >= 3


def resolve_team(
    *,
    source: str,
    external_team_id: str | None,
    team_name: str | None,
    local_teams: list[LocalTeam],
    team_aliases: list[TeamAlias],
) -> tuple[LocalTeam | None, str, float]:
    norm = normalize(team_name)
    if not norm:
        return None, "missing_team_name", 0.0

    alias_candidates: list[TeamAlias] = []
    if external_team_id:
        alias_candidates.extend(
            alias
            for alias in team_aliases
            if alias.external_team_id == external_team_id
            and alias.alias_source in {source, source.split("_", 1)[0], "manual_verified_external_id", "wikidata"}
        )
    if not alias_candidates:
        alias_candidates.extend(alias for alias in team_aliases if alias.alias_norm and alias.alias_norm == norm)
    alias_candidates.sort(key=lambda alias: alias.confidence, reverse=True)
    if alias_candidates:
        top = alias_candidates[0]
        same_score = [alias for alias in alias_candidates if alias.confidence == top.confidence]
        if len({alias.team_id for alias in same_score}) == 1:
            local = next((team for team in local_teams if team.team_id == top.team_id), None)
            if local:
                method = "alias_external_id" if external_team_id and top.external_team_id == external_team_id else "alias_name"
                return local, method, round(top.confidence, 4)

    exact = [team for team in local_teams if team.norm == norm]
    if len(exact) == 1:
        return exact[0], "exact_name", 1.0

    ext_tokens = tokens(norm)
    scored: list[tuple[float, LocalTeam]] = []
    for team in local_teams:
        if not ext_tokens or not team.tokens:
            continue
        overlap = len(ext_tokens & team.tokens)
        if overlap == 0:
            continue
        token_score = overlap / max(len(ext_tokens), len(team.tokens))
        name_score = similarity(norm, team.norm)
        score = max(token_score, name_score)
        if score >= 0.78:
            scored.append((score, team))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
        return scored[0][1], "token_fuzzy_unique", round(scored[0][0], 3)

    return None, "unresolved_or_ambiguous", 0.0


def blocked_external_team_scope(team_name: str | None) -> str | None:
    norm = normalize(team_name)
    if not norm:
        return None
    if " season" in norm and re.search(r"\b(19|20)\d{2}\b", norm):
        return "season_entity_not_club"
    markers = {
        "academy",
        "youth",
        "reserves",
        "reserve",
        "women",
        "woman",
        "feminino",
        "femenino",
        "femeni",
        "ladies",
        "under",
    }
    norm_tokens = set(norm.split())
    if norm_tokens & markers:
        return "non_senior_team_entity"
    if re.search(r"\b(u|under)\s*(17|18|19|20|21|23)\b", norm):
        return "non_senior_team_entity"
    if re.search(r"\b(sub)\s*(17|18|19|20|21|23)\b", norm):
        return "non_senior_team_entity"
    if re.search(r"\b(b|ii|iii)\b", norm):
        return "non_senior_team_entity"
    return None


def is_preferred_rank(payload: dict[str, Any]) -> bool:
    return "PreferredRank" in str(payload.get("rank", ""))


def chunked(rows: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def read_facts_path(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    if SUMMARY_PATH.exists():
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        base_dir = Path(summary["base_dir"])
        return base_dir / "normalized" / "external_coach_facts.jsonl"
    base = ROOT / "data" / "external_coach_sources"
    runs = sorted([path for path in base.glob("external_coach_sources_*") if path.is_dir()])
    if not runs:
        raise RuntimeError("Nenhuma fonte externa encontrada em data/external_coach_sources.")
    return runs[-1] / "normalized" / "external_coach_facts.jsonl"


def read_facts(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
    return rows


def apply_schema(conn: psycopg.Connection[Any]) -> None:
    for migration_path in (MIGRATION_PATH, ALIAS_MIGRATION_PATH):
        sql = migration_path.read_text(encoding="utf-8")
        up_sql = sql.split("-- migrate:down", 1)[0].replace("-- migrate:up", "", 1)
        conn.execute(up_sql)


def load_local_teams(conn: psycopg.Connection[Any]) -> list[LocalTeam]:
    rows = conn.execute(
        "select team_id, team_name from mart.dim_team where team_name is not null"
    ).fetchall()
    return [
        LocalTeam(
            team_id=int(row["team_id"]),
            team_name=str(row["team_name"]),
            norm=normalize(str(row["team_name"])),
            tokens=tokens(normalize(str(row["team_name"]))),
        )
        for row in rows
    ]


def load_team_aliases(conn: psycopg.Connection[Any]) -> list[TeamAlias]:
    if conn.execute("select to_regclass('mart.team_identity_alias') as table_name").fetchone()["table_name"] is None:
        return []
    rows = conn.execute(
        """
        select
          a.team_id,
          t.team_name,
          a.alias_source,
          a.external_team_id,
          a.alias_name,
          a.confidence
        from mart.team_identity_alias a
        join mart.dim_team t
          on t.team_id = a.team_id
        where a.is_active
          and a.status = 'active'
        """
    ).fetchall()
    return [
        TeamAlias(
            team_id=int(row["team_id"]),
            team_name=str(row["team_name"]),
            alias_source=str(row["alias_source"]),
            external_team_id=str(row["external_team_id"]) if row.get("external_team_id") else None,
            alias_name=str(row["alias_name"]) if row.get("alias_name") else None,
            alias_norm=normalize(row.get("alias_name")),
            confidence=float(row["confidence"] or 0),
        )
        for row in rows
    ]


def load_match_teams(conn: psycopg.Connection[Any], cutoff: date) -> dict[int, list[MatchTeam]]:
    rows = conn.execute(
        """
        select match_id, competition_key, season, date_day, home_team_id as team_id
        from mart.fact_matches
        where date_day between %s and %s
        union all
        select match_id, competition_key, season, date_day, away_team_id as team_id
        from mart.fact_matches
        where date_day between %s and %s
        """,
        (WINDOW_START, cutoff, WINDOW_START, cutoff),
    ).fetchall()
    grouped: dict[int, list[MatchTeam]] = defaultdict(list)
    for row in rows:
        if row["team_id"] is None:
            continue
        season = row.get("season")
        grouped[int(row["team_id"])].append(
            MatchTeam(
                match_id=int(row["match_id"]),
                team_id=int(row["team_id"]),
                match_date=as_date(row["date_day"]) or WINDOW_START,
                competition_key=row.get("competition_key"),
                season=int(season) if season is not None and str(season).isdigit() else None,
            )
        )
    for team_matches in grouped.values():
        team_matches.sort(key=lambda item: item.match_date)
    return grouped


def load_existing_assignments(
    conn: psycopg.Connection[Any], cutoff: date
) -> tuple[set[tuple[int, int]], dict[int, list[ExistingAssignment]]]:
    rows = conn.execute(
        """
        select
          fcma.match_id,
          fcma.team_id,
          fcma.coach_identity_id,
          fm.date_day,
          coalesce(ci.display_name, ci.canonical_name) as coach_name
        from mart.fact_coach_match_assignment fcma
        join mart.fact_matches fm
          on fm.match_id = fcma.match_id
        left join mart.coach_identity ci
          on ci.coach_identity_id = fcma.coach_identity_id
        where fcma.is_public_eligible = true
          and fm.date_day between %s and %s
        """,
        (WINDOW_START, cutoff),
    ).fetchall()
    keys: set[tuple[int, int]] = set()
    by_team: dict[int, list[ExistingAssignment]] = defaultdict(list)
    for row in rows:
        if row["match_id"] is None or row["team_id"] is None:
            continue
        key = (int(row["match_id"]), int(row["team_id"]))
        keys.add(key)
        match_date = as_date(row["date_day"])
        if not match_date:
            continue
        by_team[key[1]].append(
            ExistingAssignment(
                match_id=key[0],
                team_id=key[1],
                match_date=match_date,
                coach_identity_id=int(row["coach_identity_id"]) if row.get("coach_identity_id") else None,
                coach_name=row.get("coach_name"),
                coach_norm=normalize(row.get("coach_name")),
            )
        )
    return keys, by_team


def load_identity_refs(conn: psycopg.Connection[Any]) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        """
        select source, external_person_id, coach_identity_id
        from mart.coach_identity_source_ref
        """
    ).fetchall()
    return {
        (str(row["source"]), str(row["external_person_id"])): int(row["coach_identity_id"])
        for row in rows
        if row.get("external_person_id")
    }


def load_coach_alias_index(conn: psycopg.Connection[Any]) -> CoachAliasIndex:
    if conn.execute("select to_regclass('mart.coach_identity_alias') as table_name").fetchone()["table_name"] is None:
        return CoachAliasIndex(by_identity_id={}, by_source_person={}, by_name={})
    rows = conn.execute(
        """
        select
          canonical_coach_identity_id,
          alias_coach_identity_id,
          alias_source,
          external_person_id,
          alias_name,
          confidence
        from mart.coach_identity_alias
        where is_active
          and status = 'active'
        order by confidence desc, coach_identity_alias_id desc
        """
    ).fetchall()
    by_identity_id: dict[int, int] = {}
    by_source_person: dict[tuple[str, str], int] = {}
    by_name: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        canonical_id = int(row["canonical_coach_identity_id"])
        if row.get("alias_coach_identity_id"):
            by_identity_id[int(row["alias_coach_identity_id"])] = canonical_id
        if row.get("external_person_id"):
            by_source_person[(str(row["alias_source"]), str(row["external_person_id"]))] = canonical_id
        alias_norm = normalize(row.get("alias_name"))
        if alias_norm and canonical_id not in by_name[alias_norm]:
            by_name[alias_norm].append(canonical_id)
    return CoachAliasIndex(
        by_identity_id=by_identity_id,
        by_source_person=by_source_person,
        by_name=dict(by_name),
    )


def canonicalize_identity_id(identity_id: int | None, aliases: CoachAliasIndex) -> int | None:
    if identity_id is None:
        return None
    return aliases.by_identity_id.get(identity_id, identity_id)


def load_canonical_name_index(
    conn: psycopg.Connection[Any], aliases: CoachAliasIndex
) -> dict[str, list[int]]:
    rows = conn.execute(
        """
        select coach_identity_id, coalesce(display_name, canonical_name) as coach_name
        from mart.coach_identity
        where coalesce(display_name, canonical_name) is not null
        """
    ).fetchall()
    index: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        norm = normalize(row.get("coach_name"))
        if norm and norm not in INVALID_NAMES:
            identity_id = canonicalize_identity_id(int(row["coach_identity_id"]), aliases)
            if identity_id is not None and identity_id not in index[norm]:
                index[norm].append(identity_id)
    for norm, identity_ids in aliases.by_name.items():
        if norm and norm not in INVALID_NAMES:
            for identity_id in identity_ids:
                if identity_id not in index[norm]:
                    index[norm].append(identity_id)
    return index


def upsert_raw_facts(
    conn: psycopg.Connection[Any],
    facts: list[dict[str, Any]],
    run_id: str,
    batch_size: int,
) -> None:
    sql = """
        insert into raw.external_coach_source_facts (
          source,
          source_record_id,
          source_url,
          external_person_id,
          external_team_id,
          coach_name,
          team_name,
          source_role,
          start_date_original,
          end_date_original,
          source_confidence,
          payload,
          ingested_run,
          updated_at
        )
        values (
          %(source)s,
          %(source_record_id)s,
          %(source_url)s,
          %(external_person_id)s,
          %(external_team_id)s,
          %(coach_name)s,
          %(team_name)s,
          %(source_role)s,
          %(start_date_original)s,
          %(end_date_original)s,
          %(source_confidence)s,
          %(payload)s,
          %(ingested_run)s,
          now()
        )
        on conflict (source, source_record_id) do update set
          source_url = excluded.source_url,
          external_person_id = excluded.external_person_id,
          external_team_id = excluded.external_team_id,
          coach_name = excluded.coach_name,
          team_name = excluded.team_name,
          source_role = excluded.source_role,
          start_date_original = excluded.start_date_original,
          end_date_original = excluded.end_date_original,
          source_confidence = excluded.source_confidence,
          payload = excluded.payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
    """
    rows: list[dict[str, Any]] = []
    for fact in facts:
        rows.append(
            {
                "source": fact.get("source"),
                "source_record_id": fact.get("source_record_id"),
                "source_url": fact.get("source_url"),
                "external_person_id": fact.get("coach_external_id"),
                "external_team_id": fact.get("team_external_id"),
                "coach_name": fact.get("coach_name"),
                "team_name": fact.get("team_name"),
                "source_role": fact.get("role"),
                "start_date_original": as_date(fact.get("start_date")),
                "end_date_original": as_date(fact.get("end_date")),
                "source_confidence": as_float(fact.get("confidence")),
                "payload": Jsonb(clean_payload(fact.get("payload"))),
                "ingested_run": run_id,
            }
        )
    with conn.cursor() as cursor:
        for batch in chunked(rows, batch_size):
            cursor.executemany(sql, batch)


def resolve_identity(
    *,
    source: str,
    external_person_id: str | None,
    coach_norm: str,
    source_refs: dict[tuple[str, str], int],
    canonical_name_index: dict[str, list[int]],
    aliases: CoachAliasIndex,
    same_coach_identity_counts: Counter[int],
) -> tuple[int | None, str | None, float]:
    if external_person_id:
        for ref_source in (source, source.split("_", 1)[0], "wikidata" if source.startswith("wikidata") else source):
            direct = aliases.by_source_person.get((ref_source, external_person_id))
            if direct:
                return direct, "coach_alias_external_id", 1.0
        direct = source_refs.get((source, external_person_id))
        if direct:
            return canonicalize_identity_id(direct, aliases), "source_ref_exact", 1.0
        if source.startswith("wikidata"):
            for ref_source in ("wikidata_P286_team_to_person", "wikidata_P6087_person_to_team", "wikidata"):
                direct = source_refs.get((ref_source, external_person_id))
                if direct:
                    return canonicalize_identity_id(direct, aliases), "wikidata_source_ref", 0.98

    if same_coach_identity_counts:
        identity_id, count = same_coach_identity_counts.most_common(1)[0]
        if count > 0:
            return canonicalize_identity_id(identity_id, aliases), "same_team_assignment_name", 0.92

    exact_name = canonical_name_index.get(coach_norm, [])
    if len(exact_name) == 1:
        return canonicalize_identity_id(exact_name[0], aliases), "global_exact_name_unique", 0.86

    alias_name = aliases.by_name.get(coach_norm, [])
    if len(alias_name) == 1:
        return alias_name[0], "coach_alias_name", 0.88

    return None, None, 0.0


def classify_fact(
    fact: dict[str, Any],
    local_teams: list[LocalTeam],
    team_aliases: list[TeamAlias],
    match_teams_by_team: dict[int, list[MatchTeam]],
    existing_keys: set[tuple[int, int]],
    assignments_by_team: dict[int, list[ExistingAssignment]],
    source_refs: dict[tuple[str, str], int],
    canonical_name_index: dict[str, list[int]],
    aliases: CoachAliasIndex,
    cutoff: date,
    run_id: str,
) -> dict[str, Any]:
    source = str(fact.get("source") or "")
    source_record_id = str(fact.get("source_record_id") or "")
    payload = clean_payload(fact.get("payload"))
    coach_name = fact.get("coach_name")
    coach_norm = normalize(coach_name)
    team_scope_block = blocked_external_team_scope(fact.get("team_name"))
    team, team_method, team_score = resolve_team(
        source=source,
        external_team_id=fact.get("team_external_id"),
        team_name=fact.get("team_name"),
        local_teams=local_teams,
        team_aliases=team_aliases,
    )
    start_original = as_date(fact.get("start_date"))
    end_original = as_date(fact.get("end_date"))
    role = role_candidate(str(fact.get("role") or ""), source, payload)
    tier = source_tier(source)
    is_estimated = is_estimated_date(source, fact.get("role"), start_original, end_original)
    source_confidence = as_float(fact.get("confidence")) or 0.0

    result: dict[str, Any] = {
        "source": source,
        "source_record_id": source_record_id,
        "source_url": fact.get("source_url"),
        "external_person_id": fact.get("coach_external_id"),
        "external_team_id": fact.get("team_external_id"),
        "team_id": team.team_id if team else None,
        "local_team_name": team.team_name if team else None,
        "team_match_method": team_method,
        "team_match_score": team_score,
        "coach_identity_id": None,
        "identity_match_method": None,
        "identity_match_score": 0.0,
        "candidate_coach_key": candidate_key(source, fact.get("coach_external_id"), coach_norm),
        "coach_name": coach_name,
        "coach_name_normalized": coach_norm,
        "team_name": fact.get("team_name"),
        "source_role": fact.get("role"),
        "role_candidate": role,
        "start_date_original": start_original,
        "end_date_original": end_original,
        "clipped_start_date": None,
        "clipped_end_date": None,
        "is_date_estimated": is_estimated,
        "source_tier": tier,
        "source_confidence": source_confidence,
        "candidate_confidence": 0.0,
        "canonical_missing_matches_covered": 0,
        "canonical_assigned_matches_covered": 0,
        "existing_same_coach_overlap_matches": 0,
        "best_existing_coach_similarity": 0.0,
        "classification": "review_needed",
        "block_reason": None,
        "payload": Jsonb(payload),
        "ingested_run": run_id,
    }

    if not valid_coach_name(coach_name):
        result.update(classification="blocked_invalid_name", block_reason="invalid_or_missing_coach_name")
        return result
    if team_scope_block:
        result.update(classification="blocked_non_senior_or_season_team", block_reason=team_scope_block)
        return result
    if not team:
        result.update(classification="blocked_unresolved_team", block_reason="team_not_resolved")
        return result
    if end_original and start_original and end_original < start_original:
        result.update(classification="blocked_invalid_interval", block_reason="end_before_start")
        return result
    if role == "assistant_candidate":
        result.update(classification="blocked_assistant", block_reason="assistant_role_not_promotable")
        return result
    if role == "unknown_role":
        result.update(classification="blocked_unknown_role", block_reason="unknown_role_not_promotable")
        return result
    if not start_original:
        result.update(classification="review_needed", block_reason="missing_start_date")
        return result

    clipped_start = max(start_original, WINDOW_START)
    clipped_end = min(end_original or cutoff, cutoff)
    result["clipped_start_date"] = clipped_start
    result["clipped_end_date"] = clipped_end

    if clipped_end < WINDOW_START or clipped_start > cutoff or clipped_end < clipped_start:
        result["clipped_start_date"] = None
        result["clipped_end_date"] = None
        result.update(classification="blocked_outside_window", block_reason="no_overlap_with_product_window")
        return result

    local_matches = [
        match for match in match_teams_by_team.get(team.team_id, []) if clipped_start <= match.match_date <= clipped_end
    ]
    missing = [match for match in local_matches if (match.match_id, team.team_id) not in existing_keys]
    assigned = [match for match in local_matches if (match.match_id, team.team_id) in existing_keys]
    result["canonical_missing_matches_covered"] = len(missing)
    result["canonical_assigned_matches_covered"] = len(assigned)

    preliminary_identity_id, _, _ = resolve_identity(
        source=source,
        external_person_id=fact.get("coach_external_id"),
        coach_norm=coach_norm,
        source_refs=source_refs,
        canonical_name_index=canonical_name_index,
        aliases=aliases,
        same_coach_identity_counts=Counter(),
    )

    same_coach = 0
    best_similarity = 0.0
    same_coach_identity_counts: Counter[int] = Counter()
    for assignment in assignments_by_team.get(team.team_id, []):
        if not (clipped_start <= assignment.match_date <= clipped_end):
            continue
        assignment_identity_id = canonicalize_identity_id(assignment.coach_identity_id, aliases)
        score = similarity(coach_norm, assignment.coach_norm)
        best_similarity = max(best_similarity, score)
        if preliminary_identity_id is not None and assignment_identity_id == preliminary_identity_id:
            same_coach += 1
            same_coach_identity_counts[preliminary_identity_id] += 1
            best_similarity = max(best_similarity, 1.0)
        elif score >= 0.86:
            same_coach += 1
            if assignment_identity_id:
                same_coach_identity_counts[assignment_identity_id] += 1
    result["existing_same_coach_overlap_matches"] = same_coach
    result["best_existing_coach_similarity"] = round(best_similarity, 4)

    identity_id, identity_method, identity_score = resolve_identity(
        source=source,
        external_person_id=fact.get("coach_external_id"),
        coach_norm=coach_norm,
        source_refs=source_refs,
        canonical_name_index=canonical_name_index,
        aliases=aliases,
        same_coach_identity_counts=same_coach_identity_counts,
    )
    result["coach_identity_id"] = identity_id
    result["identity_match_method"] = identity_method
    result["identity_match_score"] = identity_score

    date_weight = 0.70 if is_estimated else 1.0
    if end_original is None:
        date_weight *= 0.85
    role_weight = 0.90 if role == "interim_head_coach_candidate" else 1.0
    coverage_weight = min(len(missing) / 10, 1.0)
    confidence = source_weight(source) * team_score * role_weight * date_weight * (0.75 + 0.25 * coverage_weight)
    result["candidate_confidence"] = round(confidence, 4)

    if not local_matches:
        result.update(classification="low_value_context", block_reason="no_local_matches_in_interval")
    elif not missing and (assigned or same_coach):
        result.update(classification="likely_duplicate", block_reason="interval_already_covered_publicly")
    elif not missing:
        result.update(classification="low_value_context", block_reason="no_missing_public_match_team_covered")
    elif end_original is None and same_coach == 0 and not is_preferred_rank(payload):
        result.update(
            classification="review_needed",
            block_reason="open_ended_without_current_confirmation",
        )
    elif tier == "strong" and team_score >= 0.90 and confidence >= 0.65 and not is_estimated:
        result.update(classification="promotable_candidate", block_reason=None)
    else:
        result.update(classification="review_needed", block_reason="needs_human_or_second_source_before_public_promotion")
    return result


def reset_staging(conn: psycopg.Connection[Any]) -> None:
    conn.execute("delete from mart.stg_external_coach_assignment_candidates")
    conn.execute("delete from mart.stg_external_coach_candidate_resolution")


def upsert_resolutions(
    conn: psycopg.Connection[Any], rows: list[dict[str, Any]], batch_size: int
) -> None:
    sql = """
        insert into mart.stg_external_coach_candidate_resolution (
          source,
          source_record_id,
          source_url,
          external_person_id,
          external_team_id,
          team_id,
          local_team_name,
          team_match_method,
          team_match_score,
          coach_identity_id,
          identity_match_method,
          identity_match_score,
          candidate_coach_key,
          coach_name,
          coach_name_normalized,
          team_name,
          source_role,
          role_candidate,
          start_date_original,
          end_date_original,
          clipped_start_date,
          clipped_end_date,
          is_date_estimated,
          source_tier,
          source_confidence,
          candidate_confidence,
          canonical_missing_matches_covered,
          canonical_assigned_matches_covered,
          existing_same_coach_overlap_matches,
          best_existing_coach_similarity,
          classification,
          block_reason,
          payload,
          ingested_run,
          updated_at
        )
        values (
          %(source)s,
          %(source_record_id)s,
          %(source_url)s,
          %(external_person_id)s,
          %(external_team_id)s,
          %(team_id)s,
          %(local_team_name)s,
          %(team_match_method)s,
          %(team_match_score)s,
          %(coach_identity_id)s,
          %(identity_match_method)s,
          %(identity_match_score)s,
          %(candidate_coach_key)s,
          %(coach_name)s,
          %(coach_name_normalized)s,
          %(team_name)s,
          %(source_role)s,
          %(role_candidate)s,
          %(start_date_original)s,
          %(end_date_original)s,
          %(clipped_start_date)s,
          %(clipped_end_date)s,
          %(is_date_estimated)s,
          %(source_tier)s,
          %(source_confidence)s,
          %(candidate_confidence)s,
          %(canonical_missing_matches_covered)s,
          %(canonical_assigned_matches_covered)s,
          %(existing_same_coach_overlap_matches)s,
          %(best_existing_coach_similarity)s,
          %(classification)s,
          %(block_reason)s,
          %(payload)s,
          %(ingested_run)s,
          now()
        )
        on conflict (source, source_record_id) do update set
          source_url = excluded.source_url,
          external_person_id = excluded.external_person_id,
          external_team_id = excluded.external_team_id,
          team_id = excluded.team_id,
          local_team_name = excluded.local_team_name,
          team_match_method = excluded.team_match_method,
          team_match_score = excluded.team_match_score,
          coach_identity_id = excluded.coach_identity_id,
          identity_match_method = excluded.identity_match_method,
          identity_match_score = excluded.identity_match_score,
          candidate_coach_key = excluded.candidate_coach_key,
          coach_name = excluded.coach_name,
          coach_name_normalized = excluded.coach_name_normalized,
          team_name = excluded.team_name,
          source_role = excluded.source_role,
          role_candidate = excluded.role_candidate,
          start_date_original = excluded.start_date_original,
          end_date_original = excluded.end_date_original,
          clipped_start_date = excluded.clipped_start_date,
          clipped_end_date = excluded.clipped_end_date,
          is_date_estimated = excluded.is_date_estimated,
          source_tier = excluded.source_tier,
          source_confidence = excluded.source_confidence,
          candidate_confidence = excluded.candidate_confidence,
          canonical_missing_matches_covered = excluded.canonical_missing_matches_covered,
          canonical_assigned_matches_covered = excluded.canonical_assigned_matches_covered,
          existing_same_coach_overlap_matches = excluded.existing_same_coach_overlap_matches,
          best_existing_coach_similarity = excluded.best_existing_coach_similarity,
          classification = excluded.classification,
          block_reason = excluded.block_reason,
          payload = excluded.payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
    """
    with conn.cursor() as cursor:
        for batch in chunked(rows, batch_size):
            cursor.executemany(sql, batch)


def build_assignment_candidates(
    resolutions: list[dict[str, Any]],
    match_teams_by_team: dict[int, list[MatchTeam]],
    existing_keys: set[tuple[int, int]],
    run_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    allowed = {"promotable_candidate", "review_needed"}
    for resolution in resolutions:
        if resolution["classification"] not in allowed:
            continue
        if not resolution.get("team_id") or not resolution.get("clipped_start_date") or not resolution.get("clipped_end_date"):
            continue
        start = resolution["clipped_start_date"]
        end = resolution["clipped_end_date"]
        team_id = int(resolution["team_id"])
        status = "promotable" if resolution["classification"] == "promotable_candidate" else "review_needed"
        method = "single_head_coach_tenure"
        if resolution["role_candidate"] == "interim_head_coach_candidate":
            method = "interim_head_coach_tenure"
        elif status != "promotable":
            method = "inferred_low_confidence"

        for match in match_teams_by_team.get(team_id, []):
            if not (start <= match.match_date <= end):
                continue
            if (match.match_id, team_id) in existing_keys:
                continue
            rows.append(
                {
                    "source": resolution["source"],
                    "source_record_id": resolution["source_record_id"],
                    "match_id": match.match_id,
                    "team_id": team_id,
                    "source_url": resolution.get("source_url"),
                    "external_person_id": resolution.get("external_person_id"),
                    "coach_identity_id": resolution.get("coach_identity_id"),
                    "candidate_coach_key": resolution.get("candidate_coach_key"),
                    "coach_name": resolution.get("coach_name"),
                    "role_candidate": resolution.get("role_candidate"),
                    "assignment_method": method,
                    "assignment_confidence": resolution.get("candidate_confidence"),
                    "match_date": match.match_date,
                    "competition_key": match.competition_key,
                    "season": match.season,
                    "is_existing_public_assignment": False,
                    "existing_coach_identity_id": None,
                    "existing_coach_name": None,
                    "conflict_candidate_count": 0,
                    "promotion_status": status,
                    "block_reason": resolution.get("block_reason") if status != "promotable" else None,
                    "payload": Jsonb(
                        {
                            "source_tier": resolution.get("source_tier"),
                            "classification": resolution.get("classification"),
                            "team_match_method": resolution.get("team_match_method"),
                            "identity_match_method": resolution.get("identity_match_method"),
                        }
                    ),
                    "ingested_run": run_id,
                }
            )
    return rows


def upsert_assignment_candidates(
    conn: psycopg.Connection[Any], rows: list[dict[str, Any]], batch_size: int
) -> None:
    sql = """
        insert into mart.stg_external_coach_assignment_candidates (
          source,
          source_record_id,
          match_id,
          team_id,
          source_url,
          external_person_id,
          coach_identity_id,
          candidate_coach_key,
          coach_name,
          role_candidate,
          assignment_method,
          assignment_confidence,
          match_date,
          competition_key,
          season,
          is_existing_public_assignment,
          existing_coach_identity_id,
          existing_coach_name,
          conflict_candidate_count,
          promotion_status,
          block_reason,
          payload,
          ingested_run,
          updated_at
        )
        values (
          %(source)s,
          %(source_record_id)s,
          %(match_id)s,
          %(team_id)s,
          %(source_url)s,
          %(external_person_id)s,
          %(coach_identity_id)s,
          %(candidate_coach_key)s,
          %(coach_name)s,
          %(role_candidate)s,
          %(assignment_method)s,
          %(assignment_confidence)s,
          %(match_date)s,
          %(competition_key)s,
          %(season)s,
          %(is_existing_public_assignment)s,
          %(existing_coach_identity_id)s,
          %(existing_coach_name)s,
          %(conflict_candidate_count)s,
          %(promotion_status)s,
          %(block_reason)s,
          %(payload)s,
          %(ingested_run)s,
          now()
        )
        on conflict (source, source_record_id, match_id, team_id) do update set
          source_url = excluded.source_url,
          external_person_id = excluded.external_person_id,
          coach_identity_id = excluded.coach_identity_id,
          candidate_coach_key = excluded.candidate_coach_key,
          coach_name = excluded.coach_name,
          role_candidate = excluded.role_candidate,
          assignment_method = excluded.assignment_method,
          assignment_confidence = excluded.assignment_confidence,
          match_date = excluded.match_date,
          competition_key = excluded.competition_key,
          season = excluded.season,
          is_existing_public_assignment = excluded.is_existing_public_assignment,
          existing_coach_identity_id = excluded.existing_coach_identity_id,
          existing_coach_name = excluded.existing_coach_name,
          conflict_candidate_count = excluded.conflict_candidate_count,
          promotion_status = excluded.promotion_status,
          block_reason = excluded.block_reason,
          payload = excluded.payload,
          ingested_run = excluded.ingested_run,
          updated_at = now()
    """
    with conn.cursor() as cursor:
        for batch in chunked(rows, batch_size):
            cursor.executemany(sql, batch)


def mark_conflicts(conn: psycopg.Connection[Any]) -> None:
    conn.execute(
        """
        with conflicts as (
          select
            match_id,
            team_id,
            count(distinct candidate_coach_key) as candidate_count
          from mart.stg_external_coach_assignment_candidates
          where promotion_status = 'promotable'
          group by match_id, team_id
          having count(distinct candidate_coach_key) > 1
        )
        update mart.stg_external_coach_assignment_candidates c
        set
          promotion_status = 'blocked_conflict',
          block_reason = 'multiple_promotable_coaches_for_match_team',
          conflict_candidate_count = conflicts.candidate_count,
          updated_at = now()
        from conflicts
        where c.match_id = conflicts.match_id
          and c.team_id = conflicts.team_id
          and c.promotion_status = 'promotable'
        """
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_count_map(conn: psycopg.Connection[Any], sql: str) -> dict[str, int]:
    return {str(row["key"]): int(row["n"]) for row in conn.execute(sql).fetchall()}


def build_summary(
    conn: psycopg.Connection[Any], run_id: str, cutoff: date, confirmation_team_id: int
) -> dict[str, Any]:
    coverage = conn.execute(
        """
        with match_teams as (
          select match_id, home_team_id as team_id
          from mart.fact_matches
          where date_day between %s and %s
          union all
          select match_id, away_team_id as team_id
          from mart.fact_matches
          where date_day between %s and %s
        ),
        public_assignments as (
          select f.match_id, f.team_id
          from mart.fact_coach_match_assignment f
          join mart.fact_matches m on m.match_id = f.match_id
          where f.is_public_eligible = true
            and m.date_day between %s and %s
        ),
        promotable as (
          select distinct match_id, team_id
          from mart.stg_external_coach_assignment_candidates
          where promotion_status = 'promotable'
        ),
        review_needed as (
          select distinct match_id, team_id
          from mart.stg_external_coach_assignment_candidates
          where promotion_status = 'review_needed'
        )
        select
          (select count(*) from match_teams) as total_match_teams,
          (select count(*) from public_assignments) as public_assigned,
          (select count(*) from promotable) as promotable_match_teams,
          (select count(*) from review_needed) as review_needed_match_teams
        """,
        (WINDOW_START, cutoff, WINDOW_START, cutoff, WINDOW_START, cutoff),
    ).fetchone()

    classification_counts = fetch_count_map(
        conn,
        """
        select classification as key, count(*) as n
        from mart.stg_external_coach_candidate_resolution
        group by classification
        """,
    )
    source_counts = fetch_count_map(
        conn,
        """
        select source as key, count(*) as n
        from raw.external_coach_source_facts
        group by source
        """,
    )
    assignment_status_counts = fetch_count_map(
        conn,
        """
        select promotion_status as key, count(*) as n
        from mart.stg_external_coach_assignment_candidates
        group by promotion_status
        """,
    )
    gate_counts = {
        "outside_window_assignment_candidates": int(
            conn.execute(
                """
                select count(*) as n
                from mart.stg_external_coach_assignment_candidates
                where match_date < %s or match_date > %s
                """,
                (WINDOW_START, cutoff),
            ).fetchone()["n"]
        ),
        "would_overwrite_public_assignment": int(
            conn.execute(
                """
                select count(*) as n
                from mart.stg_external_coach_assignment_candidates c
                join mart.fact_coach_match_assignment f
                  on f.match_id = c.match_id
                 and f.team_id = c.team_id
                where f.is_public_eligible = true
                  and c.promotion_status in ('promotable', 'review_needed')
                """
            ).fetchone()["n"]
        ),
        "assistant_promotable_candidates": int(
            conn.execute(
                """
                select count(*) as n
                from mart.stg_external_coach_candidate_resolution
                where classification = 'promotable_candidate'
                  and role_candidate in ('assistant_candidate', 'unknown_role')
                """
            ).fetchone()["n"]
        ),
        "invalid_promotable_names": int(
            conn.execute(
                """
                select count(*) as n
                from mart.stg_external_coach_candidate_resolution
                where classification = 'promotable_candidate'
                  and (
                    coach_name_normalized is null
                    or coach_name_normalized in ('not applicable', 'unknown', 'n a', 'na', 'none', 'null')
                  )
                """
            ).fetchone()["n"]
        ),
    }

    top_teams = conn.execute(
        """
        select
          c.team_id,
          coalesce(d.team_name, c.team_id::text) as team_name,
          count(distinct (c.match_id, c.team_id)) as promotable_match_teams
        from mart.stg_external_coach_assignment_candidates c
        left join mart.dim_team d on d.team_id = c.team_id
        where c.promotion_status = 'promotable'
        group by c.team_id, d.team_name
        order by promotable_match_teams desc, team_name
        limit 30
        """
    ).fetchall()

    top_sources = conn.execute(
        """
        select
          source,
          count(*) as candidates,
          sum(canonical_missing_matches_covered) as missing_match_team_sum
        from mart.stg_external_coach_candidate_resolution
        where classification = 'promotable_candidate'
        group by source
        order by missing_match_team_sum desc nulls last, candidates desc
        """
    ).fetchall()

    confirmation_sample = conn.execute(
        """
        select
          source,
          local_team_name,
          coach_name,
          clipped_start_date,
          clipped_end_date,
          canonical_missing_matches_covered,
          candidate_confidence,
          classification
        from mart.stg_external_coach_candidate_resolution
        where (%s <> 0 and team_id = %s)
           or (%s = 0 and coach_name_normalized in (
             'jorge jesus',
             'domenec torrent',
             'rogerio ceni',
             'renato gaucho',
             'paulo sousa',
             'dorival junior',
             'vitor pereira',
             'jorge sampaoli',
             'tite',
             'filipe luis'
           ))
        order by
          case
            when classification = 'promotable_candidate' then 0
            when classification = 'review_needed' and canonical_missing_matches_covered > 0 then 1
            when classification = 'likely_duplicate' then 2
            when classification = 'low_value_context' then 3
            else 4
          end,
          canonical_missing_matches_covered desc,
          clipped_start_date nulls last,
          coach_name
        limit 80
        """,
        (confirmation_team_id, confirmation_team_id, confirmation_team_id),
    ).fetchall()

    return {
        "run_id": run_id,
        "window_start": WINDOW_START.isoformat(),
        "window_end": cutoff.isoformat(),
        "coverage": dict(coverage),
        "classification_counts": classification_counts,
        "source_counts": source_counts,
        "assignment_status_counts": assignment_status_counts,
        "gate_counts": gate_counts,
        "top_teams_by_promotable_match_teams": [dict(row) for row in top_teams],
        "top_promotable_sources": [dict(row) for row in top_sources],
        "confirmation_sample": [dict(row) for row in confirmation_sample],
    }


def write_reports(conn: psycopg.Connection[Any], summary: dict[str, Any]) -> None:
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    promotable_rows = conn.execute(
        """
        select
          source,
          source_record_id,
          local_team_name,
          coach_name,
          clipped_start_date,
          clipped_end_date,
          canonical_missing_matches_covered,
          canonical_assigned_matches_covered,
          candidate_confidence,
          team_match_method,
          identity_match_method,
          source_url
        from mart.stg_external_coach_candidate_resolution
        where classification = 'promotable_candidate'
        order by canonical_missing_matches_covered desc, candidate_confidence desc
        limit 50000
        """
    ).fetchall()
    write_csv(
        PROMOTABLE_CSV_PATH,
        [dict(row) for row in promotable_rows],
        [
            "source",
            "source_record_id",
            "local_team_name",
            "coach_name",
            "clipped_start_date",
            "clipped_end_date",
            "canonical_missing_matches_covered",
            "canonical_assigned_matches_covered",
            "candidate_confidence",
            "team_match_method",
            "identity_match_method",
            "source_url",
        ],
    )

    conflict_rows = conn.execute(
        """
        select
          match_id,
          team_id,
          competition_key,
          season,
          match_date,
          conflict_candidate_count,
          string_agg(distinct coach_name, ' | ' order by coach_name) as coach_names,
          string_agg(distinct source, ' | ' order by source) as sources
        from mart.stg_external_coach_assignment_candidates
        where promotion_status = 'blocked_conflict'
        group by match_id, team_id, competition_key, season, match_date, conflict_candidate_count
        order by match_date, match_id, team_id
        limit 50000
        """
    ).fetchall()
    write_csv(
        CONFLICTS_CSV_PATH,
        [dict(row) for row in conflict_rows],
        [
            "match_id",
            "team_id",
            "competition_key",
            "season",
            "match_date",
            "conflict_candidate_count",
            "coach_names",
            "sources",
        ],
    )

    coverage_rows = conn.execute(
        """
        select
          competition_key,
          season,
          team_id,
          count(distinct (match_id, team_id)) filter (where promotion_status = 'promotable') as promotable_match_teams,
          count(distinct (match_id, team_id)) filter (where promotion_status = 'review_needed') as review_needed_match_teams,
          count(distinct (match_id, team_id)) filter (where promotion_status = 'blocked_conflict') as blocked_conflict_match_teams
        from mart.stg_external_coach_assignment_candidates
        group by competition_key, season, team_id
        order by promotable_match_teams desc nulls last, review_needed_match_teams desc nulls last
        """
    ).fetchall()
    write_csv(
        COVERAGE_CSV_PATH,
        [dict(row) for row in coverage_rows],
        [
            "competition_key",
            "season",
            "team_id",
            "promotable_match_teams",
            "review_needed_match_teams",
            "blocked_conflict_match_teams",
        ],
    )

    coverage = summary["coverage"]
    existing = int(coverage["public_assigned"])
    total = int(coverage["total_match_teams"])
    promotable = int(coverage["promotable_match_teams"])
    review_needed = int(coverage["review_needed_match_teams"])
    after = existing + promotable
    before_pct = (existing / total * 100) if total else 0.0
    after_pct = (after / total * 100) if total else 0.0

    lines = [
        "# External coach coupling report",
        "",
        "## Escopo",
        "",
        "- Camada externa carregada em raw/staging.",
        "- Nenhuma promocao para `mart.coach_tenure`.",
        "- Nenhuma promocao para `mart.fact_coach_match_assignment`.",
        f"- Janela aplicada: `{summary['window_start']}` ate `{summary['window_end']}`.",
        "",
        "## Cobertura potencial",
        "",
        f"- Match-teams publicos na janela: `{total}`",
        f"- Assignments publicos atuais: `{existing}` (`{before_pct:.2f}%`)",
        f"- Match-teams novos automaticamente promoviveis em staging: `{promotable}`",
        f"- Cobertura potencial se promovidos: `{after}` (`{after_pct:.2f}%`)",
        f"- Match-teams em review: `{review_needed}`",
        "",
        "## Gates",
        "",
    ]
    for key, value in summary["gate_counts"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Classificacao dos fatos externos", ""])
    for key, value in sorted(summary["classification_counts"].items(), key=lambda item: item[0]):
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Status dos candidatos por partida", ""])
    for key, value in sorted(summary["assignment_status_counts"].items(), key=lambda item: item[0]):
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Fontes com candidatos promoviveis", ""])
    for row in summary["top_promotable_sources"]:
        lines.append(
            f"- `{row['source']}`: `{row['candidates']}` candidatos, "
            f"`{row['missing_match_team_sum']}` match-teams brutos cobertos"
        )

    lines.extend(["", "## Times com maior cobertura incremental potencial", ""])
    for row in summary["top_teams_by_promotable_match_teams"][:20]:
        lines.append(f"- `{row['team_name']}`: `{row['promotable_match_teams']}` match-teams")

    lines.extend(["", "## Amostra de confirmacao", ""])
    lines.append(
        "Esta amostra nao altera criterio por clube; serve apenas para conferir nomes conhecidos contra o mesmo motor geral."
    )
    for row in summary["confirmation_sample"][:40]:
        lines.append(
            f"- `{row.get('local_team_name')}` | `{row.get('coach_name')}` | "
            f"{row.get('clipped_start_date') or '?'} ate {row.get('clipped_end_date') or '?'} | "
            f"`{row.get('classification')}` | lacuna `{row.get('canonical_missing_matches_covered')}`"
        )

    lines.extend(
        [
            "",
            "## Arquivos gerados",
            "",
            f"- Resumo JSON: `{SUMMARY_JSON_PATH}`",
            f"- Candidatos promoviveis: `{PROMOTABLE_CSV_PATH}`",
            f"- Conflitos: `{CONFLICTS_CSV_PATH}`",
            f"- Cobertura por recorte: `{COVERAGE_CSV_PATH}`",
            "",
            "## Leitura operacional",
            "",
            "- `promotable` ainda significa promovivel por regra, nao promovido ao produto.",
            "- `review_needed` pode enriquecer historico depois de validacao ou segunda fonte.",
            "- `blocked_conflict` impede publicacao ate escolha manual ou fonte mais forte.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    env_values = load_env_file(Path(args.env_file))
    cutoff = product_cutoff(env_values)
    run_id = args.run_id or utc_run_id()
    facts_path = read_facts_path(args.facts_path)
    facts = read_facts(facts_path, args.limit)
    dsn = resolve_pg_dsn(env_values)

    started = time.monotonic()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        if args.apply_schema:
            apply_schema(conn)

        local_teams = load_local_teams(conn)
        team_aliases = load_team_aliases(conn)
        match_teams_by_team = load_match_teams(conn, cutoff)
        existing_keys, assignments_by_team = load_existing_assignments(conn, cutoff)
        source_refs = load_identity_refs(conn)
        aliases = load_coach_alias_index(conn)
        canonical_name_index = load_canonical_name_index(conn, aliases)

        reset_staging(conn)
        upsert_raw_facts(conn, facts, run_id, args.batch_size)

        resolutions = [
            classify_fact(
                fact,
                local_teams,
                team_aliases,
                match_teams_by_team,
                existing_keys,
                assignments_by_team,
                source_refs,
                canonical_name_index,
                aliases,
                cutoff,
                run_id,
            )
            for fact in facts
        ]
        upsert_resolutions(conn, resolutions, args.batch_size)

        assignment_candidates = build_assignment_candidates(
            resolutions,
            match_teams_by_team,
            existing_keys,
            run_id,
        )
        upsert_assignment_candidates(conn, assignment_candidates, args.batch_size)
        mark_conflicts(conn)

        summary = build_summary(conn, run_id, cutoff, args.confirmation_team_id)
        summary["facts_loaded_this_run"] = len(facts)
        summary["assignment_candidate_rows_built_this_run"] = len(assignment_candidates)
        summary["elapsed_seconds"] = round(time.monotonic() - started, 2)
        write_reports(conn, summary)
        conn.commit()

    print(json.dumps(summary, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
