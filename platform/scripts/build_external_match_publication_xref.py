from __future__ import annotations

import json
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from _repo_root import resolve_repo_root


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"

STOPWORDS = {
    "a",
    "association",
    "athletic",
    "club",
    "clube",
    "de",
    "do",
    "dos",
    "esporte",
    "esportiva",
    "fc",
    "football",
    "futebol",
    "regatas",
    "saf",
    "sc",
    "sociedade",
    "sport",
}

SOURCE_PRIORITY = {
    "dataset_brasileirao": 400,
    "transfermarkt": 300,
    "eloratings": 200,
}

CANONICAL_SOURCE_OFFSET = {
    "dataset_brasileirao": 920_000_000_000,
    "transfermarkt": 930_000_000_000,
    "eloratings": 940_000_000_000,
}


@dataclass(frozen=True)
class ExternalCoverageMatch:
    source: str
    source_entity_id: str
    competition_key: str
    match_date: date
    home_team_name: str
    away_team_name: str
    home_signature: str
    away_signature: str
    home_goals: int | None
    away_goals: int | None
    source_priority: int


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


def resolve_dsn(env_values: dict[str, str]) -> str:
    dsn = os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL") or DEFAULT_DSN
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg2://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    if "@postgres:" in dsn:
        dsn = dsn.replace("@postgres:", "@127.0.0.1:")
    if "@postgres/" in dsn:
        dsn = dsn.replace("@postgres/", "@127.0.0.1/")
    if "@localhost:" in dsn:
        dsn = dsn.replace("@localhost:", "@127.0.0.1:")
    return dsn


def repair_text(value: str | None) -> str:
    text = (value or "").strip()
    if text == "":
        return ""
    if "Ã" in text or "Â" in text or "�" in text:
        try:
            return text.encode("latin1", "ignore").decode("utf-8", "ignore").strip()
        except UnicodeError:
            return text
    return text


def normalize_text(value: str | None) -> str:
    text = repair_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = text.replace("&", " ").replace("/", " ").replace("-", " ").replace(".", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def team_signature(value: str | None) -> str:
    normalized = normalize_text(value)
    tokens = [token for token in normalized.split() if token and token not in STOPWORDS]
    return " ".join(tokens) if tokens else normalized


def team_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return SequenceMatcher(None, left, right).ratio()
    overlap = len(left_tokens & right_tokens)
    subset_ratio = overlap / min(len(left_tokens), len(right_tokens))
    jaccard = overlap / len(left_tokens | right_tokens)
    ordered_ratio = SequenceMatcher(None, left, right).ratio()
    return max(jaccard, subset_ratio * 0.96, ordered_ratio)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def canonical_external_match_id(source: str, source_entity_id: str) -> int:
    offset = CANONICAL_SOURCE_OFFSET[source]
    if source_entity_id.isdigit():
        return offset + int(source_entity_id)
    digest = hashlib.sha1(source_entity_id.encode("utf-8")).hexdigest()
    return offset + (int(digest[:15], 16) % 99_999_999_999)


def load_external_new_coverage(conn: psycopg.Connection[Any]) -> list[ExternalCoverageMatch]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            with brasileirao as (
              select
                'dataset_brasileirao'::text as source,
                bx.brasileirao_match_id::text as source_entity_id,
                'brasileirao_a'::text as competition_key,
                bx.match_date,
                bx.home_team_name_raw,
                bx.away_team_name_raw,
                bm.home_score,
                bm.away_score
              from control.brasileirao_fixture_xref bx
              left join raw.brasileirao_matches bm
                on bm.match_id = bx.brasileirao_match_id
              where bx.identity_status = 'new_coverage'
                and bx.match_date is not null
            ),
            transfermarkt as (
              select
                'transfermarkt'::text as source,
                tx.tm_game_id::text as source_entity_id,
                cpm.competition_key,
                tx.match_date,
                tx.home_team_name_raw,
                tx.away_team_name_raw,
                tg.home_club_goals as home_score,
                tg.away_club_goals as away_score
              from control.tm_game_fixture_xref tx
              inner join raw.tm_games tg
                on tg.game_id = tx.tm_game_id
              inner join control.competition_provider_map cpm
                on cpm.provider = 'transfermarkt'
               and cpm.provider_league_code = tg.competition_id
              where tx.identity_status = 'new_coverage'
                and tx.match_date is not null
            ),
            eloratings as (
              select
                'eloratings'::text as source,
                ex.elo_match_hash::text as source_entity_id,
                ex.competition_key,
                ex.match_date,
                ex.home_team_name_raw,
                ex.away_team_name_raw,
                em.ft_home_raw as home_score,
                em.ft_away_raw as away_score
              from control.elo_match_xref ex
              left join raw.elo_matches em
                on em.record_hash = ex.elo_match_hash
              where ex.identity_status = 'new_coverage'
                and ex.match_date is not null
                and ex.competition_key is not null
            )
            select * from brasileirao
            union all
            select * from transfermarkt
            union all
            select * from eloratings;
            """
        )
        rows = cursor.fetchall()

    matches: list[ExternalCoverageMatch] = []
    for row in rows:
        source = str(row["source"])
        home_name = repair_text(row["home_team_name_raw"])
        away_name = repair_text(row["away_team_name_raw"])
        matches.append(
            ExternalCoverageMatch(
                source=source,
                source_entity_id=str(row["source_entity_id"]),
                competition_key=str(row["competition_key"]),
                match_date=row["match_date"],
                home_team_name=home_name,
                away_team_name=away_name,
                home_signature=team_signature(home_name),
                away_signature=team_signature(away_name),
                home_goals=parse_int(row["home_score"]),
                away_goals=parse_int(row["away_score"]),
                source_priority=SOURCE_PRIORITY[source],
            )
        )
    return matches


def candidate_dates(match_date: date) -> Iterable[date]:
    yield match_date
    yield match_date - timedelta(days=1)
    yield match_date + timedelta(days=1)


def is_duplicate(left: ExternalCoverageMatch, right: ExternalCoverageMatch) -> tuple[bool, dict[str, Any]]:
    home_similarity = team_similarity(left.home_signature, right.home_signature)
    away_similarity = team_similarity(left.away_signature, right.away_signature)
    goals_exact = (
        left.home_goals is not None
        and left.away_goals is not None
        and left.home_goals == right.home_goals
        and left.away_goals == right.away_goals
    )
    day_delta = abs((left.match_date - right.match_date).days)
    duplicate = home_similarity >= 0.92 and away_similarity >= 0.92 and goals_exact and day_delta <= 1
    return duplicate, {
        "homeSimilarity": round(home_similarity, 4),
        "awaySimilarity": round(away_similarity, 4),
        "goalsExact": goals_exact,
        "dayDelta": day_delta,
    }


def build_publication_rows(matches: list[ExternalCoverageMatch]) -> list[tuple[Any, ...]]:
    index: dict[tuple[str, date], list[ExternalCoverageMatch]] = {}
    publishable: list[ExternalCoverageMatch] = []
    rows: list[tuple[Any, ...]] = []

    sorted_matches = sorted(
        matches,
        key=lambda item: (
            item.competition_key,
            item.match_date,
            -item.source_priority,
            item.source,
            item.source_entity_id,
        ),
    )

    for match in sorted_matches:
        duplicate_of: ExternalCoverageMatch | None = None
        duplicate_evidence: dict[str, Any] | None = None
        for probe_date in candidate_dates(match.match_date):
            for candidate in index.get((match.competition_key, probe_date), []):
                duplicate, evidence = is_duplicate(match, candidate)
                if duplicate:
                    duplicate_of = candidate
                    duplicate_evidence = evidence
                    break
            if duplicate_of is not None:
                break

        if duplicate_of is None:
            publishable.append(match)
            index.setdefault((match.competition_key, match.match_date), []).append(match)
            evidence = {
                "homeTeamName": match.home_team_name,
                "awayTeamName": match.away_team_name,
                "homeGoals": match.home_goals,
                "awayGoals": match.away_goals,
            }
            rows.append(
                (
                    match.source,
                    match.source_entity_id,
                    canonical_external_match_id(match.source, match.source_entity_id),
                    "publishable",
                    None,
                    None,
                    match.competition_key,
                    match.match_date,
                    match.source_priority,
                    "external_source_priority_no_duplicate",
                    json.dumps(evidence, ensure_ascii=True),
                )
            )
            continue

        evidence = {
            "duplicateOfSource": duplicate_of.source,
            "duplicateOfSourceEntityId": duplicate_of.source_entity_id,
            "homeTeamName": match.home_team_name,
            "awayTeamName": match.away_team_name,
            "duplicateEvidence": duplicate_evidence or {},
        }
        rows.append(
            (
                match.source,
                match.source_entity_id,
                None,
                "suppressed_duplicate",
                duplicate_of.source,
                duplicate_of.source_entity_id,
                match.competition_key,
                match.match_date,
                match.source_priority,
                "external_cross_source_duplicate",
                json.dumps(evidence, ensure_ascii=True),
            )
        )

    return rows


def upsert_publication_rows(conn: psycopg.Connection[Any], rows: list[tuple[Any, ...]]) -> None:
    with conn.cursor() as cursor:
        cursor.execute("truncate table control.external_match_publication_xref;")
        cursor.executemany(
            """
            insert into control.external_match_publication_xref (
              source,
              source_entity_id,
              canonical_external_match_id,
              publication_status,
              duplicate_of_source,
              duplicate_of_source_entity_id,
              competition_key,
              match_date,
              source_priority,
              match_method,
              source_evidence
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb);
            """,
            rows,
        )


def summarize(rows: list[tuple[Any, ...]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        key = f"{row[0]}:{row[3]}"
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def main() -> None:
    env_values = load_env_file(DEFAULT_ENV_PATH)
    dsn = resolve_dsn(env_values)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        matches = load_external_new_coverage(conn)
        rows = build_publication_rows(matches)
        upsert_publication_rows(conn, rows)
        conn.commit()

    print(json.dumps({"processed": len(rows), "summary": summarize(rows)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
