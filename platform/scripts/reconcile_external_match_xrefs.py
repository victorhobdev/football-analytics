from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    "associacao",
    "associacaoo",
    "athletic",
    "club",
    "clube",
    "de",
    "del",
    "do",
    "dos",
    "esporte",
    "esportiva",
    "esportivo",
    "fc",
    "foot",
    "footbal",
    "football",
    "futebol",
    "regatas",
    "s",
    "saf",
    "sa",
    "sc",
    "sociedade",
    "sport",
}

TOKEN_REPLACEMENTS = {
    "athletico": "atletico",
    "atletico-pr": "atletico",
    "bragantino": "bragantino",
    "botafogo-rj": "botafogo",
    "gremio": "gremio",
    "sao": "sao",
    "saoo": "sao",
}

FULL_NAME_ALIASES = {
    "atletico mg": "atletico mineiro",
    "botafogo rj": "botafogo",
    "ceara sporting club": "ceara",
    "clube atletico mineiro": "atletico mineiro",
    "s a f botafogo": "botafogo",
    "sport": "sport recife",
    "vasco": "vasco gama",
}


@dataclass(frozen=True)
class LocalMatch:
    match_id: int
    competition_key: str
    match_date: date
    home_team_name: str
    away_team_name: str
    home_signature: str
    away_signature: str
    home_goals: int | None
    away_goals: int | None


@dataclass(frozen=True)
class ExternalMatch:
    source: str
    source_match_id: str
    competition_key: str
    match_date: date
    home_team_name: str
    away_team_name: str
    home_signature: str
    away_signature: str
    home_goals: int | None
    away_goals: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcilia partidas externas com fixtures publicadas para popular "
            "control.brasileirao_fixture_xref, control.tm_game_fixture_xref "
            "e control.elo_match_xref."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument(
        "--source",
        choices=("all", "brasileirao", "transfermarkt", "eloratings"),
        default="all",
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
    text = (
        text.replace("&", " ")
        .replace("/", " ")
        .replace("-", " ")
        .replace(".", " ")
        .replace("'", " ")
        .replace("’", " ")
    )
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def team_signature(value: str | None) -> str:
    normalized = normalize_text(value)
    if normalized in FULL_NAME_ALIASES:
        return FULL_NAME_ALIASES[normalized]
    tokens = []
    for token in normalized.split():
        token = TOKEN_REPLACEMENTS.get(token, token)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    if not tokens:
        return normalized
    return " ".join(tokens)


def parse_iso_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_br_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


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


def sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def team_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return sequence_ratio(left, right)
    overlap = len(left_tokens & right_tokens)
    subset_ratio = overlap / min(len(left_tokens), len(right_tokens))
    jaccard = overlap / len(left_tokens | right_tokens)
    ordered_ratio = sequence_ratio(left, right)
    return max(jaccard, subset_ratio * 0.96, ordered_ratio)


def build_local_match_index(conn: psycopg.Connection[Any]) -> dict[tuple[str, date], list[LocalMatch]]:
    rows = []
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              fm.match_id,
              fm.competition_key,
              fm.date_day,
              rf.home_team_name,
              rf.away_team_name,
              fm.home_goals,
              fm.away_goals
            from mart.fact_matches fm
            inner join raw.fixtures rf
              on rf.fixture_id = fm.match_id
            where fm.competition_key is not null
              and fm.date_day is not null;
            """
        )
        rows = cursor.fetchall()

    index: dict[tuple[str, date], list[LocalMatch]] = {}
    for row in rows:
        competition_key = str(row["competition_key"])
        match_date = row["date_day"]
        match = LocalMatch(
            match_id=int(row["match_id"]),
            competition_key=competition_key,
            match_date=match_date,
            home_team_name=repair_text(row["home_team_name"]),
            away_team_name=repair_text(row["away_team_name"]),
            home_signature=team_signature(row["home_team_name"]),
            away_signature=team_signature(row["away_team_name"]),
            home_goals=parse_int(row["home_goals"]),
            away_goals=parse_int(row["away_goals"]),
        )
        index.setdefault((competition_key, match_date), []).append(match)
    return index


def load_tm_competition_map(conn: psycopg.Connection[Any]) -> dict[str, str]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select provider_league_code, competition_key
            from control.competition_provider_map
            where provider = 'transfermarkt'
              and provider_league_code is not null
              and is_active = true;
            """
        )
        rows = cursor.fetchall()
    return {
        str(row["provider_league_code"]).strip(): str(row["competition_key"]).strip()
        for row in rows
        if str(row["provider_league_code"]).strip() != ""
    }


def load_elo_competition_map(conn: psycopg.Connection[Any]) -> dict[str, str]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select provider_league_code, competition_key
            from control.competition_provider_map
            where provider = 'eloratings'
              and provider_league_code is not null
              and is_active = true;
            """
        )
        rows = cursor.fetchall()
    return {
        str(row["provider_league_code"]).strip(): str(row["competition_key"]).strip()
        for row in rows
        if str(row["provider_league_code"]).strip() != ""
    }


def iter_candidates(local_index: dict[tuple[str, date], list[LocalMatch]], competition_key: str, match_date: date) -> Iterable[tuple[LocalMatch, int]]:
    for day_delta in (0, -1, 1):
        probe_date = match_date + timedelta(days=day_delta)
        for match in local_index.get((competition_key, probe_date), []):
            yield match, day_delta


def score_match(external: ExternalMatch, local: LocalMatch, day_delta: int) -> tuple[float, dict[str, Any]]:
    home_similarity = team_similarity(external.home_signature, local.home_signature)
    away_similarity = team_similarity(external.away_signature, local.away_signature)
    date_score = 10.0 if day_delta == 0 else 7.0

    goals_exact = (
        external.home_goals is not None
        and external.away_goals is not None
        and external.home_goals == local.home_goals
        and external.away_goals == local.away_goals
    )
    goals_score = 10.0 if goals_exact else 0.0
    total_score = (home_similarity * 40.0) + (away_similarity * 40.0) + date_score + goals_score

    evidence = {
        "dayDelta": day_delta,
        "homeSimilarity": round(home_similarity, 4),
        "awaySimilarity": round(away_similarity, 4),
        "goalsExact": goals_exact,
        "localMatchId": local.match_id,
        "localHomeTeamName": local.home_team_name,
        "localAwayTeamName": local.away_team_name,
        "localHomeGoals": local.home_goals,
        "localAwayGoals": local.away_goals,
        "totalScore": round(total_score, 4),
    }
    return total_score, evidence


def classify_match(
    external: ExternalMatch,
    local_index: dict[tuple[str, date], list[LocalMatch]],
) -> tuple[int | None, str, float | None, str, str, dict[str, Any]]:
    scored_candidates: list[tuple[float, LocalMatch, dict[str, Any]]] = []
    for local, day_delta in iter_candidates(local_index, external.competition_key, external.match_date):
        total_score, evidence = score_match(external, local, day_delta)
        scored_candidates.append((total_score, local, evidence))

    if not scored_candidates:
        return (
            None,
            "new_coverage",
            None,
            "no_local_candidate_same_competition_date_window",
            "pending",
            {
                "competitionKey": external.competition_key,
                "matchDate": external.match_date.isoformat(),
                "homeTeamName": external.home_team_name,
                "awayTeamName": external.away_team_name,
            },
        )

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_match, best_evidence = scored_candidates[0]
    second_score = scored_candidates[1][0] if len(scored_candidates) > 1 else None
    best_evidence["competitionKey"] = external.competition_key
    best_evidence["matchDate"] = external.match_date.isoformat()
    best_evidence["homeTeamName"] = external.home_team_name
    best_evidence["awayTeamName"] = external.away_team_name
    best_evidence["secondBestScore"] = round(second_score, 4) if second_score is not None else None

    strong_home = float(best_evidence["homeSimilarity"]) >= 0.9
    strong_away = float(best_evidence["awaySimilarity"]) >= 0.9
    unique_enough = second_score is None or (best_score - second_score) >= 5.0
    premium_near_date = (
        best_score >= 93.0
        and float(best_evidence["homeSimilarity"]) >= 0.95
        and float(best_evidence["awaySimilarity"]) >= 0.95
        and bool(best_evidence["goalsExact"])
        and abs(int(best_evidence["dayDelta"])) <= 1
    )

    if (best_score >= 94.0 and strong_home and strong_away and unique_enough) or (
        premium_near_date and unique_enough
    ):
        if best_evidence["goalsExact"] and best_evidence["dayDelta"] == 0:
            match_method = "exact_date_exact_goals_strong_team_match"
        elif best_evidence["dayDelta"] == 0:
            match_method = "exact_date_strong_team_match"
        else:
            match_method = "near_date_strong_team_match"
        return (
            best_match.match_id,
            "linked_to_sportmonks",
            round(best_score / 100.0, 4),
            match_method,
            "auto_approved",
            best_evidence,
        )

    if best_score >= 85.0 and not unique_enough:
        return (
            None,
            "ambiguous",
            round(best_score / 100.0, 4),
            "multiple_local_candidates_close_score",
            "manual_review",
            best_evidence,
        )

    return (
        None,
        "new_coverage",
        round(best_score / 100.0, 4),
        "no_high_confidence_local_match",
        "pending",
        best_evidence,
    )


def load_brasileirao_matches(conn: psycopg.Connection[Any]) -> list[ExternalMatch]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              match_id,
              match_date_raw,
              home_team_name,
              away_team_name,
              home_score,
              away_score
            from raw.brasileirao_matches;
            """
        )
        rows = cursor.fetchall()

    matches: list[ExternalMatch] = []
    for row in rows:
        match_date = parse_br_date(row["match_date_raw"])
        if match_date is None:
            continue
        matches.append(
            ExternalMatch(
                source="dataset_brasileirao",
                source_match_id=str(row["match_id"]),
                competition_key="brasileirao_a",
                match_date=match_date,
                home_team_name=repair_text(row["home_team_name"]),
                away_team_name=repair_text(row["away_team_name"]),
                home_signature=team_signature(row["home_team_name"]),
                away_signature=team_signature(row["away_team_name"]),
                home_goals=parse_int(row["home_score"]),
                away_goals=parse_int(row["away_score"]),
            )
        )
    return matches


def load_tm_matches(conn: psycopg.Connection[Any], competition_map: dict[str, str]) -> list[ExternalMatch]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              game_id,
              competition_id,
              match_date_raw,
              home_club_name,
              away_club_name,
              home_club_goals,
              away_club_goals
            from raw.tm_games
            where competition_id = any(%s);
            """,
            [sorted(competition_map.keys())],
        )
        rows = cursor.fetchall()

    matches: list[ExternalMatch] = []
    for row in rows:
        competition_id = str(row["competition_id"]).strip()
        competition_key = competition_map.get(competition_id)
        match_date = parse_iso_date(row["match_date_raw"])
        if competition_key is None or match_date is None:
            continue
        matches.append(
            ExternalMatch(
                source="transfermarkt",
                source_match_id=str(row["game_id"]),
                competition_key=competition_key,
                match_date=match_date,
                home_team_name=repair_text(row["home_club_name"]),
                away_team_name=repair_text(row["away_club_name"]),
                home_signature=team_signature(row["home_club_name"]),
                away_signature=team_signature(row["away_club_name"]),
                home_goals=parse_int(row["home_club_goals"]),
                away_goals=parse_int(row["away_club_goals"]),
            )
        )
    return matches


def load_elo_matches(conn: psycopg.Connection[Any], competition_map: dict[str, str]) -> list[ExternalMatch]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              record_hash,
              division,
              match_date_raw,
              home_team_name,
              away_team_name,
              ft_home_raw,
              ft_away_raw
            from raw.elo_matches
            where division = any(%s);
            """,
            [sorted(competition_map.keys())],
        )
        rows = cursor.fetchall()

    matches: list[ExternalMatch] = []
    for row in rows:
        division = str(row["division"]).strip()
        competition_key = competition_map.get(division)
        match_date = parse_iso_date(row["match_date_raw"])
        if competition_key is None or match_date is None:
            continue
        matches.append(
            ExternalMatch(
                source="eloratings",
                source_match_id=str(row["record_hash"]),
                competition_key=competition_key,
                match_date=match_date,
                home_team_name=repair_text(row["home_team_name"]),
                away_team_name=repair_text(row["away_team_name"]),
                home_signature=team_signature(row["home_team_name"]),
                away_signature=team_signature(row["away_team_name"]),
                home_goals=parse_int(row["ft_home_raw"]),
                away_goals=parse_int(row["ft_away_raw"]),
            )
        )
    return matches


def upsert_brasileirao_results(conn: psycopg.Connection[Any], rows: list[tuple[Any, ...]]) -> None:
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into control.brasileirao_fixture_xref (
              brasileirao_match_id,
              local_fixture_id,
              match_date,
              home_team_name_raw,
              away_team_name_raw,
              identity_status,
              confidence,
              resolved_at,
              updated_at,
              match_method,
              review_status,
              source_evidence
            )
            values (%s, %s, %s, %s, %s, %s, %s, now(), now(), %s, %s, %s::jsonb)
            on conflict (brasileirao_match_id) do update set
              local_fixture_id = excluded.local_fixture_id,
              match_date = excluded.match_date,
              home_team_name_raw = excluded.home_team_name_raw,
              away_team_name_raw = excluded.away_team_name_raw,
              identity_status = excluded.identity_status,
              confidence = excluded.confidence,
              resolved_at = now(),
              updated_at = now(),
              match_method = excluded.match_method,
              review_status = excluded.review_status,
              source_evidence = excluded.source_evidence;
            """,
            rows,
        )


def upsert_tm_results(conn: psycopg.Connection[Any], rows: list[tuple[Any, ...]]) -> None:
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into control.tm_game_fixture_xref (
              tm_game_id,
              local_fixture_id,
              match_date,
              home_team_name_raw,
              away_team_name_raw,
              identity_status,
              confidence,
              resolved_at,
              updated_at,
              match_method,
              review_status,
              source_evidence
            )
            values (%s, %s, %s, %s, %s, %s, %s, now(), now(), %s, %s, %s::jsonb)
            on conflict (tm_game_id) do update set
              local_fixture_id = excluded.local_fixture_id,
              match_date = excluded.match_date,
              home_team_name_raw = excluded.home_team_name_raw,
              away_team_name_raw = excluded.away_team_name_raw,
              identity_status = excluded.identity_status,
              confidence = excluded.confidence,
              resolved_at = now(),
              updated_at = now(),
              match_method = excluded.match_method,
              review_status = excluded.review_status,
              source_evidence = excluded.source_evidence;
            """,
            rows,
        )


def upsert_elo_results(conn: psycopg.Connection[Any], rows: list[tuple[Any, ...]]) -> None:
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into control.elo_match_xref (
              elo_match_hash,
              local_fixture_id,
              match_date,
              competition_key,
              division,
              home_team_name_raw,
              away_team_name_raw,
              identity_status,
              confidence,
              resolved_at,
              updated_at,
              match_method,
              review_status,
              source_evidence
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now(), %s, %s, %s::jsonb)
            on conflict (elo_match_hash) do update set
              local_fixture_id = excluded.local_fixture_id,
              match_date = excluded.match_date,
              competition_key = excluded.competition_key,
              division = excluded.division,
              home_team_name_raw = excluded.home_team_name_raw,
              away_team_name_raw = excluded.away_team_name_raw,
              identity_status = excluded.identity_status,
              confidence = excluded.confidence,
              resolved_at = now(),
              updated_at = now(),
              match_method = excluded.match_method,
              review_status = excluded.review_status,
              source_evidence = excluded.source_evidence;
            """,
            rows,
        )


def summarize_status(rows: Iterable[tuple[Any, ...]], status_index: int) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        status = str(row[status_index])
        summary[status] = summary.get(status, 0) + 1
    return summary


def main() -> None:
    args = parse_args()
    env_values = load_env_file(Path(args.env_file))
    dsn = resolve_dsn(env_values)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        local_index = build_local_match_index(conn)
        tm_competition_map = load_tm_competition_map(conn)
        elo_competition_map = load_elo_competition_map(conn)

        brasileirao_rows: list[tuple[Any, ...]] = []
        tm_rows: list[tuple[Any, ...]] = []
        elo_rows: list[tuple[Any, ...]] = []

        if args.source in {"all", "brasileirao"}:
            for external in load_brasileirao_matches(conn):
                local_fixture_id, identity_status, confidence, match_method, review_status, evidence = classify_match(
                    external,
                    local_index,
                )
                brasileirao_rows.append(
                    (
                        external.source_match_id,
                        local_fixture_id,
                        external.match_date,
                        external.home_team_name,
                        external.away_team_name,
                        identity_status,
                        confidence,
                        match_method,
                        review_status,
                        json.dumps(evidence, ensure_ascii=True),
                    )
                )
            upsert_brasileirao_results(conn, brasileirao_rows)

        if args.source in {"all", "transfermarkt"}:
            for external in load_tm_matches(conn, tm_competition_map):
                local_fixture_id, identity_status, confidence, match_method, review_status, evidence = classify_match(
                    external,
                    local_index,
                )
                tm_rows.append(
                    (
                        external.source_match_id,
                        local_fixture_id,
                        external.match_date,
                        external.home_team_name,
                        external.away_team_name,
                        identity_status,
                        confidence,
                        match_method,
                        review_status,
                        json.dumps(evidence, ensure_ascii=True),
                    )
                )
            upsert_tm_results(conn, tm_rows)

        if args.source in {"all", "eloratings"}:
            for external in load_elo_matches(conn, elo_competition_map):
                local_fixture_id, identity_status, confidence, match_method, review_status, evidence = classify_match(
                    external,
                    local_index,
                )
                division = next(
                    (
                        provider_code
                        for provider_code, competition_key in elo_competition_map.items()
                        if competition_key == external.competition_key
                    ),
                    None,
                )
                elo_rows.append(
                    (
                        external.source_match_id,
                        local_fixture_id,
                        external.match_date,
                        external.competition_key,
                        division,
                        external.home_team_name,
                        external.away_team_name,
                        identity_status,
                        confidence,
                        match_method,
                        review_status,
                        json.dumps(evidence, ensure_ascii=True),
                    )
                )
            upsert_elo_results(conn, elo_rows)

        conn.commit()

    print(
        json.dumps(
            {
                "brasileirao": {
                    "processed": len(brasileirao_rows),
                    "statusSummary": summarize_status(brasileirao_rows, 5),
                },
                "transfermarkt": {
                    "processed": len(tm_rows),
                    "statusSummary": summarize_status(tm_rows, 5),
                },
                "eloratings": {
                    "processed": len(elo_rows),
                    "statusSummary": summarize_status(elo_rows, 7),
                },
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
