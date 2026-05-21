from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass, replace
from io import StringIO
from typing import Any, Iterable

import pandas as pd
import psycopg
import requests


AS_OF_YEAR = 2025
SOURCE = "wikipedia"
USER_AGENT = "football-analytics-historical-stats/0.1"

SEASON_COLUMN_KEYWORDS = ("season", "year", "ano", "temporada")
CHAMPION_COLUMN_KEYWORDS = ("champion", "champions", "winner", "winners", "campeao", "campe", "vencedor")
PLAYER_COLUMN_KEYWORDS = ("player", "players", "jogador")
GOALS_COLUMN_KEYWORDS = ("goals", "goals scored", "gols")
RANK_COLUMN_KEYWORDS = ("rank", "ranking", "pos")
APPEARANCE_COLUMN_KEYWORDS = ("apps", "appearances", "matches")
DISQUALIFYING_APPEARANCE_METRICS = ("goals", "assists", "clean sheets", "scored", "taken")
INVALID_CHAMPION_NAMES = {
    "nan",
    "none",
    "not held",
    "no champion",
    "no champions",
    "cancelled",
    "canceled",
    "league suspended due to spanish civil war",
}

TEAM_RESOLUTION_STOPWORDS = frozenset(
    {
        "ac",
        "cf",
        "club",
        "de",
        "fc",
        "losc",
        "olympique",
        "rc",
        "sc",
        "sv",
        "the",
    }
)
TEAM_RESOLUTION_ALIAS_GROUPS = (
    frozenset({"athletico paranaense", "athletico pr"}),
    frozenset({"atletico goianiense", "atletico go"}),
    frozenset({"athletic bilbao", "athletic"}),
    frozenset({"inter", "inter milan", "internazionale"}),
    frozenset({"lyon", "lyonnais"}),
    frozenset({"psv", "psv eindhoven"}),
    frozenset({"rb bragantino", "red bull bragantino", "bragantino"}),
)

TEAM_MATCH_RECORD_HEURISTICS = {
    "most_points_single_season": "requires team/club, points, and a season embedded in the team cell",
    "most_goals_single_season_team": "requires a direct team-season goals-for record table; not inferred from points tables",
    "fewest_goals_conceded_single_season": "requires a direct team-season goals-against record table; not inferred from points tables",
    "longest_unbeaten_run": "requires a direct unbeaten-run table with team and match count",
    "longest_winning_run": "requires a direct winning-run table with team and match count",
    "biggest_win": "requires a direct match-record table with teams and score",
    "highest_scoring_match": "requires a direct match-record table with teams, score, and total goals",
}

INDIVIDUAL_RECORD_HEURISTICS = {
    "player_most_goals_single_season": "requires a direct player-season goals record table",
    "player_most_goals_single_match": "requires a direct match record table with player and goals as separate columns",
    "player_most_titles": "requires a direct player titles table",
    "player_most_appearances": "requires a direct appearances/games table with player and appearance count",
}


@dataclass(frozen=True)
class CompetitionWikiMapping:
    competition_key: str
    competition_id: int | None
    competition_name: str
    wiki_main_url: str
    wiki_scorers_url: str | None
    wiki_records_url: str | None


@dataclass(frozen=True)
class HistoricalStatRow:
    competition_key: str
    competition_id: int | None
    stat_code: str
    stat_group: str
    entity_type: str
    entity_id: int | None
    entity_name: str
    value_numeric: int
    value_label: str
    rank: int
    source_url: str
    as_of_year: int
    record_key: str
    metadata: dict[str, Any]
    ingestion_run_id: str
    season_label: str | None = None
    occurred_on: str | None = None


def build_default_pg_dsn() -> str:
    user = os.getenv("POSTGRES_USER", "football")
    password = os.getenv("POSTGRES_PASSWORD", "football")
    database = os.getenv("POSTGRES_DB", "football_dw")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def resolve_pg_dsn(explicit_dsn: str | None) -> str:
    return explicit_dsn or os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or build_default_pg_dsn()


def flatten_columns(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    flat_columns: list[str] = []
    for column in out.columns:
        if isinstance(column, tuple):
            parts = [str(part).strip() for part in column if str(part).strip() and not str(part).startswith("Unnamed")]
            flat_columns.append(" ".join(parts) if parts else str(column))
        else:
            flat_columns.append(str(column).strip())
    out.columns = flat_columns
    return out


def normalize_text(value: Any) -> str:
    raw = "" if value is None else str(value)
    raw = re.sub(r"\[[^\]]+\]", "", raw)
    raw = raw.replace("\xa0", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def normalize_column_name(value: str) -> str:
    return normalize_text(value).lower()


def normalize_entity_name(value: Any) -> str:
    cleaned = normalize_text(value)
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned)
    cleaned = re.sub(r"\s+\d+(?:st|nd|rd|th)?\s*[#*†‡§]*\s*$", "", cleaned)
    cleaned = re.sub(r"\s*[#*†‡§]+\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -")


def normalize_record_token(value: str) -> str:
    normalized = normalize_text(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def stable_record_key(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def table_payload(table: pd.DataFrame) -> list[dict[str, Any]]:
    normalized = table.where(pd.notnull(table), None)
    return json.loads(normalized.to_json(orient="records", date_format="iso"))


def payload_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_column(columns: Iterable[str], keywords: Iterable[str]) -> str | None:
    for column in columns:
        normalized_column = normalize_column_name(column)
        if any(keyword in normalized_column for keyword in keywords):
            return column
    return None


def find_preferred_column(
    columns: Iterable[str],
    *,
    include_keywords: Iterable[str],
    prefer_keywords: Iterable[str] = (),
    reject_keywords: Iterable[str] = (),
) -> str | None:
    matches: list[tuple[int, str]] = []
    for index, column in enumerate(columns):
        normalized_column = normalize_column_name(column)
        if not any(keyword in normalized_column for keyword in include_keywords):
            continue
        if any(keyword in normalized_column for keyword in reject_keywords):
            continue
        priority = 1 if any(keyword in normalized_column for keyword in prefer_keywords) else 0
        matches.append((priority, column))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], list(columns).index(item[1]) if hasattr(columns, '__iter__') else 0))
    return matches[0][1]


def find_season_column(columns: Iterable[str]) -> str | None:
    for column in columns:
        normalized_column = normalize_column_name(column)
        tokens = [token for token in re.split(r"[^a-z0-9]+", normalized_column) if token]
        if tokens and tokens[0] in SEASON_COLUMN_KEYWORDS:
            return column
    return None


def find_champion_columns(table: pd.DataFrame) -> tuple[str, str] | None:
    season_column = find_season_column(table.columns)
    champion_column = find_preferred_column(
        table.columns,
        include_keywords=CHAMPION_COLUMN_KEYWORDS,
        prefer_keywords=("club", "team"),
        reject_keywords=("country", "nation"),
    )
    if season_column is None or champion_column is None:
        return None
    if season_column == champion_column:
        return None
    return season_column, champion_column


def find_scorer_columns(table: pd.DataFrame) -> tuple[str, str, str | None] | None:
    if find_season_column(table.columns) is not None:
        return None

    columns = list(table.columns)
    player_column = find_column(table.columns, PLAYER_COLUMN_KEYWORDS)
    goals_column = find_column(table.columns, GOALS_COLUMN_KEYWORDS)
    rank_column = find_column(table.columns, RANK_COLUMN_KEYWORDS)
    appearance_column = find_column(table.columns, APPEARANCE_COLUMN_KEYWORDS)

    if player_column is None or goals_column is None:
        return None
    if player_column == goals_column:
        return None
    if appearance_column is not None and columns.index(appearance_column) < columns.index(goals_column):
        return None
    return player_column, goals_column, rank_column


def find_appearance_record_columns(table: pd.DataFrame) -> tuple[str, str, str | None] | None:
    columns = list(table.columns)
    player_column = find_column(columns, PLAYER_COLUMN_KEYWORDS)
    appearance_column = find_column(columns, ("appearances", "games"))
    rank_column = find_column(columns, RANK_COLUMN_KEYWORDS)

    if player_column is None or appearance_column is None:
        return None
    if player_column == appearance_column:
        return None

    appearance_index = columns.index(appearance_column)
    for metric in DISQUALIFYING_APPEARANCE_METRICS:
        metric_column = find_column(columns, (metric,))
        if metric_column is not None and columns.index(metric_column) < appearance_index:
            return None

    return player_column, appearance_column, rank_column


def find_player_season_goals_columns(table: pd.DataFrame) -> tuple[str, str, str] | None:
    season_column = find_season_column(table.columns)
    player_column = find_column(table.columns, PLAYER_COLUMN_KEYWORDS)
    goals_column = find_column(table.columns, (*GOALS_COLUMN_KEYWORDS, "tally"))

    if season_column is None or player_column is None or goals_column is None:
        return None
    if len({season_column, player_column, goals_column}) < 3:
        return None

    return season_column, player_column, goals_column


def parse_int(value: Any) -> int | None:
    text = normalize_text(value)
    match = re.search(r"-?\d+", text.replace(",", "").replace("−", "-"))
    if match is None:
        return None
    return int(match.group(0))


def extract_years(value: Any) -> list[int]:
    text = normalize_text(value)
    return [int(year) for year in re.findall(r"\b((?:18|19|20)\d{2})\b", text)]


def find_exact_column(table: pd.DataFrame, *candidates: str) -> str | None:
    normalized_candidates = {candidate.lower() for candidate in candidates}
    for column in table.columns:
        if normalize_column_name(column) in normalized_candidates:
            return column
    return None


def find_direct_titles_columns(table: pd.DataFrame) -> tuple[str, str, str | None] | None:
    team_column = find_exact_column(table, "club", "team")
    titles_column = find_exact_column(table, "titles", "winners", "won", "champions")
    seasons_column = find_exact_column(table, "years won", "winning seasons")

    if team_column is None or titles_column is None or team_column == titles_column:
        return None

    return team_column, titles_column, seasons_column


def extract_team_and_season(value: Any) -> tuple[str, str | None]:
    text = normalize_text(value)
    match = re.match(r"^(?P<team>.+?)\s+\((?P<season>[^)]*\d{4}[^)]*)\)", text)
    if match:
        return normalize_entity_name(match.group("team")), normalize_text(match.group("season"))
    return normalize_entity_name(text), None


def parse_embedded_team_points(value: Any) -> list[tuple[str, int]]:
    text = normalize_text(value)
    if not text:
        return []

    matches: list[tuple[str, int]] = []
    for match in re.finditer(r"(?P<team>.+?)\s*\((?P<points>-?\d+)\)(?:,|$)", text):
        team_name = normalize_entity_name(match.group("team"))
        points = int(match.group("points"))
        if not team_name:
            continue
        matches.append((team_name, points))

    return matches


def build_team_record_row(
    *,
    mapping: CompetitionWikiMapping,
    stat_code: str,
    entity_name: str,
    value_numeric: int,
    value_label: str,
    season_label: str | None,
    source_url: str,
    as_of_year: int,
    ingestion_run_id: str,
    table_index: int,
    parser_name: str,
    metadata: dict[str, Any],
) -> HistoricalStatRow:
    record_key = stable_record_key(
        stat_code,
        "team",
        normalize_record_token(entity_name),
        normalize_record_token(str(season_label or "unknown")),
    )
    return HistoricalStatRow(
        competition_key=mapping.competition_key,
        competition_id=mapping.competition_id,
        stat_code=stat_code,
        stat_group="team_records",
        entity_type="team",
        entity_id=None,
        entity_name=entity_name,
        value_numeric=value_numeric,
        value_label=value_label,
        rank=1,
        season_label=season_label,
        source_url=source_url,
        as_of_year=as_of_year,
        record_key=record_key,
        metadata={
            "sourceTableIndex": table_index,
            "parser": parser_name,
            **metadata,
        },
        ingestion_run_id=ingestion_run_id,
    )


def reduce_best_record_rows(rows: list[HistoricalStatRow]) -> list[HistoricalStatRow]:
    if not rows:
        return []

    comparison_mode = {
        "most_points_single_season": "max",
        "most_goals_single_season_team": "max",
        "fewest_goals_conceded_single_season": "min",
        "player_most_appearances": "max",
        "player_most_goals_single_season": "max",
    }

    reduced: list[HistoricalStatRow] = []
    for stat_code in sorted({row.stat_code for row in rows}):
        stat_rows = [row for row in rows if row.stat_code == stat_code]
        mode = comparison_mode.get(stat_code)
        if mode is None:
            reduced.extend(stat_rows)
            continue

        values = [int(row.value_numeric) for row in stat_rows]
        target_value = max(values) if mode == "max" else min(values)
        target_rows = [row for row in stat_rows if int(row.value_numeric) == target_value]

        unique_rows: dict[str, HistoricalStatRow] = {}
        for row in target_rows:
            unique_rows[row.record_key] = replace(row, rank=1)

        reduced.extend(
            sorted(
                unique_rows.values(),
                key=lambda row: (
                    normalize_record_token(row.entity_name),
                    normalize_record_token(str(row.season_label or "")),
                    row.record_key,
                ),
            )
        )

    return reduced


def build_source_url_list(*urls: str | None) -> list[str]:
    deduped: list[str] = []
    for url in urls:
        normalized_url = (url or "").strip()
        if not normalized_url or normalized_url in deduped:
            continue
        deduped.append(normalized_url)
    return deduped


def parse_champions_table(
    *,
    mapping: CompetitionWikiMapping,
    table: pd.DataFrame,
    table_index: int,
    source_url: str,
    ingestion_run_id: str,
    as_of_year: int,
) -> list[HistoricalStatRow]:
    columns = find_champion_columns(table)
    if columns is None:
        return []

    season_column, champion_column = columns
    champions: dict[str, int] = {}
    seasons_by_champion: dict[str, list[str]] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for _, row in table.iterrows():
        season = normalize_text(row.get(season_column))
        champion = normalize_entity_name(row.get(champion_column))
        if not season or not champion:
            continue
        if not extract_years(season):
            continue
        if champion.lower() in INVALID_CHAMPION_NAMES:
            continue
        if champion == normalize_entity_name(season):
            continue
        if re.fullmatch(r"\d+", champion):
            continue
        pair = (season, champion)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        champions[champion] = champions.get(champion, 0) + 1
        seasons_by_champion.setdefault(champion, []).append(season)

    if not champions:
        return []

    sorted_champions = sorted(champions.items(), key=lambda item: (-item[1], normalize_record_token(item[0])))
    rows: list[HistoricalStatRow] = []
    previous_value: int | None = None
    current_rank = 0

    for index, (entity_name, titles) in enumerate(sorted_champions, start=1):
        if titles != previous_value:
            current_rank = index
            previous_value = titles
        record_key = stable_record_key("all_time_champions", "team", normalize_record_token(entity_name))
        rows.append(
            HistoricalStatRow(
                competition_key=mapping.competition_key,
                competition_id=mapping.competition_id,
                stat_code="all_time_champions",
                stat_group="champions",
                entity_type="team",
                entity_id=None,
                entity_name=entity_name,
                value_numeric=titles,
                value_label=f"{titles} titles",
                rank=current_rank,
                source_url=source_url,
                as_of_year=as_of_year,
                record_key=record_key,
                metadata={
                    "sourceTableIndex": table_index,
                    "seasonColumn": season_column,
                    "championColumn": champion_column,
                    "seasons": seasons_by_champion.get(entity_name, []),
                },
                ingestion_run_id=ingestion_run_id,
            )
        )

    return rows


def parse_champion_titles_table(
    *,
    mapping: CompetitionWikiMapping,
    table: pd.DataFrame,
    table_index: int,
    source_url: str,
    ingestion_run_id: str,
    as_of_year: int,
) -> tuple[list[HistoricalStatRow], int | None]:
    columns = find_direct_titles_columns(table)
    if columns is None:
        return [], None

    team_column, titles_column, seasons_column = columns
    parsed_rows: list[tuple[str, int, list[str]]] = []
    candidate_years: list[int] = []

    for _, row in table.iterrows():
        entity_name = normalize_entity_name(row.get(team_column))
        titles = parse_int(row.get(titles_column))
        seasons_text = normalize_text(row.get(seasons_column)) if seasons_column else ""
        seasons = [item.strip() for item in seasons_text.split(",") if item.strip()] if seasons_text else []

        if not entity_name or titles is None:
            continue
        if titles <= 0:
            continue
        if entity_name.lower() in INVALID_CHAMPION_NAMES:
            continue
        if re.fullmatch(r"\d+", entity_name):
            continue

        parsed_rows.append((entity_name, titles, seasons))
        candidate_years.extend(extract_years(seasons_text))

    if len(parsed_rows) < 2:
        return [], None

    parsed_rows.sort(key=lambda item: (-item[1], normalize_record_token(item[0])))
    rows: list[HistoricalStatRow] = []
    previous_value: int | None = None
    current_rank = 0

    for index, (entity_name, titles, seasons) in enumerate(parsed_rows, start=1):
        if titles != previous_value:
            current_rank = index
            previous_value = titles
        record_key = stable_record_key("all_time_champions", "team", normalize_record_token(entity_name))
        rows.append(
            HistoricalStatRow(
                competition_key=mapping.competition_key,
                competition_id=mapping.competition_id,
                stat_code="all_time_champions",
                stat_group="champions",
                entity_type="team",
                entity_id=None,
                entity_name=entity_name,
                value_numeric=titles,
                value_label=f"{titles} titles",
                rank=current_rank,
                source_url=source_url,
                as_of_year=as_of_year,
                record_key=record_key,
                metadata={
                    "sourceTableIndex": table_index,
                    "teamColumn": team_column,
                    "titlesColumn": titles_column,
                    "winningSeasonsColumn": seasons_column,
                    "seasons": seasons,
                    "parser": "titles_table",
                },
                ingestion_run_id=ingestion_run_id,
            )
        )

    return rows, min(candidate_years) if candidate_years else None


def parse_team_match_records_table(
    *,
    mapping: CompetitionWikiMapping,
    table: pd.DataFrame,
    table_index: int,
    source_url: str,
    ingestion_run_id: str,
    as_of_year: int,
) -> list[HistoricalStatRow]:
    season_column = find_season_column(table.columns)
    team_column = find_exact_column(table, "team", "club")
    points_column = find_exact_column(table, "pts", "points")
    played_column = find_exact_column(table, "pld", "played")
    wins_column = find_exact_column(table, "w", "wins")
    draws_column = find_exact_column(table, "d", "draws")
    losses_column = find_exact_column(table, "l", "losses")
    goals_for_column = find_exact_column(table, "gf", "goals for")
    goals_against_column = find_exact_column(table, "ga", "goals against")
    goal_difference_column = find_exact_column(table, "gd", "goal difference")

    record_rows: list[HistoricalStatRow] = []

    if season_column and team_column and any(
        column is not None for column in (points_column, goals_for_column, goals_against_column)
    ):
        rows: list[dict[str, Any]] = []
        for _, row in table.iterrows():
            season_label = normalize_text(row.get(season_column))
            team_name = normalize_entity_name(row.get(team_column))
            if not team_name or not extract_years(season_label):
                continue
            rows.append(
                {
                    "teamName": team_name,
                    "seasonLabel": season_label,
                    "points": parse_int(row.get(points_column)) if points_column else None,
                    "played": parse_int(row.get(played_column)) if played_column else None,
                    "wins": parse_int(row.get(wins_column)) if wins_column else None,
                    "draws": parse_int(row.get(draws_column)) if draws_column else None,
                    "losses": parse_int(row.get(losses_column)) if losses_column else None,
                    "goalsFor": parse_int(row.get(goals_for_column)) if goals_for_column else None,
                    "goalsAgainst": parse_int(row.get(goals_against_column)) if goals_against_column else None,
                    "goalDifference": parse_int(row.get(goal_difference_column)) if goal_difference_column else None,
                }
            )

        if rows:
            point_rows = [row for row in rows if row.get("points") is not None]
            if point_rows:
                highest_points = max(int(row["points"]) for row in point_rows)
                for row in point_rows:
                    if int(row["points"]) != highest_points:
                        continue
                    record_rows.append(
                        build_team_record_row(
                            mapping=mapping,
                            stat_code="most_points_single_season",
                            entity_name=str(row["teamName"]),
                            value_numeric=highest_points,
                            value_label=f"{highest_points} points",
                            season_label=str(row["seasonLabel"]),
                            source_url=source_url,
                            as_of_year=as_of_year,
                            ingestion_run_id=ingestion_run_id,
                            table_index=table_index,
                            parser_name="team_season_metrics_table",
                            metadata={
                                "seasonColumn": season_column,
                                "teamColumn": team_column,
                                "pointsColumn": points_column,
                                "played": row.get("played"),
                                "wins": row.get("wins"),
                                "draws": row.get("draws"),
                                "losses": row.get("losses"),
                                "goalsFor": row.get("goalsFor"),
                                "goalsAgainst": row.get("goalsAgainst"),
                                "goalDifference": row.get("goalDifference"),
                            },
                        )
                    )

            goals_for_rows = [row for row in rows if row.get("goalsFor") is not None]
            if goals_for_rows:
                highest_goals_for = max(int(row["goalsFor"]) for row in goals_for_rows)
                for row in goals_for_rows:
                    if int(row["goalsFor"]) != highest_goals_for:
                        continue
                    record_rows.append(
                        build_team_record_row(
                            mapping=mapping,
                            stat_code="most_goals_single_season_team",
                            entity_name=str(row["teamName"]),
                            value_numeric=highest_goals_for,
                            value_label=f"{highest_goals_for} goals",
                            season_label=str(row["seasonLabel"]),
                            source_url=source_url,
                            as_of_year=as_of_year,
                            ingestion_run_id=ingestion_run_id,
                            table_index=table_index,
                            parser_name="team_season_metrics_table",
                            metadata={
                                "seasonColumn": season_column,
                                "teamColumn": team_column,
                                "goalsForColumn": goals_for_column,
                                "points": row.get("points"),
                                "goalsAgainst": row.get("goalsAgainst"),
                            },
                        )
                    )

            goals_against_rows = [row for row in rows if row.get("goalsAgainst") is not None]
            if goals_against_rows:
                lowest_goals_against = min(int(row["goalsAgainst"]) for row in goals_against_rows)
                for row in goals_against_rows:
                    if int(row["goalsAgainst"]) != lowest_goals_against:
                        continue
                    record_rows.append(
                        build_team_record_row(
                            mapping=mapping,
                            stat_code="fewest_goals_conceded_single_season",
                            entity_name=str(row["teamName"]),
                            value_numeric=lowest_goals_against,
                            value_label=f"{lowest_goals_against} goals conceded",
                            season_label=str(row["seasonLabel"]),
                            source_url=source_url,
                            as_of_year=as_of_year,
                            ingestion_run_id=ingestion_run_id,
                            table_index=table_index,
                            parser_name="team_season_metrics_table",
                            metadata={
                                "seasonColumn": season_column,
                                "teamColumn": team_column,
                                "goalsAgainstColumn": goals_against_column,
                                "points": row.get("points"),
                                "goalsFor": row.get("goalsFor"),
                            },
                        )
                    )

    if record_rows:
        return record_rows

    combined_points_column = None
    if season_column and points_column is None:
        combined_points_column = find_column(table.columns, ("points", "point"))

    if season_column is None or combined_points_column is None:
        return []

    rows = []
    for _, row in table.iterrows():
        season_label = normalize_text(row.get(season_column))
        if not extract_years(season_label):
            continue
        for team_name, points in parse_embedded_team_points(row.get(combined_points_column)):
            rows.append(
                {
                    "teamName": team_name,
                    "seasonLabel": season_label,
                    "points": points,
                }
            )

    if not rows:
        return []

    highest_points = max(int(row["points"]) for row in rows)
    return [
        build_team_record_row(
            mapping=mapping,
            stat_code="most_points_single_season",
            entity_name=str(row["teamName"]),
            value_numeric=highest_points,
            value_label=f"{highest_points} points",
            season_label=str(row["seasonLabel"]),
            source_url=source_url,
            as_of_year=as_of_year,
            ingestion_run_id=ingestion_run_id,
            table_index=table_index,
            parser_name="embedded_team_points_table",
            metadata={
                "seasonColumn": season_column,
                "combinedPointsColumn": combined_points_column,
            },
        )
        for row in rows
        if int(row["points"]) == highest_points
    ]


def parse_individual_records_table(
    *,
    mapping: CompetitionWikiMapping,
    table: pd.DataFrame,
    table_index: int,
    source_url: str,
    ingestion_run_id: str,
    as_of_year: int,
) -> list[HistoricalStatRow]:
    record_rows: list[HistoricalStatRow] = []

    season_goals_columns = find_player_season_goals_columns(table)
    if season_goals_columns is not None:
        season_column, player_column, goals_column = season_goals_columns
        season_rows: list[dict[str, Any]] = []
        for _, row in table.iterrows():
            season_label = normalize_text(row.get(season_column))
            player_name = normalize_entity_name(row.get(player_column))
            goals = parse_int(row.get(goals_column))
            if not player_name or goals is None or not extract_years(season_label):
                continue
            season_rows.append(
                {
                    "entity_name": player_name,
                    "seasonLabel": season_label,
                    "goals": goals,
                }
            )

        if season_rows:
            top_goals = max(int(row["goals"]) for row in season_rows)
            for row in season_rows:
                if int(row["goals"]) != top_goals:
                    continue
                entity_name = str(row["entity_name"])
                season_label = str(row["seasonLabel"])
                record_key = stable_record_key(
                    "player_most_goals_single_season",
                    "player",
                    normalize_record_token(entity_name),
                    normalize_record_token(season_label),
                )
                record_rows.append(
                    HistoricalStatRow(
                        competition_key=mapping.competition_key,
                        competition_id=mapping.competition_id,
                        stat_code="player_most_goals_single_season",
                        stat_group="player_records",
                        entity_type="player",
                        entity_id=None,
                        entity_name=entity_name,
                        value_numeric=top_goals,
                        value_label=f"{top_goals} goals",
                        rank=1,
                        season_label=season_label,
                        source_url=source_url,
                        as_of_year=as_of_year,
                        record_key=record_key,
                        metadata={
                            "sourceTableIndex": table_index,
                            "seasonColumn": season_column,
                            "playerColumn": player_column,
                            "goalsColumn": goals_column,
                            "parser": "player_season_goals_table",
                        },
                        ingestion_run_id=ingestion_run_id,
                    )
                )

    columns = find_appearance_record_columns(table)
    if columns is None:
        return record_rows

    player_column, appearance_column, rank_column = columns
    rows: list[dict[str, Any]] = []
    for _, row in table.iterrows():
        player_name = normalize_entity_name(row.get(player_column))
        appearances = parse_int(row.get(appearance_column))
        if not player_name or appearances is None:
            continue
        rows.append(
            {
                "entity_name": player_name,
                "appearances": appearances,
                "rank": parse_int(row.get(rank_column)) if rank_column else None,
            }
        )

    if not rows:
        return record_rows

    top_row = sorted(rows, key=lambda item: (item["rank"] is None, item["rank"] or 0, -int(item["appearances"])))[0]
    entity_name = str(top_row["entity_name"])
    appearances = int(top_row["appearances"])
    record_key = stable_record_key("player_most_appearances", "player", normalize_record_token(entity_name))
    record_rows.append(
        HistoricalStatRow(
            competition_key=mapping.competition_key,
            competition_id=mapping.competition_id,
            stat_code="player_most_appearances",
            stat_group="player_records",
            entity_type="player",
            entity_id=None,
            entity_name=entity_name,
            value_numeric=appearances,
            value_label=f"{appearances} appearances",
            rank=1,
            source_url=source_url,
            as_of_year=as_of_year,
            record_key=record_key,
            metadata={
                "sourceTableIndex": table_index,
                "playerColumn": player_column,
                "appearanceColumn": appearance_column,
                "parser": "player_appearances_table",
            },
            ingestion_run_id=ingestion_run_id,
        )
    )

    return record_rows


def parse_scorers_table(
    *,
    mapping: CompetitionWikiMapping,
    table: pd.DataFrame,
    table_index: int,
    source_url: str,
    ingestion_run_id: str,
    as_of_year: int,
) -> list[HistoricalStatRow]:
    columns = find_scorer_columns(table)
    if columns is None:
        return []

    player_column, goals_column, rank_column = columns
    parsed_rows: list[dict[str, Any]] = []

    for _, row in table.iterrows():
        player_name = normalize_entity_name(row.get(player_column))
        goals = parse_int(row.get(goals_column))
        if not player_name or player_name.lower() in {"nan", "none"} or goals is None:
            continue
        parsed_rows.append(
            {
                "entity_name": player_name,
                "goals": goals,
                "source_rank": parse_int(row.get(rank_column)) if rank_column else None,
            }
        )

    if not parsed_rows:
        return []

    parsed_rows.sort(key=lambda item: (item["source_rank"] is None, item["source_rank"] or 0, -item["goals"], normalize_record_token(item["entity_name"])))

    rows: list[HistoricalStatRow] = []
    previous_value: int | None = None
    current_rank = 0
    for index, parsed_row in enumerate(parsed_rows, start=1):
        goals = int(parsed_row["goals"])
        if parsed_row["source_rank"] is not None:
            current_rank = int(parsed_row["source_rank"])
        elif goals != previous_value:
            current_rank = index
        previous_value = goals

        entity_name = str(parsed_row["entity_name"])
        record_key = stable_record_key("all_time_top_scorers", "player", normalize_record_token(entity_name))
        rows.append(
            HistoricalStatRow(
                competition_key=mapping.competition_key,
                competition_id=mapping.competition_id,
                stat_code="all_time_top_scorers",
                stat_group="scorers",
                entity_type="player",
                entity_id=None,
                entity_name=entity_name,
                value_numeric=goals,
                value_label=f"{goals} goals",
                rank=current_rank,
                source_url=source_url,
                as_of_year=as_of_year,
                record_key=record_key,
                metadata={
                    "sourceTableIndex": table_index,
                    "playerColumn": player_column,
                    "goalsColumn": goals_column,
                    "rankColumn": rank_column,
                },
                ingestion_run_id=ingestion_run_id,
            )
        )

    return rows


def fetch_mappings(conn: psycopg.Connection[Any], competition_key: str | None) -> list[CompetitionWikiMapping]:
    params: list[Any] = []
    where_clause = "where is_active"
    if competition_key:
        where_clause += " and competition_key = %s"
        params.append(competition_key)

    rows = conn.execute(
        f"""
        select competition_key, competition_id, competition_name, wiki_main_url, wiki_scorers_url, wiki_records_url
        from control.competition_wiki_mapping
        {where_clause}
        order by competition_key
        """,
        params,
    ).fetchall()

    return [
        CompetitionWikiMapping(
            competition_key=row[0],
            competition_id=int(row[1]) if row[1] is not None else None,
            competition_name=row[2],
            wiki_main_url=row[3],
            wiki_scorers_url=row[4],
            wiki_records_url=row[5],
        )
        for row in rows
    ]


def insert_raw_table(
    conn: psycopg.Connection[Any],
    *,
    ingestion_run_id: str,
    competition_key: str,
    source_url: str,
    table_index: int | None,
    table_caption: str | None,
    payload_jsonb: Any | None,
    parse_status: str,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    source_hash = payload_hash(payload_jsonb) if payload_jsonb is not None else None
    conn.execute(
        """
        insert into raw.wikipedia_competition_tables (
          ingestion_run_id,
          competition_key,
          source_url,
          table_index,
          table_caption,
          source_hash,
          payload_jsonb,
          parse_status,
          error_message,
          metadata
        )
        values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
        """,
        [
            ingestion_run_id,
            competition_key,
            source_url,
            table_index,
            table_caption,
            source_hash,
            json.dumps(payload_jsonb, ensure_ascii=True, default=str) if payload_jsonb is not None else None,
            parse_status,
            error_message,
            json.dumps(metadata or {}, ensure_ascii=True, default=str),
        ],
    )


def upsert_historical_rows(conn: psycopg.Connection[Any], rows: list[HistoricalStatRow]) -> None:
    for row in rows:
        conn.execute(
            """
            insert into mart.competition_historical_stats (
              competition_key,
              competition_id,
              stat_code,
              stat_group,
              entity_type,
              entity_id,
              entity_name,
              value_numeric,
              value_label,
              rank,
              season_label,
              occurred_on,
              source,
              source_url,
              as_of_year,
              record_key,
              metadata,
              ingestion_run_id
            )
            values (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
            )
            on conflict (competition_key, stat_code, as_of_year, source, record_key) do update
            set
              competition_id = excluded.competition_id,
              stat_group = excluded.stat_group,
              entity_type = excluded.entity_type,
              entity_id = excluded.entity_id,
              entity_name = excluded.entity_name,
              value_numeric = excluded.value_numeric,
              value_label = excluded.value_label,
              rank = excluded.rank,
              season_label = excluded.season_label,
              occurred_on = excluded.occurred_on,
              source_url = excluded.source_url,
              metadata = excluded.metadata,
              ingestion_run_id = excluded.ingestion_run_id,
              updated_at = now()
            """,
            [
                row.competition_key,
                row.competition_id,
                row.stat_code,
                row.stat_group,
                row.entity_type,
                row.entity_id,
                row.entity_name,
                row.value_numeric,
                row.value_label,
                row.rank,
                row.season_label,
                row.occurred_on,
                SOURCE,
                row.source_url,
                row.as_of_year,
                row.record_key,
                json.dumps(row.metadata, ensure_ascii=True, default=str),
                row.ingestion_run_id,
            ],
        )


def replace_existing_rows(
    conn: psycopg.Connection[Any],
    *,
    competition_key: str,
    stat_codes: list[str],
    as_of_year: int,
) -> None:
    conn.execute(
        """
        delete from mart.competition_historical_stats
        where competition_key = %s
          and stat_code = any(%s)
          and as_of_year = %s
          and source = %s
        """,
        [competition_key, stat_codes, as_of_year, SOURCE],
    )


def ingest_champions(
    conn: psycopg.Connection[Any],
    *,
    mappings: list[CompetitionWikiMapping],
    ingestion_run_id: str,
    as_of_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ingestionRunId": ingestion_run_id,
        "asOfYear": as_of_year,
        "competitions": [],
    }
    headers = {"User-Agent": USER_AGENT}

    for mapping in mappings:
        competition_summary: dict[str, Any] = {
            "competitionKey": mapping.competition_key,
            "sourceUrl": mapping.wiki_main_url,
            "rawTables": 0,
            "historicalRows": 0,
            "status": "pending",
        }
        try:
            response = requests.get(mapping.wiki_main_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=mapping.wiki_main_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="failed_fetch",
                    error_message=str(exc),
                )
            competition_summary["status"] = "failed_fetch"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        try:
            tables = [flatten_columns(table) for table in pd.read_html(StringIO(response.text))]
        except ValueError as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=mapping.wiki_main_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="no_table",
                    error_message=str(exc),
                )
            competition_summary["status"] = "no_table"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        direct_rows: list[HistoricalStatRow] = []
        direct_rows_min_year: int | None = None
        fallback_rows: list[HistoricalStatRow] = []
        for table_index, table in enumerate(tables):
            payload = table_payload(table)
            titles_rows, titles_min_year = parse_champion_titles_table(
                mapping=mapping,
                table=table,
                table_index=table_index,
                source_url=mapping.wiki_main_url,
                ingestion_run_id=ingestion_run_id,
                as_of_year=as_of_year,
            )
            champion_rows = titles_rows or parse_champions_table(
                mapping=mapping,
                table=table,
                table_index=table_index,
                source_url=mapping.wiki_main_url,
                ingestion_run_id=ingestion_run_id,
                as_of_year=as_of_year,
            )
            parse_status = "success" if champion_rows else "unsupported_structure"
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=mapping.wiki_main_url,
                    table_index=table_index,
                    table_caption=None,
                    payload_jsonb=payload,
                    parse_status=parse_status,
                    metadata={
                        "columns": list(table.columns),
                        "parser": "titles_table" if titles_rows else ("season_table" if champion_rows else None),
                    },
                )
            competition_summary["rawTables"] += 1
            if titles_rows:
                if direct_rows_min_year is None or (titles_min_year is not None and titles_min_year > direct_rows_min_year):
                    direct_rows = titles_rows
                    direct_rows_min_year = titles_min_year
            elif champion_rows and not fallback_rows:
                fallback_rows = champion_rows

        all_rows = direct_rows or fallback_rows

        if not all_rows:
            competition_summary["status"] = "unsupported_structure"
        else:
            if not dry_run:
                replace_existing_rows(
                    conn,
                    competition_key=mapping.competition_key,
                    stat_codes=sorted({row.stat_code for row in all_rows}),
                    as_of_year=as_of_year,
                )
                upsert_historical_rows(conn, all_rows)
            competition_summary["historicalRows"] = len(all_rows)
            competition_summary["status"] = "success"

        summary["competitions"].append(competition_summary)

    return summary


def ingest_team_match_records(
    conn: psycopg.Connection[Any],
    *,
    mappings: list[CompetitionWikiMapping],
    ingestion_run_id: str,
    as_of_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ingestionRunId": ingestion_run_id,
        "asOfYear": as_of_year,
        "statCodes": [
            "most_points_single_season",
            "most_goals_single_season_team",
            "fewest_goals_conceded_single_season",
            "longest_unbeaten_run",
            "longest_winning_run",
            "biggest_win",
            "highest_scoring_match",
        ],
        "competitions": [],
    }
    headers = {"User-Agent": USER_AGENT}

    for mapping in mappings:
        source_url = mapping.wiki_records_url or mapping.wiki_main_url
        competition_summary: dict[str, Any] = {
            "competitionKey": mapping.competition_key,
            "sourceUrl": source_url,
            "rawTables": 0,
            "historicalRows": 0,
            "status": "pending",
        }
        try:
            response = requests.get(source_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="failed_fetch",
                    error_message=str(exc),
                    metadata={"statGroup": "team_match_records", "heuristics": TEAM_MATCH_RECORD_HEURISTICS},
                )
            competition_summary["status"] = "failed_fetch"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        try:
            tables = [flatten_columns(table) for table in pd.read_html(StringIO(response.text))]
        except ValueError as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="no_table",
                    error_message=str(exc),
                    metadata={"statGroup": "team_match_records", "heuristics": TEAM_MATCH_RECORD_HEURISTICS},
                )
            competition_summary["status"] = "no_table"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        all_rows: list[HistoricalStatRow] = []
        for table_index, table in enumerate(tables):
            payload = table_payload(table)
            record_rows = parse_team_match_records_table(
                mapping=mapping,
                table=table,
                table_index=table_index,
                source_url=source_url,
                ingestion_run_id=ingestion_run_id,
                as_of_year=as_of_year,
            )
            parse_status = "success" if record_rows else "unsupported_structure"
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=table_index,
                    table_caption=None,
                    payload_jsonb=payload,
                    parse_status=parse_status,
                    metadata={
                        "columns": list(table.columns),
                        "statGroup": "team_match_records",
                        "heuristics": TEAM_MATCH_RECORD_HEURISTICS,
                    },
                )
            competition_summary["rawTables"] += 1
            all_rows.extend(record_rows)

        all_rows = reduce_best_record_rows(all_rows)

        if not all_rows:
            competition_summary["status"] = "unsupported_structure"
        else:
            if not dry_run:
                replace_existing_rows(
                    conn,
                    competition_key=mapping.competition_key,
                    stat_codes=sorted({row.stat_code for row in all_rows}),
                    as_of_year=as_of_year,
                )
                upsert_historical_rows(conn, all_rows)
            competition_summary["historicalRows"] = len(all_rows)
            competition_summary["status"] = "success"

        summary["competitions"].append(competition_summary)

    return summary


def ingest_individual_records(
    conn: psycopg.Connection[Any],
    *,
    mappings: list[CompetitionWikiMapping],
    ingestion_run_id: str,
    as_of_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ingestionRunId": ingestion_run_id,
        "asOfYear": as_of_year,
        "statCodes": list(INDIVIDUAL_RECORD_HEURISTICS.keys()),
        "competitions": [],
    }
    headers = {"User-Agent": USER_AGENT}

    for mapping in mappings:
        source_urls = build_source_url_list(
            mapping.wiki_records_url,
            mapping.wiki_scorers_url,
            mapping.wiki_main_url,
        )
        competition_summary: dict[str, Any] = {
            "competitionKey": mapping.competition_key,
            "sourceUrl": source_urls[0],
            "rawTables": 0,
            "historicalRows": 0,
            "status": "pending",
        }

        all_rows: list[HistoricalStatRow] = []
        fetch_failed = False
        for source_url in source_urls:
            try:
                response = requests.get(source_url, headers=headers, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:
                if not dry_run:
                    insert_raw_table(
                        conn,
                        ingestion_run_id=ingestion_run_id,
                        competition_key=mapping.competition_key,
                        source_url=source_url,
                        table_index=None,
                        table_caption=None,
                        payload_jsonb=None,
                        parse_status="failed_fetch",
                        error_message=str(exc),
                        metadata={"statGroup": "player_records", "heuristics": INDIVIDUAL_RECORD_HEURISTICS},
                    )
                fetch_failed = True
                competition_summary["error"] = str(exc)
                continue

            try:
                tables = [flatten_columns(table) for table in pd.read_html(StringIO(response.text))]
            except ValueError as exc:
                if not dry_run:
                    insert_raw_table(
                        conn,
                        ingestion_run_id=ingestion_run_id,
                        competition_key=mapping.competition_key,
                        source_url=source_url,
                        table_index=None,
                        table_caption=None,
                        payload_jsonb=None,
                        parse_status="no_table",
                        error_message=str(exc),
                        metadata={"statGroup": "player_records", "heuristics": INDIVIDUAL_RECORD_HEURISTICS},
                    )
                competition_summary["error"] = str(exc)
                continue

            for table_index, table in enumerate(tables):
                payload = table_payload(table)
                record_rows = parse_individual_records_table(
                    mapping=mapping,
                    table=table,
                    table_index=table_index,
                    source_url=source_url,
                    ingestion_run_id=ingestion_run_id,
                    as_of_year=as_of_year,
                )
                parse_status = "success" if record_rows else "unsupported_structure"
                if not dry_run:
                    insert_raw_table(
                        conn,
                        ingestion_run_id=ingestion_run_id,
                        competition_key=mapping.competition_key,
                        source_url=source_url,
                        table_index=table_index,
                        table_caption=None,
                        payload_jsonb=payload,
                        parse_status=parse_status,
                        metadata={
                            "columns": list(table.columns),
                            "statGroup": "player_records",
                            "heuristics": INDIVIDUAL_RECORD_HEURISTICS,
                        },
                    )
                competition_summary["rawTables"] += 1
                all_rows.extend(record_rows)

        all_rows = reduce_best_record_rows(all_rows)

        if not all_rows:
            if fetch_failed and competition_summary.get("error"):
                competition_summary["status"] = "failed_fetch"
            else:
                competition_summary["status"] = "unsupported_structure"
        else:
            if not dry_run:
                replace_existing_rows(
                    conn,
                    competition_key=mapping.competition_key,
                    stat_codes=sorted({row.stat_code for row in all_rows}),
                    as_of_year=as_of_year,
                )
                upsert_historical_rows(conn, all_rows)
            competition_summary["historicalRows"] = len(all_rows)
            competition_summary["status"] = "success"

        summary["competitions"].append(competition_summary)

    return summary


def ingest_scorers(
    conn: psycopg.Connection[Any],
    *,
    mappings: list[CompetitionWikiMapping],
    ingestion_run_id: str,
    as_of_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ingestionRunId": ingestion_run_id,
        "asOfYear": as_of_year,
        "statCode": "all_time_top_scorers",
        "competitions": [],
    }
    headers = {"User-Agent": USER_AGENT}

    for mapping in mappings:
        source_url = mapping.wiki_scorers_url or mapping.wiki_main_url
        competition_summary: dict[str, Any] = {
            "competitionKey": mapping.competition_key,
            "sourceUrl": source_url,
            "rawTables": 0,
            "historicalRows": 0,
            "status": "pending",
        }
        try:
            response = requests.get(source_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="failed_fetch",
                    error_message=str(exc),
                    metadata={"statCode": "all_time_top_scorers"},
                )
            competition_summary["status"] = "failed_fetch"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        try:
            tables = [flatten_columns(table) for table in pd.read_html(StringIO(response.text))]
        except ValueError as exc:
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=None,
                    table_caption=None,
                    payload_jsonb=None,
                    parse_status="no_table",
                    error_message=str(exc),
                    metadata={"statCode": "all_time_top_scorers"},
                )
            competition_summary["status"] = "no_table"
            competition_summary["error"] = str(exc)
            summary["competitions"].append(competition_summary)
            continue

        all_rows: list[HistoricalStatRow] = []
        for table_index, table in enumerate(tables):
            payload = table_payload(table)
            scorer_rows = parse_scorers_table(
                mapping=mapping,
                table=table,
                table_index=table_index,
                source_url=source_url,
                ingestion_run_id=ingestion_run_id,
                as_of_year=as_of_year,
            )
            parse_status = "success" if scorer_rows else "unsupported_structure"
            if not dry_run:
                insert_raw_table(
                    conn,
                    ingestion_run_id=ingestion_run_id,
                    competition_key=mapping.competition_key,
                    source_url=source_url,
                    table_index=table_index,
                    table_caption=None,
                    payload_jsonb=payload,
                    parse_status=parse_status,
                    metadata={"columns": list(table.columns), "statCode": "all_time_top_scorers"},
                )
            competition_summary["rawTables"] += 1
            if scorer_rows and not all_rows:
                all_rows = scorer_rows

        if not all_rows:
            competition_summary["status"] = "unsupported_structure"
        else:
            if not dry_run:
                replace_existing_rows(
                    conn,
                    competition_key=mapping.competition_key,
                    stat_codes=sorted({row.stat_code for row in all_rows}),
                    as_of_year=as_of_year,
                )
                upsert_historical_rows(conn, all_rows)
            competition_summary["historicalRows"] = len(all_rows)
            competition_summary["status"] = "success"

        summary["competitions"].append(competition_summary)

    return summary


def resolve_team_ids(
    conn: psycopg.Connection[Any],
    *,
    as_of_year: int,
    dry_run: bool,
) -> dict[str, Any]:
    def normalize_resolution_name(value: Any) -> str:
        normalized = normalize_text(value).lower().replace("&", " and ")
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("munchen", "munich").replace("muenchen", "munich")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        tokens = [
            token
            for token in normalized.split()
            if token not in TEAM_RESOLUTION_STOPWORDS and not token.isdigit()
        ]
        return " ".join(tokens).strip()

    def build_resolution_keys(value: Any) -> set[str]:
        normalized = normalize_resolution_name(value)
        if normalized == "":
            return set()

        keys = {normalized}
        for group in TEAM_RESOLUTION_ALIAS_GROUPS:
            if normalized in group:
                keys.update(group)
        return keys

    before_null = conn.execute(
        """
        select count(*)
        from mart.competition_historical_stats
        where as_of_year = %s
          and entity_type = 'team'
          and entity_id is null
        """,
        [as_of_year],
    ).fetchone()[0]

    unresolved_names = conn.execute(
        """
        select distinct competition_key, entity_name
        from mart.competition_historical_stats
        where as_of_year = %s
          and entity_type = 'team'
          and entity_id is null
        """,
        [as_of_year],
    ).fetchall()

    teams = conn.execute(
        """
        select team_id, team_name
        from mart.dim_team
        where team_name is not null
        """,
    ).fetchall()

    usage_rows = conn.execute(
        """
        select competition_key, team_id, count(*)::int as match_count
        from (
          select competition_key, home_team_id as team_id
          from mart.fact_matches
          where home_team_id is not null
          union all
          select competition_key, away_team_id as team_id
          from mart.fact_matches
          where away_team_id is not null
        ) team_matches
        group by competition_key, team_id
        """,
    ).fetchall()

    usage_by_competition_team = {
        (str(row[0]), int(row[1])): int(row[2])
        for row in usage_rows
    }

    candidates_by_key: dict[str, list[tuple[int, str]]] = {}
    for row in teams:
        team_id = int(row[0])
        team_name = str(row[1])
        for key in build_resolution_keys(team_name):
            candidates_by_key.setdefault(key, []).append((team_id, team_name))

    resolutions: list[dict[str, Any]] = []
    ambiguous_names = 0

    for competition_key, entity_name in unresolved_names:
        candidate_map: dict[int, str] = {}
        for key in build_resolution_keys(entity_name):
            for team_id, team_name in candidates_by_key.get(key, []):
                candidate_map.setdefault(team_id, team_name)

        if not candidate_map:
            continue

        ranked_candidates = sorted(
            (
                (
                    usage_by_competition_team.get((str(competition_key), team_id), 0),
                    team_id,
                    team_name,
                )
                for team_id, team_name in candidate_map.items()
            ),
            key=lambda item: (-item[0], item[1]),
        )

        resolution_method: str | None = None
        selected_candidate: tuple[int, int, str] | None = None

        if len(ranked_candidates) == 1:
            selected_candidate = ranked_candidates[0]
            resolution_method = "normalized_team_name"
        elif (
            ranked_candidates[0][0] > 0
            and ranked_candidates[0][0] > ranked_candidates[1][0]
        ):
            selected_candidate = ranked_candidates[0]
            resolution_method = "competition_team_usage"
        else:
            ambiguous_names += 1
            continue

        resolutions.append(
            {
                "competitionKey": str(competition_key),
                "entityName": str(entity_name),
                "teamId": selected_candidate[1],
                "method": resolution_method,
            }
        )

    updated_rows: list[tuple[Any, ...]] = []
    if not dry_run:
        for resolution in resolutions:
            updated_rows.extend(
                conn.execute(
                    """
                    update mart.competition_historical_stats
                    set
                      entity_id = %s,
                      metadata = jsonb_set(
                        coalesce(metadata, '{}'::jsonb),
                        '{entityResolution}',
                        jsonb_build_object('method', %s::text, 'resolvedEntityId', %s),
                        true
                      ),
                      updated_at = now()
                    where competition_key = %s
                      and entity_name = %s
                      and as_of_year = %s
                      and entity_type = 'team'
                      and entity_id is null
                    returning competition_key, stat_code, entity_name, entity_id
                    """,
                    [
                        resolution["teamId"],
                        resolution["method"],
                        resolution["teamId"],
                        resolution["competitionKey"],
                        resolution["entityName"],
                        as_of_year,
                    ],
                ).fetchall()
            )
    else:
        updated_rows = [
            (
                resolution["competitionKey"],
                "dry_run",
                resolution["entityName"],
                resolution["teamId"],
            )
            for resolution in resolutions
        ]

    after_null = conn.execute(
        """
        select count(*)
        from mart.competition_historical_stats
        where as_of_year = %s
          and entity_type = 'team'
          and entity_id is null
        """,
        [as_of_year],
    ).fetchone()[0]

    return {
        "asOfYear": as_of_year,
        "beforeNullTeamEntityIds": int(before_null),
        "resolvedRows": len(updated_rows),
        "afterNullTeamEntityIds": int(after_null),
        "ambiguousNames": int(ambiguous_names),
        "sample": [
            {
                "competitionKey": row[0],
                "statCode": row[1],
                "entityName": row[2],
                "entityId": row[3],
            }
            for row in updated_rows[:20]
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Wikipedia historical competition statistics.")
    parser.add_argument("--dsn", default=None, help="Postgres DSN. Defaults to FOOTBALL_PG_DSN, DATABASE_URL or local defaults.")
    parser.add_argument("--competition-key", default=None, help="Optional competition_key filter.")
    parser.add_argument(
        "--stat",
        choices=("champions", "scorers", "team-match-records", "individual-records", "resolve-team-ids"),
        default="champions",
    )
    parser.add_argument("--as-of-year", type=int, default=AS_OF_YEAR)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    ingestion_run_id = f"wikipedia_historical_stats_{uuid.uuid4().hex}"
    dsn = resolve_pg_dsn(args.dsn)

    with psycopg.connect(dsn) as conn:
        mappings = fetch_mappings(conn, args.competition_key)
        if not mappings:
            print(
                json.dumps(
                    {
                        "ingestionRunId": ingestion_run_id,
                        "status": "no_active_mappings",
                        "competitionKey": args.competition_key,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1

        if args.stat == "resolve-team-ids":
            summary = resolve_team_ids(conn, as_of_year=args.as_of_year, dry_run=args.dry_run)
        elif args.stat == "champions":
            summary = ingest_champions(
                conn,
                mappings=mappings,
                ingestion_run_id=ingestion_run_id,
                as_of_year=args.as_of_year,
                dry_run=args.dry_run,
            )
        elif args.stat == "scorers":
            summary = ingest_scorers(
                conn,
                mappings=mappings,
                ingestion_run_id=ingestion_run_id,
                as_of_year=args.as_of_year,
                dry_run=args.dry_run,
            )
        elif args.stat == "team-match-records":
            summary = ingest_team_match_records(
                conn,
                mappings=mappings,
                ingestion_run_id=ingestion_run_id,
                as_of_year=args.as_of_year,
                dry_run=args.dry_run,
            )
        else:
            summary = ingest_individual_records(
                conn,
                mappings=mappings,
                ingestion_run_id=ingestion_run_id,
                as_of_year=args.as_of_year,
                dry_run=args.dry_run,
            )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
