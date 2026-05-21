from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..core.context_registry import (
    build_canonical_context,
    get_canonical_competition,
    list_canonical_competition_ids,
)
from ..core.contracts import build_api_response, build_coverage_from_counts
from ..db.client import db_client

router = APIRouter(prefix="/api/v1/home", tags=["home"])

_HOME_SECTION_COUNT = 3


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _to_int(value: Any) -> int:
    return int(value or 0)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _format_competition_coverage(
    *,
    matches_count: int,
    match_statistics_count: int,
    lineups_count: int,
    events_count: int,
    player_statistics_count: int,
) -> dict[str, Any]:
    component_counts = (
        match_statistics_count,
        lineups_count,
        events_count,
        player_statistics_count,
    )

    if matches_count <= 0:
        return build_coverage_from_counts(0, 0, "Competition depth coverage")

    if max(component_counts) <= 0:
        return build_coverage_from_counts(0, matches_count, "Competition depth coverage")

    aggregated_available = max(
        1,
        round(
            sum(min(count, matches_count) / matches_count for count in component_counts)
            / len(component_counts)
            * matches_count
        ),
    )

    return build_coverage_from_counts(
        aggregated_available,
        matches_count,
        "Competition depth coverage",
    )


def _build_home_coverage(
    *,
    archive_summary: dict[str, Any],
    competitions: list[dict[str, Any]],
    editorial_highlights: list[dict[str, Any]],
) -> dict[str, Any]:
    available_sections = 0

    if _to_int(archive_summary.get("matches")) > 0:
        available_sections += 1
    if competitions:
        available_sections += 1
    if editorial_highlights:
        available_sections += 1

    return build_coverage_from_counts(available_sections, _HOME_SECTION_COUNT, "Home coverage")


def _fetch_archive_summary() -> dict[str, Any]:
    row = db_client.fetch_one(
        """
        select
            (select count(distinct league_id) from mart.fact_matches) as competitions,
            (select count(distinct (league_id, season)) from mart.fact_matches) as seasons,
            (select count(*) from mart.fact_matches) as matches,
            (select count(distinct player_id) from mart.dim_player) as players;
        """
    ) or {}

    return {
        "competitions": _to_int(row.get("competitions")),
        "seasons": _to_int(row.get("seasons")),
        "matches": _to_int(row.get("matches")),
        "players": _to_int(row.get("players")),
    }


def _fetch_competitions() -> list[dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        with match_totals as (
            select
                fm.league_id,
                count(distinct fm.match_id)::int as matches_count,
                count(distinct fm.season)::int as seasons_count,
                min(fm.season)::int as min_season,
                max(fm.season)::int as max_season
            from mart.fact_matches fm
            group by fm.league_id
        ),
        match_statistics as (
            select
                rf.league_id,
                count(distinct ms.fixture_id)::int as available_count
            from raw.match_statistics ms
            inner join raw.fixtures rf
              on rf.fixture_id = ms.fixture_id
            group by rf.league_id
        ),
        fixture_lineups as (
            select
                rf.league_id,
                count(distinct fl.fixture_id)::int as available_count
            from raw.fixture_lineups fl
            inner join raw.fixtures rf
              on rf.fixture_id = fl.fixture_id
            group by rf.league_id
        ),
        match_events as (
            select
                rf.league_id,
                count(distinct me.fixture_id)::int as available_count
            from raw.match_events me
            inner join raw.fixtures rf
              on rf.fixture_id = me.fixture_id
            group by rf.league_id
        ),
        fixture_player_statistics as (
            select
                rf.league_id,
                count(distinct fps.fixture_id)::int as available_count
            from raw.fixture_player_statistics fps
            inner join raw.fixtures rf
              on rf.fixture_id = fps.fixture_id
            group by rf.league_id
        ),
        competition_names as (
            select distinct on (dc.league_id)
                dc.league_id,
                dc.league_name
            from mart.dim_competition dc
            order by dc.league_id, dc.updated_at desc nulls last
        )
        select
            mt.league_id,
            cn.league_name,
            mt.matches_count,
            mt.seasons_count,
            mt.min_season,
            mt.max_season,
            coalesce(ms.available_count, 0) as match_statistics_count,
            coalesce(fl.available_count, 0) as lineups_count,
            coalesce(me.available_count, 0) as events_count,
            coalesce(fps.available_count, 0) as player_statistics_count
        from match_totals mt
        left join competition_names cn
          on cn.league_id = mt.league_id
        left join match_statistics ms
          on ms.league_id = mt.league_id
        left join fixture_lineups fl
          on fl.league_id = mt.league_id
        left join match_events me
          on me.league_id = mt.league_id
        left join fixture_player_statistics fps
          on fps.league_id = mt.league_id
        order by mt.league_id asc;
        """
    )

    merged_rows: dict[int, dict[str, Any]] = {}
    competition_order = {
        competition_id: index
        for index, competition_id in enumerate(list_canonical_competition_ids())
    }

    for row in rows:
        league_id = row.get("league_id")
        if league_id is None:
            continue

        canonical_competition = get_canonical_competition(int(league_id))
        if canonical_competition is None:
            continue

        bucket = merged_rows.setdefault(
            canonical_competition.competition_id,
            {
                "competitionId": str(canonical_competition.competition_id),
                "competitionKey": canonical_competition.competition_key,
                "competitionName": canonical_competition.default_name,
                "assetId": None,
                "matchesCount": 0,
                "seasonsCount": 0,
                "minSeason": None,
                "maxSeason": None,
                "matchStatisticsCount": 0,
                "lineupsCount": 0,
                "eventsCount": 0,
                "playerStatisticsCount": 0,
            },
        )

        bucket["matchesCount"] += _to_int(row.get("matches_count"))
        bucket["seasonsCount"] += _to_int(row.get("seasons_count"))
        bucket["matchStatisticsCount"] += _to_int(row.get("match_statistics_count"))
        bucket["lineupsCount"] += _to_int(row.get("lineups_count"))
        bucket["eventsCount"] += _to_int(row.get("events_count"))
        bucket["playerStatisticsCount"] += _to_int(row.get("player_statistics_count"))

        min_season = row.get("min_season")
        max_season = row.get("max_season")
        if isinstance(min_season, int):
            bucket["minSeason"] = (
                min_season
                if bucket["minSeason"] is None
                else min(bucket["minSeason"], min_season)
            )
        if isinstance(max_season, int):
            bucket["maxSeason"] = (
                max_season
                if bucket["maxSeason"] is None
                else max(bucket["maxSeason"], max_season)
            )

        if bucket["assetId"] is None:
            bucket["assetId"] = str(league_id)

    payload: list[dict[str, Any]] = []
    for competition in sorted(
        merged_rows.values(),
        key=lambda item: competition_order.get(int(item["competitionId"]), 999),
    ):
        min_season = competition["minSeason"]
        max_season = competition["maxSeason"]
        from_context = (
            build_canonical_context(
                competition_id=int(competition["competitionId"]),
                competition_name=competition["competitionName"],
                season_id=min_season,
            )
            if min_season is not None
            else None
        )
        latest_context = (
            build_canonical_context(
                competition_id=int(competition["competitionId"]),
                competition_name=competition["competitionName"],
                season_id=max_season,
            )
            if max_season is not None
            else None
        )

        payload.append(
            {
                "competitionId": competition["competitionId"],
                "competitionKey": competition["competitionKey"],
                "competitionName": competition["competitionName"],
                "assetId": competition["assetId"],
                "matchesCount": competition["matchesCount"],
                "seasonsCount": competition["seasonsCount"],
                "range": {
                    "fromSeasonId": str(min_season) if min_season is not None else None,
                    "fromSeasonLabel": from_context["seasonLabel"] if from_context else None,
                    "toSeasonId": str(max_season) if max_season is not None else None,
                    "toSeasonLabel": latest_context["seasonLabel"] if latest_context else None,
                },
                "latestContext": latest_context,
                "coverage": _format_competition_coverage(
                    matches_count=_to_int(competition["matchesCount"]),
                    match_statistics_count=_to_int(competition["matchStatisticsCount"]),
                    lineups_count=_to_int(competition["lineupsCount"]),
                    events_count=_to_int(competition["eventsCount"]),
                    player_statistics_count=_to_int(competition["playerStatisticsCount"]),
                ),
            }
        )

    return payload


def _build_editorial_title(player_name: str, competition_name: str) -> str:
    return f"{player_name}: o pico recente de {competition_name}"


def _build_editorial_description(row: dict[str, Any], team_name: str | None) -> str:
    fragments = [
        f"{_to_int(row.get('matches_played'))} jogos",
        f"{_to_int(row.get('goals'))} gols",
        f"{_to_int(row.get('assists'))} assistências",
    ]
    rating = _to_float(row.get("rating"))
    if rating is not None:
        fragments.append(f"rating {rating:.2f}")

    sentence = ", ".join(fragments)
    if team_name:
        return f"{sentence} por {team_name} no recorte selecionado."
    return f"{sentence} no recorte selecionado."


def _fetch_editorial_highlights() -> list[dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        with candidate_contexts(slot, league_id, season) as (
            values
                (1, 2, 2024),
                (2, 1122, 2024),
                (3, 82, 2024),
                (4, 648, 2024)
        ),
        ranked_players as (
            select
                cc.slot,
                cc.league_id,
                cc.season,
                dc.league_name,
                pms.player_id,
                pms.player_name,
                pms.team_id,
                pms.team_name,
                count(distinct pms.match_id)::int as matches_played,
                sum(coalesce(pms.goals, 0))::numeric as goals,
                sum(coalesce(pms.assists, 0))::numeric as assists,
                avg(pms.rating)::numeric as rating,
                max(pms.match_date) as last_match_date,
                row_number() over (
                    partition by cc.slot
                    order by
                        avg(pms.rating) desc nulls last,
                        sum(coalesce(pms.goals, 0)) desc,
                        sum(coalesce(pms.assists, 0)) desc,
                        count(distinct pms.match_id) desc,
                        pms.player_name asc
                ) as player_rank
            from candidate_contexts cc
            inner join mart.dim_competition dc
              on dc.league_id = cc.league_id
            inner join mart.player_match_summary pms
              on pms.competition_sk = dc.competition_sk
             and pms.season = cc.season
            group by
                cc.slot,
                cc.league_id,
                cc.season,
                dc.league_name,
                pms.player_id,
                pms.player_name,
                pms.team_id,
                pms.team_name
        )
        select
            slot,
            league_id,
            league_name,
            season,
            player_id,
            player_name,
            team_id,
            team_name,
            matches_played,
            goals,
            assists,
            rating,
            last_match_date
        from ranked_players
        where player_rank = 1
        order by slot asc
        limit 2;
        """
    )

    highlights: list[dict[str, Any]] = []
    for row in rows:
        canonical_context = build_canonical_context(
            competition_id=row.get("league_id"),
            competition_name=row.get("league_name"),
            season_id=row.get("season"),
        )
        if canonical_context is None:
            continue

        player_name = str(row.get("player_name") or "Jogador em destaque")
        team_name = row.get("team_name")
        highlights.append(
            {
                "id": f"highlight-{row.get('slot')}",
                "eyebrow": "Curadoria de dados reais",
                "competitionLabel": f"{canonical_context['competitionName']} · {canonical_context['seasonLabel']}",
                "title": _build_editorial_title(player_name, canonical_context["competitionName"]),
                "description": _build_editorial_description(row, team_name if isinstance(team_name, str) else None),
                "playerId": str(row["player_id"]),
                "playerName": player_name,
                "teamId": str(row["team_id"]) if row.get("team_id") is not None else None,
                "teamName": team_name,
                "imageAssetId": str(row["player_id"]),
                "context": canonical_context,
                "metrics": {
                    "matchesPlayed": _to_int(row.get("matches_played")),
                    "goals": _to_int(row.get("goals")),
                    "assists": _to_int(row.get("assists")),
                    "rating": _to_float(row.get("rating")),
                },
            }
        )

    return highlights


@router.get("")
def get_home_page(request: Request) -> dict[str, Any]:
    archive_summary = _fetch_archive_summary()
    competitions = _fetch_competitions()
    editorial_highlights = _fetch_editorial_highlights()

    return build_api_response(
        {
            "archiveSummary": archive_summary,
            "competitions": competitions,
            "editorialHighlights": editorial_highlights,
        },
        request_id=_request_id(request),
        coverage=_build_home_coverage(
            archive_summary=archive_summary,
            competitions=competitions,
            editorial_highlights=editorial_highlights,
        ),
    )
