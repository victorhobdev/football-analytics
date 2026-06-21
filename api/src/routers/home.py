from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..core.context_registry import (
    build_canonical_context,
    get_canonical_competition_by_key,
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


def _infer_competition_catalog_metadata(
    competition_key: str,
    competition_name: str,
    catalog_row: dict[str, Any] | None = None,
) -> dict[str, str]:
    if catalog_row is not None:
        competition_type = str(catalog_row.get("competition_type") or "").strip().lower()
        country = str(catalog_row.get("country_name") or "").strip() or "Mundo"
        confederation = str(catalog_row.get("confederation_name") or "").strip().upper()
        region_map = {
            "AFC": "Ásia",
            "CAF": "África",
            "CONCACAF": "América do Norte",
            "CONMEBOL": "América do Sul",
            "FIFA": "Global",
            "UEFA": "Europa",
        }
        region = region_map.get(confederation, "Global")

        if competition_type == "league":
            return {
                "country": country,
                "region": region,
                "scope": "domestic",
                "type": "domestic_league",
            }

        if competition_type == "continental_cup":
            return {
                "country": country if country not in {"", "Mundo"} else region,
                "region": region,
                "scope": "continental",
                "type": "international_cup",
            }

        if competition_type == "cup":
            scope = "global" if confederation == "FIFA" or country == "Mundo" else "domestic"
            return {
                "country": country,
                "region": region,
                "scope": scope,
                "type": "international_cup" if scope == "global" else "domestic_cup",
            }

        if confederation == "FIFA" or country == "Mundo":
            return {
                "country": "Mundo",
                "region": "Global",
                "scope": "global",
                "type": "international_cup",
            }

        return {
            "country": country,
            "region": region,
            "scope": "domestic",
            "type": "domestic_cup",
        }

    normalized = f"{competition_key} {competition_name}".lower()

    women_markers = ("women", "womens", "feminina", "feminino", "frauen", "nwsl", "liga_f")
    is_women = any(marker in normalized for marker in women_markers)

    region = "Global"
    country = "Mundo"
    scope = "continental"
    competition_type = "international_cup"

    if competition_key in {
        "brasileirao_a",
        "brasileirao_b",
        "copa_do_brasil",
        "supercopa_do_brasil",
    }:
        region = "América do Sul"
        country = "Brasil"
        scope = "domestic"
        competition_type = "domestic_cup" if "copa" in competition_key else "domestic_league"
    elif competition_key in {"premier_league", "fa_womens_super_league"}:
        region = "Europa"
        country = "Inglaterra"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key in {"la_liga", "copa_del_rey", "liga_f"}:
        region = "Europa"
        country = "Espanha"
        scope = "domestic"
        competition_type = "domestic_cup" if competition_key == "copa_del_rey" else "domestic_league"
    elif competition_key in {"serie_a_it", "serie_a_women"}:
        region = "Europa"
        country = "Itália"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key in {"bundesliga", "frauen_bundesliga"}:
        region = "Europa"
        country = "Alemanha"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key == "ligue_1":
        region = "Europa"
        country = "França"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key == "primeira_liga":
        region = "Europa"
        country = "Portugal"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key in {"major_league_soccer", "nwsl", "north_american_league"}:
        region = "América do Norte"
        country = "Estados Unidos"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key == "liga_profesional_argentina":
        region = "América do Sul"
        country = "Argentina"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key == "indian_super_league":
        region = "Ásia"
        country = "Índia"
        scope = "domestic"
        competition_type = "domestic_league"
    elif competition_key in {
        "champions_league",
        "uefa_europa_league",
        "uefa_euro",
        "uefa_womens_euro",
    }:
        region = "Europa"
        country = "Europa"
        scope = "continental"
        competition_type = "international_cup"
    elif competition_key in {"libertadores", "sudamericana", "copa_america"}:
        region = "América do Sul"
        country = "América do Sul"
        scope = "continental"
        competition_type = "international_cup"
    elif competition_key == "african_cup_of_nations":
        region = "África"
        country = "África"
        scope = "continental"
        competition_type = "international_cup"
    elif competition_key in {
        "fifa_world_cup_mens",
        "fifa_womens_world_cup",
        "fifa_u20_world_cup",
        "fifa_intercontinental_cup",
    }:
        region = "Global"
        country = "Mundo"
        scope = "global"
        competition_type = "international_cup"

    if is_women and country == "Mundo":
        country = "Mundo"

    return {
        "country": country,
        "region": region,
        "scope": scope,
        "type": competition_type,
    }


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
        with world_cup_presence as (
            select
                exists (
                    select 1
                    from raw.fixtures
                    where competition_key = 'fifa_world_cup_mens'
                    limit 1
                ) as has_world_cup,
                exists (
                    select 1
                    from mart.fact_matches
                    where competition_key = 'fifa_world_cup_mens'
                    limit 1
                ) as has_world_cup_in_fact
        )
        select
            (select count(distinct competition_key) from mart.fact_matches where competition_key is not null)
                + case
                    when wp.has_world_cup and not wp.has_world_cup_in_fact then 1
                    else 0
                  end as competitions,
            (select count(distinct (competition_key, season)) from mart.fact_matches where competition_key is not null)
                + case
                    when wp.has_world_cup and not wp.has_world_cup_in_fact
                        then (
                            select count(distinct season_label)
                            from raw.fixtures
                            where competition_key = 'fifa_world_cup_mens'
                        )
                    else 0
                  end as seasons,
            (select count(*) from mart.fact_matches)
                + case
                    when wp.has_world_cup and not wp.has_world_cup_in_fact
                        then (
                            select count(*)
                            from raw.fixtures
                            where competition_key = 'fifa_world_cup_mens'
                        )
                    else 0
                  end as matches,
            (select count(distinct player_id) from mart.dim_player) as players,
            (select count(*) from mart.fact_match_odds) as matches_with_odds,
            (select count(distinct match_id) from mart.fact_elo_match_team_stats) as matches_with_team_stats,
            (select count(*) from mart.fact_elo_match_team_stats) as team_stat_rows,
            (select count(*) from mart.fact_transfermarkt_transfers) as market_transfers,
            (select count(*) from mart.fact_transfermarkt_player_valuations) as market_valuations
        from world_cup_presence wp;
        """
    ) or {}

    return {
        "competitions": _to_int(row.get("competitions")),
        "seasons": _to_int(row.get("seasons")),
        "matches": _to_int(row.get("matches")),
        "players": _to_int(row.get("players")),
        "matchesWithOdds": _to_int(row.get("matches_with_odds")),
        "matchesWithTeamStats": _to_int(row.get("matches_with_team_stats")),
        "teamStatRows": _to_int(row.get("team_stat_rows")),
        "marketTransfers": _to_int(row.get("market_transfers")),
        "marketValuations": _to_int(row.get("market_valuations")),
    }


def _normalize_archive_summary_from_competitions(
    archive_summary: dict[str, Any],
    competitions: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_summary = dict(archive_summary)
    normalized_summary["competitions"] = len(competitions)
    normalized_summary["seasons"] = sum(_to_int(item.get("seasonsCount")) for item in competitions)
    normalized_summary["matches"] = sum(_to_int(item.get("matchesCount")) for item in competitions)
    return normalized_summary


def _fetch_control_competition_catalog() -> dict[str, dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        select
            competition_key,
            competition_name,
            competition_type,
            country_name,
            confederation_name,
            tier,
            display_priority
        from control.competitions
        where is_active = true;
        """
    )
    return {
        str(row["competition_key"]).strip(): row
        for row in rows
        if str(row.get("competition_key") or "").strip() != ""
    }


def _normalize_archive_summary_from_competitions(
    archive_summary: dict[str, Any],
    competitions: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_summary = dict(archive_summary)
    normalized_summary["competitions"] = len(competitions)
    normalized_summary["seasons"] = sum(_to_int(item.get("seasonsCount")) for item in competitions)
    normalized_summary["matches"] = sum(_to_int(item.get("matchesCount")) for item in competitions)
    return normalized_summary


def _fetch_control_competition_catalog() -> dict[str, dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        with match_scope as (
            select
                fm.match_id,
                fm.league_id,
                fm.competition_key,
                fm.season_label,
                fm.date_day,
                dc.league_name
            from mart.fact_matches fm
            left join mart.dim_competition dc
              on dc.competition_sk = fm.competition_sk
            where fm.competition_key is not null
        ),
        match_totals as (
            select
                competition_key,
                min(league_id)::text as competition_id,
                max(league_name) as competition_name,
                count(distinct match_id)::int as matches_count,
                count(distinct season_label)::int as seasons_count
            from match_scope
            group by competition_key
        ),
        first_season as (
            select distinct on (competition_key)
                competition_key,
                season_label as min_season_label
            from match_scope
            order by competition_key, date_day asc nulls last, season_label asc
        ),
        latest_season as (
            select distinct on (competition_key)
                competition_key,
                season_label as max_season_label
            from match_scope
            order by competition_key, date_day desc nulls last, season_label desc
        ),
        summary_by_competition as (
            select
                league_scope.competition_key,
                sum(coalesce(css.match_statistics_count, 0))::int as match_statistics_count,
                sum(coalesce(css.lineups_count, 0))::int as lineups_count,
                sum(coalesce(css.events_count, 0))::int as events_count,
                sum(coalesce(css.player_statistics_count, 0))::int as player_statistics_count
            from (
                select distinct league_id, competition_key
                from match_scope
                where league_id is not null
            ) league_scope
            left join mart.competition_serving_summary css
              on css.league_id = league_scope.league_id
            group by league_scope.competition_key
        )
        select
            mt.competition_id,
            mt.competition_key,
            mt.competition_name,
            mt.matches_count,
            mt.seasons_count,
            fs.min_season_label,
            ls.max_season_label,
            coalesce(sbc.match_statistics_count, 0) as match_statistics_count,
            coalesce(sbc.lineups_count, 0) as lineups_count,
            coalesce(sbc.events_count, 0) as events_count,
            coalesce(sbc.player_statistics_count, 0) as player_statistics_count
        from match_totals mt
        left join first_season fs
          on fs.competition_key = mt.competition_key
        left join latest_season ls
          on ls.competition_key = mt.competition_key
        left join summary_by_competition sbc
          on sbc.competition_key = mt.competition_key
        order by mt.competition_name asc;
        """
    )

    competition_order = {
        competition_id: index
        for index, competition_id in enumerate(list_canonical_competition_ids())
    }

    control_catalog = _fetch_control_competition_catalog()
    external_depth_by_key = _fetch_external_competition_depth_by_key()

    def source_rank(source: str) -> int:
        if source == "eloratings":
            return 3
        if source == "transfermarkt":
            return 2
        return 1

    def format_external_season_label(
        canonical_competition: Any,
        season_value: Any,
    ) -> str | None:
        if season_value is None:
            return None

        normalized = str(season_value).strip()
        if normalized == "":
            return None

        if (
            canonical_competition is not None
            and canonical_competition.season_calendar == "split_year"
            and normalized.isdigit()
            and len(normalized) == 4
        ):
            return f"{normalized}/{int(normalized) + 1}"

        return normalized

    payload: list[dict[str, Any]] = []
    for row in rows:
        competition_key = str(row.get("competition_key") or "").strip()
        competition_name = str(row.get("competition_name") or competition_key).strip()
        competition_id = str(row.get("competition_id") or competition_key).strip()
        if competition_key == "" or competition_id == "":
            continue

        canonical_competition = get_canonical_competition_by_key(competition_key)
        metadata = _infer_competition_catalog_metadata(
            competition_key,
            competition_name,
            control_catalog.get(competition_key),
        )
        public_competition_id = (
            str(canonical_competition.competition_id)
            if canonical_competition is not None
            else competition_id
        )
        public_competition_name = (
            canonical_competition.default_name
            if canonical_competition is not None
            else competition_name
        )

        min_season = row.get("min_season_label")
        max_season = row.get("max_season_label")
        external_candidates = external_depth_by_key.get(competition_key, [])
        candidates = [
            {
                "source": "published",
                "matchesCount": _to_int(row.get("matches_count")),
                "seasonsCount": _to_int(row.get("seasons_count")),
                "fromSeasonLabel": str(min_season) if min_season is not None else None,
                "toSeasonLabel": str(max_season) if max_season is not None else None,
            },
            *external_candidates,
        ]
        canonical_matches_count = _to_int(row.get("matches_count"))
        canonical_seasons_count = _to_int(row.get("seasons_count"))
        dominant_candidate = max(
            candidates,
            key=lambda candidate: (
                _to_int(candidate.get("seasonsCount")),
                _to_int(candidate.get("matchesCount")),
                source_rank(str(candidate.get("source") or "published")),
            ),
        )
        additional_sources = sorted(
            {
                str(candidate.get("source") or "published")
                for candidate in candidates
                if str(candidate.get("source") or "published")
                != str(dominant_candidate.get("source") or "published")
            }
        )
        source_label = (
            "multi"
            if len({str(candidate.get("source") or "published") for candidate in candidates}) > 1
            else str(dominant_candidate.get("source") or "published")
        )
        from_season_label = dominant_candidate.get("fromSeasonLabel") or format_external_season_label(
            canonical_competition,
            dominant_candidate.get("fromSeason"),
        )
        to_season_label = dominant_candidate.get("toSeasonLabel") or format_external_season_label(
            canonical_competition,
            dominant_candidate.get("toSeason"),
        )
        from_context = (
            {
                "competitionId": public_competition_id,
                "competitionKey": competition_key,
                "competitionName": public_competition_name,
                "seasonId": str(min_season),
                "seasonLabel": str(min_season),
            }
            if min_season is not None
            else None
        )
        latest_context = (
            {
                "competitionId": public_competition_id,
                "competitionKey": competition_key,
                "competitionName": public_competition_name,
                "seasonId": str(max_season),
                "seasonLabel": str(max_season),
            }
            if max_season is not None
            else None
        )

        payload.append(
            {
                "competitionId": public_competition_id,
                "competitionKey": competition_key,
                "competitionName": public_competition_name,
                "assetId": "wc_mens" if competition_key == "fifa_world_cup_mens" else public_competition_id,
                "source": source_label,
                "dominantSource": str(dominant_candidate.get("source") or "published"),
                "additionalSources": additional_sources,
                "country": metadata["country"],
                "region": metadata["region"],
                "scope": metadata["scope"],
                "type": metadata["type"],
                "matchesCount": canonical_matches_count,
                "seasonsCount": canonical_seasons_count,
                "range": {
                    "fromSeasonId": str(min_season) if min_season is not None else None,
                    "fromSeasonLabel": from_season_label,
                    "toSeasonId": str(max_season) if max_season is not None else None,
                    "toSeasonLabel": to_season_label,
                },
                "latestContext": latest_context,
                "coverage": _format_competition_coverage(
                    matches_count=_to_int(row.get("matches_count")),
                    match_statistics_count=_to_int(row.get("match_statistics_count")),
                    lineups_count=_to_int(row.get("lineups_count")),
                    events_count=_to_int(row.get("events_count")),
                    player_statistics_count=_to_int(row.get("player_statistics_count")),
                ),
            }
        )

    return sorted(
        payload,
        key=lambda item: (
            competition_order.get(int(item["competitionId"]), 999)
            if str(item["competitionId"]).isdigit()
            else 999,
            item["competitionName"],
        ),
    )


def _fetch_external_competition_depth_by_key() -> dict[str, list[dict[str, Any]]]:
    rows = db_client.fetch_all(
        """
        with split_year_competitions(competition_key) as (
            values
                ('bundesliga'),
                ('champions_league'),
                ('la_liga'),
                ('ligue_1'),
                ('premier_league'),
                ('primeira_liga'),
                ('serie_a_it')
        ),
        brasileirao_depth as (
            select
                'brasileirao_a'::text as competition_key,
                'brasileirao'::text as source,
                count(*)::int as matches_count,
                count(distinct extract(year from bx.match_date)::int)::int as seasons_count,
                min(extract(year from bx.match_date)::int)::text as min_season,
                max(extract(year from bx.match_date)::int)::text as max_season
            from control.brasileirao_fixture_xref bx
            inner join control.external_match_publication_xref px
              on px.source = 'dataset_brasileirao'
             and px.source_entity_id = bx.brasileirao_match_id
            where bx.identity_status = 'new_coverage'
              and px.publication_status = 'publishable'
              and bx.match_date is not null
        ),
        transfermarkt_depth as (
            select
                cpm.competition_key,
                'transfermarkt'::text as source,
                count(*)::int as matches_count,
                count(distinct tg.season)::int as seasons_count,
                min(tg.season)::text as min_season,
                max(tg.season)::text as max_season
            from control.competition_provider_map cpm
            inner join raw.tm_games tg
              on cpm.provider = 'transfermarkt'
             and cpm.provider_league_code = tg.competition_id
            inner join control.tm_game_fixture_xref tx
              on tx.tm_game_id = tg.game_id
            inner join control.external_match_publication_xref px
              on px.source = 'transfermarkt'
             and px.source_entity_id = tx.tm_game_id
            where tg.season ~ '^\\d+$'
              and tx.identity_status = 'new_coverage'
              and px.publication_status = 'publishable'
            group by cpm.competition_key
        ),
        elo_depth as (
            select
                cpm.competition_key,
                case
                    when syc.competition_key is not null
                     and extract(month from em.match_date_raw::date)::int <= 6
                        then extract(year from em.match_date_raw::date)::int - 1
                    else extract(year from em.match_date_raw::date)::int
                end as season_start_year
            from control.competition_provider_map cpm
            inner join raw.elo_matches em
              on cpm.provider = 'eloratings'
             and cpm.provider_league_code = em.division
            inner join control.elo_match_xref ex
              on ex.elo_match_hash = em.record_hash
            inner join control.external_match_publication_xref px
              on px.source = 'eloratings'
             and px.source_entity_id = ex.elo_match_hash
            left join split_year_competitions syc
              on syc.competition_key = cpm.competition_key
            where em.match_date_raw ~ '^\\d{4}-\\d{2}-\\d{2}$'
              and ex.identity_status = 'new_coverage'
              and px.publication_status = 'publishable'
        ),
        elo_depth_grouped as (
            select
                competition_key,
                'eloratings'::text as source,
                count(*)::int as matches_count,
                count(distinct season_start_year)::int as seasons_count,
                min(season_start_year)::text as min_season,
                max(season_start_year)::text as max_season
            from elo_depth
            group by competition_key
        )
        select
            competition_key,
            source,
            matches_count,
            seasons_count,
            min_season,
            max_season
        from (
            select * from brasileirao_depth
            union all
            select * from transfermarkt_depth
            union all
            select * from elo_depth_grouped
        ) depth
        where matches_count > 0
        order by competition_key, source;
        """,
        disable_parallel=True,
    )

    payload: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        competition_key = str(row.get("competition_key") or "").strip()
        if competition_key == "":
            continue
        payload.setdefault(competition_key, []).append(
            {
                "source": str(row.get("source") or "").strip(),
                "matchesCount": _to_int(row.get("matches_count")),
                "seasonsCount": _to_int(row.get("seasons_count")),
                "fromSeason": row.get("min_season"),
                "toSeason": row.get("max_season"),
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
    competitions = _fetch_competitions()
    archive_summary = _normalize_archive_summary_from_competitions(
        _fetch_archive_summary(),
        competitions,
    )
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
