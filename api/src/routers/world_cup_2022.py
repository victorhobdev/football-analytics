from __future__ import annotations

from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Request

from ..core.contracts import build_api_response, build_coverage_from_counts
from ..core.errors import AppError
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/world-cup-2022", tags=["world-cup-2022"])

WORLD_CUP_PROVIDER = "world_cup_2022"
WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens"
WORLD_CUP_SEASON_LABEL = "2022"
WORLD_CUP_EDITION_KEY = "fifa_world_cup_mens__2022"
WORLD_CUP_COMPETITION_NAME = "FIFA Men's World Cup"
WORLD_CUP_SEASON_NAME = "2022 FIFA Men's World Cup"
EXPECTED_FIXTURES = 64
EXPECTED_STANDINGS_ROWS = 32


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _parse_required_bigint(raw_value: str, *, field_name: str) -> int:
    try:
        return int(raw_value)
    except ValueError as exc:
        raise AppError(
            message=f"Invalid value for '{field_name}'. Expected integer-compatible identifier.",
            code="INVALID_QUERY_PARAM",
            status=400,
            details={field_name: raw_value},
        ) from exc


def _competition_payload() -> dict[str, Any]:
    return {
        "provider": WORLD_CUP_PROVIDER,
        "competitionKey": WORLD_CUP_COMPETITION_KEY,
        "competitionName": WORLD_CUP_COMPETITION_NAME,
        "seasonLabel": WORLD_CUP_SEASON_LABEL,
        "seasonName": WORLD_CUP_SEASON_NAME,
        "editionKey": WORLD_CUP_EDITION_KEY,
    }


def _fixture_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixtureId": str(row["fixture_id"]),
        "kickoffAt": row.get("date_utc"),
        "statusShort": row.get("status_short"),
        "statusLong": row.get("status_long"),
        "stageName": row.get("stage_name"),
        "groupName": row.get("group_name"),
        "roundName": row.get("round_name"),
        "venueName": row.get("venue_name"),
        "venueCity": row.get("venue_city"),
        "referee": row.get("referee"),
        "homeTeamId": str(row["home_team_id"]),
        "homeTeamName": row.get("home_team_name"),
        "awayTeamId": str(row["away_team_id"]),
        "awayTeamName": row.get("away_team_name"),
        "homeGoals": row.get("home_goals"),
        "awayGoals": row.get("away_goals"),
        "sourceProvider": row.get("source_provider"),
    }


def _fetch_world_cup_fixtures() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        SELECT
            fixture_id,
            date_utc,
            status_short,
            status_long,
            stage_name,
            group_name,
            round_name,
            venue_name,
            venue_city,
            referee,
            home_team_id,
            home_team_name,
            away_team_id,
            away_team_name,
            home_goals,
            away_goals,
            source_provider
        FROM raw.fixtures
        WHERE provider = %s
          AND competition_key = %s
          AND season_label = %s
        ORDER BY date_utc ASC, fixture_id ASC;
        """,
        [WORLD_CUP_PROVIDER, WORLD_CUP_COMPETITION_KEY, WORLD_CUP_SEASON_LABEL],
    )


def _fetch_world_cup_standings_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        SELECT
            round_id,
            stage_id,
            team_id,
            position,
            points,
            games_played,
            won,
            draw,
            lost,
            goals_for,
            goals_against,
            goal_diff,
            payload->>'stage_key' AS stage_key,
            payload->>'group_key' AS group_key,
            payload->>'team_name' AS team_name,
            payload->>'team_code' AS team_code,
            payload->>'advanced' AS advanced
        FROM raw.standings_snapshots
        WHERE provider = %s
          AND competition_key = %s
          AND season_label = %s
        ORDER BY payload->>'group_key' ASC, position ASC, team_id ASC;
        """,
        [WORLD_CUP_PROVIDER, WORLD_CUP_COMPETITION_KEY, WORLD_CUP_SEASON_LABEL],
    )


def _group_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in rows:
        group_key = row.get("group_key") or str(row.get("round_id"))
        group = grouped.setdefault(
            group_key,
            {
                "groupKey": group_key,
                "groupName": f"Group {group_key}" if len(group_key) == 1 else group_key,
                "stageKey": row.get("stage_key"),
                "rows": [],
            },
        )
        group["rows"].append(
            {
                "teamId": str(row["team_id"]),
                "teamName": row.get("team_name"),
                "teamCode": row.get("team_code"),
                "position": int(row.get("position") or 0),
                "points": int(row.get("points") or 0),
                "matchesPlayed": int(row.get("games_played") or 0),
                "wins": int(row.get("won") or 0),
                "draws": int(row.get("draw") or 0),
                "losses": int(row.get("lost") or 0),
                "goalsFor": int(row.get("goals_for") or 0),
                "goalsAgainst": int(row.get("goals_against") or 0),
                "goalDiff": int(row.get("goal_diff") or 0),
                "advanced": str(row.get("advanced")).lower() == "true",
            }
        )
    return list(grouped.values())


def _lineups_coverage(lineup_groups: list[dict[str, Any]]) -> dict[str, Any]:
    if not lineup_groups:
        return {"status": "empty", "label": "Lineups coverage", "percentage": 0}

    team_count = len(lineup_groups)
    starters = sum(len(group["starters"]) for group in lineup_groups)
    if team_count == 2 and starters == 22:
        return {"status": "complete", "label": "Lineups coverage", "percentage": 100}

    team_ratio = min(team_count, 2) / 2
    starter_ratio = min(starters, 22) / 22
    return {
        "status": "partial",
        "label": "Lineups coverage",
        "percentage": round(((team_ratio + starter_ratio) / 2) * 100, 2),
    }


def _events_coverage(event_count: int) -> dict[str, Any]:
    if event_count <= 0:
        return {"status": "empty", "label": "Events coverage", "percentage": 0}
    return {"status": "complete", "label": "Events coverage", "percentage": 100}


def _merge_coverages(label: str, coverages: list[dict[str, Any]]) -> dict[str, Any]:
    if not coverages:
        return {"status": "unknown", "label": label}

    percentages = [float(coverage.get("percentage") or 0) for coverage in coverages]
    if all(coverage.get("status") == "complete" for coverage in coverages):
        status = "complete"
    elif all(coverage.get("status") == "empty" for coverage in coverages):
        status = "empty"
    else:
        status = "partial"

    return {
        "status": status,
        "label": label,
        "percentage": round(sum(percentages) / len(percentages), 2),
    }


def _fetch_match_fixture(fixture_id: int) -> dict[str, Any] | None:
    return db_client.fetch_one(
        """
        SELECT
            fixture_id,
            date_utc,
            status_short,
            status_long,
            stage_name,
            group_name,
            round_name,
            venue_name,
            venue_city,
            referee,
            home_team_id,
            home_team_name,
            away_team_id,
            away_team_name,
            home_goals,
            away_goals,
            source_provider
        FROM raw.fixtures
        WHERE provider = %s
          AND competition_key = %s
          AND season_label = %s
          AND fixture_id = %s
        LIMIT 1;
        """,
        [WORLD_CUP_PROVIDER, WORLD_CUP_COMPETITION_KEY, WORLD_CUP_SEASON_LABEL, fixture_id],
    )


def _fetch_match_lineups(fixture_id: int) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        SELECT
            l.fixture_id,
            l.team_id,
            CASE
                WHEN l.team_id = f.home_team_id THEN f.home_team_name
                WHEN l.team_id = f.away_team_id THEN f.away_team_name
                ELSE NULL
            END AS team_name,
            l.player_id,
            l.lineup_id,
            l.position_name,
            l.lineup_type_id,
            l.formation_field,
            l.formation_position,
            l.jersey_number,
            l.details,
            l.payload->>'player_internal_id' AS player_internal_id,
            l.payload #>> '{source_payload,player_name}' AS player_name,
            l.payload #>> '{source_payload,player_nickname}' AS player_nickname,
            l.payload->>'source_name' AS source_name,
            l.payload->>'source_version' AS source_version
        FROM raw.fixture_lineups l
        JOIN raw.fixtures f
          ON f.fixture_id = l.fixture_id
         AND f.provider = %s
         AND f.competition_key = %s
         AND f.season_label = %s
        WHERE l.provider = %s
          AND l.competition_key = %s
          AND l.season_label = %s
          AND l.fixture_id = %s
        ORDER BY
            l.team_id ASC,
            l.lineup_type_id ASC,
            l.formation_position ASC NULLS LAST,
            l.jersey_number ASC NULLS LAST,
            l.lineup_id ASC;
        """,
        [
            WORLD_CUP_PROVIDER,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_SEASON_LABEL,
            WORLD_CUP_PROVIDER,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_SEASON_LABEL,
            fixture_id,
        ],
    )


def _serialize_match_lineups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in rows:
        team_id = str(row["team_id"])
        group = grouped.setdefault(
            team_id,
            {
                "teamId": team_id,
                "teamName": row.get("team_name"),
                "starters": [],
                "bench": [],
            },
        )
        player_payload = {
            "lineupId": str(row["lineup_id"]),
            "playerId": str(row["player_id"]),
            "playerInternalId": row.get("player_internal_id"),
            "playerName": row.get("player_name"),
            "playerNickname": row.get("player_nickname"),
            "positionName": row.get("position_name"),
            "formationField": row.get("formation_field"),
            "formationPosition": row.get("formation_position"),
            "jerseyNumber": row.get("jersey_number"),
            "details": row.get("details"),
            "sourceName": row.get("source_name"),
            "sourceVersion": row.get("source_version"),
        }
        if int(row.get("lineup_type_id") or 0) == 1:
            group["starters"].append(player_payload)
        else:
            group["bench"].append(player_payload)
    return list(grouped.values())


def _fetch_match_events(fixture_id: int) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        SELECT
            fixture_id,
            internal_match_id,
            source_name,
            source_version,
            source_match_id,
            source_event_id,
            event_index,
            team_internal_id,
            player_internal_id,
            event_type,
            period,
            minute,
            second,
            location_x,
            location_y,
            outcome_label,
            play_pattern_label,
            is_three_sixty_backed,
            event_payload,
            event_payload #>> '{team,name}' AS team_name,
            event_payload #>> '{player,name}' AS player_name
        FROM raw.wc_match_events
        WHERE edition_key = %s
          AND fixture_id = %s
        ORDER BY event_index ASC, source_event_id ASC;
        """,
        [WORLD_CUP_EDITION_KEY, fixture_id],
    )


def _fetch_world_cup_team(team_id: int) -> dict[str, Any] | None:
    return db_client.fetch_one(
        """
        SELECT team_id, team_name
        FROM (
            SELECT home_team_id AS team_id, home_team_name AS team_name
            FROM raw.fixtures
            WHERE provider = %s
              AND competition_key = %s
              AND season_label = %s
            UNION
            SELECT away_team_id AS team_id, away_team_name AS team_name
            FROM raw.fixtures
            WHERE provider = %s
              AND competition_key = %s
              AND season_label = %s
        ) teams
        WHERE team_id = %s
        LIMIT 1;
        """,
        [
            WORLD_CUP_PROVIDER,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_SEASON_LABEL,
            WORLD_CUP_PROVIDER,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_SEASON_LABEL,
            team_id,
        ],
    )


def _fetch_team_coach(team_id: int) -> dict[str, Any] | None:
    return db_client.fetch_one(
        """
        SELECT
            coach_tenure_id,
            team_id,
            payload->>'source_manager_id' AS coach_source_scoped_id,
            payload->>'given_name' AS given_name,
            payload->>'family_name' AS family_name,
            payload->>'country_name' AS country_name,
            payload->>'coach_identity_scope' AS coach_identity_scope,
            payload->>'coach_tenure_scope' AS coach_tenure_scope,
            payload->>'source_name' AS source_name,
            payload->>'source_version' AS source_version
        FROM raw.team_coaches
        WHERE provider = %s
          AND team_id = %s
        LIMIT 1;
        """,
        [WORLD_CUP_PROVIDER, team_id],
    )


def _fetch_team_fixtures(team_id: int) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        SELECT
            fixture_id,
            date_utc,
            status_short,
            status_long,
            stage_name,
            group_name,
            round_name,
            venue_name,
            venue_city,
            referee,
            home_team_id,
            home_team_name,
            away_team_id,
            away_team_name,
            home_goals,
            away_goals,
            source_provider,
            CASE WHEN home_team_id = %s THEN 'home' ELSE 'away' END AS venue_role,
            CASE WHEN home_team_id = %s THEN away_team_id ELSE home_team_id END AS opponent_team_id,
            CASE WHEN home_team_id = %s THEN away_team_name ELSE home_team_name END AS opponent_team_name
        FROM raw.fixtures
        WHERE provider = %s
          AND competition_key = %s
          AND season_label = %s
          AND (%s IN (home_team_id, away_team_id))
        ORDER BY date_utc ASC, fixture_id ASC;
        """,
        [
            team_id,
            team_id,
            team_id,
            WORLD_CUP_PROVIDER,
            WORLD_CUP_COMPETITION_KEY,
            WORLD_CUP_SEASON_LABEL,
            team_id,
        ],
    )


@router.get("/competition-hub")
def get_world_cup_2022_competition_hub(request: Request) -> dict[str, Any]:
    fixture_rows = _fetch_world_cup_fixtures()
    standings_rows = _fetch_world_cup_standings_rows()
    standings_groups = _group_standings(standings_rows)

    data = {
        "competition": _competition_payload(),
        "fixtures": [_fixture_item(row) for row in fixture_rows],
        "standings": {
            "groupCount": len(standings_groups),
            "rowCount": len(standings_rows),
            "groups": standings_groups,
        },
    }
    coverage = build_coverage_from_counts(
        len(fixture_rows) + len(standings_rows),
        EXPECTED_FIXTURES + EXPECTED_STANDINGS_ROWS,
        "World Cup 2022 competition hub coverage",
    )
    return build_api_response(data, request_id=_request_id(request), coverage=coverage)


@router.get("/matches/{fixtureId}")
def get_world_cup_2022_match_view(fixtureId: str, request: Request) -> dict[str, Any]:
    fixture_id = _parse_required_bigint(fixtureId, field_name="fixtureId")
    fixture_row = _fetch_match_fixture(fixture_id)
    if fixture_row is None:
        raise AppError(
            message="World Cup 2022 fixture not found.",
            code="MATCH_NOT_FOUND",
            status=404,
            details={"fixtureId": fixtureId},
        )

    lineups = _serialize_match_lineups(_fetch_match_lineups(fixture_id))
    events = [
        {
            "fixtureId": str(row["fixture_id"]),
            "internalMatchId": row.get("internal_match_id"),
            "sourceName": row.get("source_name"),
            "sourceVersion": row.get("source_version"),
            "sourceMatchId": row.get("source_match_id"),
            "sourceEventId": row.get("source_event_id"),
            "eventIndex": row.get("event_index"),
            "eventType": row.get("event_type"),
            "period": row.get("period"),
            "minute": row.get("minute"),
            "second": float(row["second"]) if row.get("second") is not None else None,
            "location": {
                "x": float(row["location_x"]) if row.get("location_x") is not None else None,
                "y": float(row["location_y"]) if row.get("location_y") is not None else None,
            },
            "outcomeLabel": row.get("outcome_label"),
            "playPatternLabel": row.get("play_pattern_label"),
            "isThreeSixtyBacked": bool(row.get("is_three_sixty_backed")),
            "team": {
                "teamInternalId": row.get("team_internal_id"),
                "teamName": row.get("team_name"),
            },
            "player": {
                "playerInternalId": row.get("player_internal_id"),
                "playerName": row.get("player_name"),
            },
            "payload": row.get("event_payload"),
        }
        for row in _fetch_match_events(fixture_id)
    ]

    lineups_coverage = _lineups_coverage(lineups)
    events_coverage = _events_coverage(len(events))
    data = {
        "competition": _competition_payload(),
        "fixture": _fixture_item(fixture_row),
        "lineups": lineups,
        "events": events,
        "sectionCoverage": {
            "lineups": lineups_coverage,
            "events": events_coverage,
        },
    }
    coverage = _merge_coverages("World Cup 2022 match view coverage", [lineups_coverage, events_coverage])
    return build_api_response(data, request_id=_request_id(request), coverage=coverage)


@router.get("/teams/{teamId}")
def get_world_cup_2022_team_view(teamId: str, request: Request) -> dict[str, Any]:
    team_id = _parse_required_bigint(teamId, field_name="teamId")
    team_row = _fetch_world_cup_team(team_id)
    if team_row is None:
        raise AppError(
            message="World Cup 2022 team not found.",
            code="TEAM_NOT_FOUND",
            status=404,
            details={"teamId": teamId},
        )

    coach_row = _fetch_team_coach(team_id)
    fixture_rows = _fetch_team_fixtures(team_id)
    coach_payload = None
    if coach_row is not None:
        full_name = " ".join(
            [part for part in [coach_row.get("given_name"), coach_row.get("family_name")] if part]
        ).strip() or None
        coach_payload = {
            "coachTenureId": str(coach_row["coach_tenure_id"]),
            "coachSourceScopedId": coach_row.get("coach_source_scoped_id"),
            "fullName": full_name,
            "givenName": coach_row.get("given_name"),
            "familyName": coach_row.get("family_name"),
            "countryName": coach_row.get("country_name"),
            "identityScope": coach_row.get("coach_identity_scope"),
            "tenureScope": coach_row.get("coach_tenure_scope"),
            "sourceName": coach_row.get("source_name"),
            "sourceVersion": coach_row.get("source_version"),
        }

    fixture_items = []
    for row in fixture_rows:
        item = _fixture_item(row)
        item["venueRole"] = row.get("venue_role")
        item["opponentTeamId"] = str(row["opponent_team_id"])
        item["opponentTeamName"] = row.get("opponent_team_name")
        fixture_items.append(item)

    coach_coverage = build_coverage_from_counts(1 if coach_payload is not None else 0, 1, "Coach coverage")
    fixtures_coverage = build_coverage_from_counts(len(fixture_items), len(fixture_items), "Team fixtures coverage")
    data = {
        "competition": _competition_payload(),
        "team": {
            "teamId": str(team_row["team_id"]),
            "teamName": team_row.get("team_name"),
            "matchesPlayed": len(fixture_items),
        },
        "coach": coach_payload,
        "fixtures": fixture_items,
        "sectionCoverage": {
            "coach": coach_coverage,
            "fixtures": fixtures_coverage,
        },
    }
    coverage = _merge_coverages("World Cup 2022 team view coverage", [coach_coverage, fixtures_coverage])
    return build_api_response(data, request_id=_request_id(request), coverage=coverage)
