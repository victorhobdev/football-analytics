from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request

from ..core.contracts import build_api_response, build_coverage_from_counts
from ..db.client import db_client
from .world_cup_labels import (
    build_world_cup_edition_name,
    serialize_world_cup_display_team,
    translate_world_cup_display_name,
    translate_world_cup_venue_name,
)

router = APIRouter(tags=["world-cup"])

WORLD_CUP_COMPETITION_KEY = "fifa_world_cup_mens"
NAME_PREFIX_NOISE_PATTERN = re.compile(r"^not applicable\s+", re.IGNORECASE)
HISTORICAL_CHAMPION_LINEAGE_ALIASES = {
    "west germany": "germany",
    "alemanha ocidental": "alemanha",
}
KNOCKOUT_ROUND_SEQUENCE = (
    "Round of 32",
    "Round of 16",
    "Quarter-finals",
    "Semi-finals",
    "Final",
)
KNOCKOUT_ROUND_LABELS = {
    "Round of 32": "16 avos de final",
    "Round of 16": "Oitavas de final",
    "Quarter-finals": "Quartas de final",
    "Semi-finals": "Semifinais",
    "Final": "Final",
}
GROUP_STAGE_SEQUENCE = (
    "group_stage_1",
    "group_stage_2",
    "final_round",
)
GROUP_STAGE_LABELS = {
    "group_stage_1": "Fase de grupos",
    "group_stage_2": "Segunda fase de grupos",
    "final_round": "Fase final",
}
INFERRED_KNOCKOUT_NOTE = (
    "Classificado identificado pela fase seguinte; a resolução detalhada não consta na fonte bruta."
)
TEAM_RESULT_PRIORITY = {
    "Campeão": 1,
    "Vice-campeão": 2,
    "Fase final": 3,
    "Semifinal": 4,
    "Quartas de final": 5,
    "Segunda fase de grupos": 6,
    "Oitavas de final": 7,
    "16 avos de final": 8,
    "Fase de grupos": 9,
    "Participação": 10,
}
MINIMUM_GOALS_FOR_SCORER_LISTS = 3
MINIMUM_SQUAD_EDITIONS_FOR_PLAYER_RANKINGS = 3


@dataclass(frozen=True)
class MatchOutcomeOverride:
    fixture_id: int
    winner_team_id: int
    resolution_type: str
    note: str | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None


MATCH_OUTCOME_OVERRIDES_BY_FIXTURE: dict[int, MatchOutcomeOverride] = {
    7020285427938503850: MatchOutcomeOverride(
        fixture_id=7020285427938503850,
        winner_team_id=7030991384093091376,
        resolution_type="penalties",
        home_penalties=1,
        away_penalties=3,
    ),
    7020256563718834684: MatchOutcomeOverride(
        fixture_id=7020256563718834684,
        winner_team_id=7030026708875084432,
        resolution_type="penalties",
        home_penalties=4,
        away_penalties=5,
    ),
    7020646853743035411: MatchOutcomeOverride(
        fixture_id=7020646853743035411,
        winner_team_id=7030456752538593319,
        resolution_type="penalties",
        home_penalties=3,
        away_penalties=2,
    ),
    7020044772174641786: MatchOutcomeOverride(
        fixture_id=7020044772174641786,
        winner_team_id=7030651194192465147,
        resolution_type="penalties",
        home_penalties=0,
        away_penalties=3,
    ),
    7020321399116805521: MatchOutcomeOverride(
        fixture_id=7020321399116805521,
        winner_team_id=7030276759082996865,
        resolution_type="penalties",
        home_penalties=1,
        away_penalties=3,
    ),
    7020397402957067683: MatchOutcomeOverride(
        fixture_id=7020397402957067683,
        winner_team_id=7030167035104799597,
        resolution_type="penalties",
        home_penalties=4,
        away_penalties=2,
    ),
    7020749698565977800: MatchOutcomeOverride(
        fixture_id=7020749698565977800,
        winner_team_id=7030545134325799351,
        resolution_type="penalties",
        home_penalties=5,
        away_penalties=3,
    ),
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    return normalized_value or None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        normalized_value = value.strip()
        if not normalized_value:
            return None
        try:
            return int(normalized_value)
        except ValueError:
            return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    normalized_value = str(value).strip()
    return normalized_value or None


def _sanitize_display_name(value: str | None) -> str | None:
    normalized_value = _normalize_text(value)
    if normalized_value is None:
        return None

    cleaned_value = NAME_PREFIX_NOISE_PATTERN.sub("", normalized_value).strip()
    return cleaned_value or normalized_value


def _normalize_compare_key(value: str | None) -> str | None:
    normalized_value = _normalize_text(value)
    if normalized_value is None:
        return None

    return normalized_value.casefold()


def _serialize_team(team_id: int | None, team_name: str | None) -> dict[str, Any] | None:
    return serialize_world_cup_display_team(team_id, _normalize_text(team_name))


def _team_reference_key(team_id: int | str | None, team_name: str | None) -> str | None:
    serialized_team = serialize_world_cup_display_team(team_id, _normalize_text(team_name))
    if serialized_team is None:
        return None

    normalized_team_id = serialized_team.get("teamId")
    if normalized_team_id is not None:
        return f"id:{normalized_team_id}"

    compare_key = _normalize_compare_key(serialized_team.get("teamName"))
    if compare_key is None:
        return None

    return f"name:{compare_key}"


def _team_reference_key_from_payload(team: dict[str, Any] | None) -> str | None:
    if team is None:
        return None

    return _team_reference_key(team.get("teamId"), team.get("teamName"))


def _build_pairing_key(fixture_row: dict[str, Any]) -> str:
    home_key = _team_reference_key(fixture_row.get("home_team_id"), fixture_row.get("home_team_name"))
    away_key = _team_reference_key(fixture_row.get("away_team_id"), fixture_row.get("away_team_name"))
    normalized_keys = sorted(
        [
            home_key or f"fixture:{fixture_row['fixture_id']}:home",
            away_key or f"fixture:{fixture_row['fixture_id']}:away",
        ]
    )
    return "|".join(normalized_keys)


def _build_group_sort_key(group_key: str | None) -> tuple[int, int | str]:
    normalized_value = _normalize_text(group_key)
    if normalized_value is None:
        return (2, "")

    if normalized_value.isdigit():
        return (0, int(normalized_value))

    return (1, normalized_value.casefold())


def _append_unique_note(notes: list[str], note: str | None) -> None:
    normalized_note = _normalize_text(note)
    if normalized_note is None or normalized_note in notes:
        return

    notes.append(normalized_note)


def _filter_scorer_list_by_minimum_goals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if int(row.get("goals") or 0) >= MINIMUM_GOALS_FOR_SCORER_LISTS
    ]


def _fetch_wc_player_profile_refs(wc_player_ids: list[int | None]) -> dict[int, dict[str, str]]:
    normalized_player_ids = sorted({player_id for player_id in wc_player_ids if player_id is not None})
    if not normalized_player_ids:
        return {}

    rows = db_client.fetch_all(
        """
        select
            wc_player_id,
            sportmonks_player_id
        from raw.wc_player_identity_map
        where wc_player_id = any(%s)
          and match_confidence = 'confirmed'
          and sportmonks_player_id is not null;
        """,
        [normalized_player_ids],
    )

    profile_refs: dict[int, dict[str, str]] = {}
    for row in rows:
        wc_player_id = _safe_int(row.get("wc_player_id"))
        sportmonks_player_id = _safe_int(row.get("sportmonks_player_id"))
        if wc_player_id is None or sportmonks_player_id is None:
            continue

        sportmonks_player_id_text = str(sportmonks_player_id)
        profile_refs[wc_player_id] = {
            "playerId": sportmonks_player_id_text,
            "profileUrl": f"/players/{sportmonks_player_id_text}",
        }

    return profile_refs


def _resolve_wc_player_profile_ref(
    profile_refs: dict[int, dict[str, str]],
    wc_player_id: int | None,
) -> dict[str, str] | None:
    if wc_player_id is None:
        return None

    return profile_refs.get(wc_player_id)


def _serialize_wc_player_id(
    wc_player_id: int | None,
    profile_refs: dict[int, dict[str, str]],
) -> str | None:
    if wc_player_id is None:
        return None

    profile_ref = _resolve_wc_player_profile_ref(profile_refs, wc_player_id)
    if profile_ref is not None:
        return profile_ref["playerId"]

    return str(wc_player_id)


def _build_champion_identity_key(team: dict[str, Any] | None) -> str | None:
    if team is None:
        return None

    normalized_team_name = _normalize_compare_key(team.get("teamName"))
    if normalized_team_name is None:
        return team.get("teamId")

    return HISTORICAL_CHAMPION_LINEAGE_ALIASES.get(normalized_team_name, normalized_team_name)


def _edition_coverage_payload(
    *,
    champion_team: dict[str, Any] | None,
    host_country: str | None,
    matches_count: int,
    used_override: bool,
) -> tuple[dict[str, Any], str | None]:
    if champion_team is None or champion_team.get("teamName") is None or matches_count <= 0:
        return (
            {
                "status": "partial",
                "label": "Cobertura parcial",
            },
            "Campeão da edição não foi resolvido com segurança nas fontes disponíveis.",
        )

    if host_country is None:
        return (
            {
                "status": "partial",
                "label": "Cobertura parcial",
            },
            "País-sede ausente no catálogo bruto da edição.",
        )

    if used_override:
        return (
            {
                "status": "complete",
                "label": "Cobertura completa",
                "percentage": 100,
            },
            None,
        )

    return (
        {
            "status": "complete",
            "label": "Cobertura completa",
            "percentage": 100,
        },
        None,
    )


def _is_technical_historical_note(note: str | None) -> bool:
    normalized_note = _normalize_text(note)
    if normalized_note is None:
        return False

    normalized_compare = normalized_note.casefold()
    return (
        normalized_note == INFERRED_KNOCKOUT_NOTE
        or "disputa de pênaltis" in normalized_compare
        or "classificado identificado pela fase seguinte" in normalized_compare
    )


def _edition_page_coverage_payload(notes: list[str]) -> dict[str, Any]:
    if not notes:
        return {
            "status": "complete",
            "label": "Cobertura completa",
            "percentage": 100,
        }

    if any(not _is_technical_historical_note(note) for note in notes):
        return {
            "status": "partial",
            "label": "Cobertura parcial",
        }

    return {
        "status": "complete",
        "label": "Cobertura completa",
        "percentage": 100,
    }


def _serialize_navigation_edition(edition: dict[str, Any] | None) -> dict[str, Any] | None:
    if edition is None:
        return None

    return {
        "seasonLabel": edition["seasonLabel"],
        "year": int(edition["year"]),
        "editionName": edition["editionName"],
    }


def _build_group_label(stage_key: str, group_key: str | None) -> str:
    normalized_group_key = _normalize_text(group_key)
    if stage_key == "final_round":
        return "Grupo final"

    if normalized_group_key is None:
        return "Grupo"

    return f"Grupo {normalized_group_key}"


def _build_team_final_round_label(position: int | None) -> str:
    if position is None:
        return "Fase final"

    if position == 3:
        return "Fase final (3º lugar)"

    if position == 4:
        return "Fase final (4º lugar)"

    return "Fase final"


def _fetch_edition_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            cs.season_label,
            cs.season_name,
            cs.starting_at,
            cs.ending_at,
            cs.payload->>'host_country' as host_country,
            case
                when nullif(cs.payload->>'count_teams', '') is null then null
                else (cs.payload->>'count_teams')::int
            end as count_teams,
            cs.payload->'format_flags' as format_flags
        from raw.competition_seasons cs
        where cs.competition_key = %s
        order by cs.season_label::int asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_match_counts_by_season() -> dict[str, int]:
    rows = db_client.fetch_all(
        """
        select
            f.season_label,
            count(*)::int as matches_count
        from raw.fixtures f
        where f.competition_key = %s
        group by f.season_label;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )

    return {
        row["season_label"]: int(row.get("matches_count") or 0)
        for row in rows
        if row.get("season_label") is not None
    }


def _fetch_final_fixture_rows() -> dict[str, dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        with ranked_finals as (
            select
                f.season_label,
                f.fixture_id,
                f.date_utc,
                f.venue_name,
                f.home_team_id,
                f.home_team_name,
                f.away_team_id,
                f.away_team_name,
                f.home_goals,
                f.away_goals,
                f.stage_name,
                f.round_name,
                row_number() over (
                    partition by f.season_label
                    order by f.date_utc desc nulls last, f.fixture_id desc
                ) as final_rank
            from raw.fixtures f
            where f.competition_key = %s
              and (f.round_name = 'Final' or f.stage_name = 'Final')
        )
        select
            season_label,
            fixture_id,
            date_utc,
            venue_name,
            home_team_id,
            home_team_name,
            away_team_id,
            away_team_name,
            home_goals,
            away_goals,
            stage_name,
            round_name
        from ranked_finals
        where final_rank = 1;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )

    return {
        row["season_label"]: row
        for row in rows
        if row.get("season_label") is not None
    }


def _fetch_final_round_rows() -> dict[str, dict[int, dict[str, Any]]]:
    rows = db_client.fetch_all(
        """
        with ranked_final_round_rows as (
            select
                ss.season_label,
                ss.position,
                ss.team_id,
                ss.payload->>'team_name' as team_name,
                row_number() over (
                    partition by ss.season_label, ss.position
                    order by ss.round_id desc, ss.stage_id desc
                ) as season_position_rank
            from raw.standings_snapshots ss
            where ss.competition_key = %s
              and ss.payload->>'stage_key' = 'final_round'
              and ss.position in (1, 2)
        )
        select
            season_label,
            position,
            team_id,
            team_name
        from ranked_final_round_rows
        where season_position_rank = 1;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )

    final_round_rows: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        season_label = row.get("season_label")
        position = row.get("position")
        if season_label is None or position is None:
            continue

        final_round_rows.setdefault(season_label, {})[int(position)] = row

    return final_round_rows


def _fetch_penalty_shootout_scores_by_fixture() -> dict[int, dict[str, int]]:
    rows = db_client.fetch_all(
        """
        select
            e.fixture_id,
            e.event_payload->'team'->>'name' as event_team_name,
            count(*) filter (
                where e.event_payload->'shot'->'outcome'->>'name' = 'Goal'
            )::int as converted_penalties
        from raw.wc_match_events e
        where e.event_type = 'Shot'
          and e.event_payload->'shot'->'type'->>'name' = 'Penalty'
          and coalesce((e.event_payload->>'period')::int, 0) = 5
        group by
            e.fixture_id,
            e.event_payload->'team'->>'name';
        """
    )

    scores_by_fixture: dict[int, dict[str, int]] = {}
    for row in rows:
        fixture_id = row.get("fixture_id")
        team_name = _normalize_compare_key(row.get("event_team_name"))
        if fixture_id is None or team_name is None:
            continue

        scores_by_fixture.setdefault(int(fixture_id), {})[team_name] = int(
            row.get("converted_penalties") or 0
        )

    override_fixture_ids = [
        override.fixture_id
        for override in MATCH_OUTCOME_OVERRIDES_BY_FIXTURE.values()
        if override.home_penalties is not None and override.away_penalties is not None
    ]
    if not override_fixture_ids:
        return scores_by_fixture

    fixture_rows = db_client.fetch_all(
        """
        select
            f.fixture_id,
            f.home_team_name,
            f.away_team_name
        from raw.fixtures f
        where f.fixture_id = any(%s);
        """,
        [override_fixture_ids],
    )
    fixture_name_index = {
        int(row["fixture_id"]): row
        for row in fixture_rows
        if row.get("fixture_id") is not None
    }
    for fixture_id in override_fixture_ids:
        if fixture_id in scores_by_fixture:
            continue

        override = MATCH_OUTCOME_OVERRIDES_BY_FIXTURE[fixture_id]
        fixture_row = fixture_name_index.get(fixture_id)
        if fixture_row is None:
            continue

        home_team_name = _normalize_compare_key(fixture_row.get("home_team_name"))
        away_team_name = _normalize_compare_key(fixture_row.get("away_team_name"))
        if (
            home_team_name is None
            or away_team_name is None
            or override.home_penalties is None
            or override.away_penalties is None
        ):
            continue

        scores_by_fixture[fixture_id] = {
            home_team_name: override.home_penalties,
            away_team_name: override.away_penalties,
        }

    return scores_by_fixture


def _fetch_historical_top_scorer() -> dict[str, Any] | None:
    row = db_client.fetch_one(
        """
        with scorer_totals as (
            select
                wg.player_id,
                max(wg.player_name) as player_name,
                max(wg.team_id) as team_id,
                max(wg.team_name) as team_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
            group by wg.player_id
        )
        select
            player_id,
            player_name,
            team_id,
            team_name,
            goals
        from scorer_totals
        order by goals desc, player_name asc
        limit 1;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )

    if row is None:
        return None

    player_id = _safe_int(row.get("player_id"))
    profile_refs = _fetch_wc_player_profile_refs([player_id])
    profile_ref = _resolve_wc_player_profile_ref(profile_refs, player_id)
    team = _serialize_team(_safe_int(row.get("team_id")), row.get("team_name"))
    return {
        "playerId": _serialize_wc_player_id(player_id, profile_refs),
        "imageAssetId": str(player_id) if player_id is not None else None,
        "playerName": _sanitize_display_name(row.get("player_name")),
        "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
        "teamId": team.get("teamId") if team else None,
        "teamName": team.get("teamName") if team else None,
        "goals": int(row.get("goals") or 0),
    }


def _fetch_edition_top_scorers(season_label: str) -> list[dict[str, Any]]:
    rows = db_client.fetch_all(
        """
        with scorer_totals as (
            select
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ) as scorer_key,
                max(wg.player_id) as player_id,
                max(wg.player_name) as player_name,
                max(wg.team_id) as team_id,
                max(wg.team_name) as team_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
              and wg.season_label = %s
            group by
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                )
        )
        select
            dense_rank() over (order by goals desc) as scorer_rank,
            player_id,
            player_name,
            team_id,
            team_name,
            goals
        from scorer_totals
        where goals > 0
        order by goals desc, player_name asc;
        """,
        [WORLD_CUP_COMPETITION_KEY, season_label],
    )

    profile_refs = _fetch_wc_player_profile_refs([_safe_int(row.get("player_id")) for row in rows])
    scorers_payload: list[dict[str, Any]] = []
    for row in rows:
        player_id = _safe_int(row.get("player_id"))
        profile_ref = _resolve_wc_player_profile_ref(profile_refs, player_id)
        team = _serialize_team(_safe_int(row.get("team_id")), row.get("team_name"))
        scorers_payload.append(
            {
                "rank": int(row.get("scorer_rank") or 0),
                "playerId": _serialize_wc_player_id(player_id, profile_refs),
                "imageAssetId": str(player_id) if player_id is not None else None,
                "playerName": _sanitize_display_name(row.get("player_name")),
                "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
                "teamId": team.get("teamId") if team else None,
                "teamName": team.get("teamName") if team else None,
                "goals": int(row.get("goals") or 0),
            }
        )

    return scorers_payload


def _fetch_group_stage_rows_for_season(season_label: str) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            ss.position,
            ss.team_id,
            ss.points,
            ss.games_played,
            ss.won,
            ss.draw,
            ss.lost,
            ss.goals_for,
            ss.goals_against,
            ss.goal_diff,
            ss.payload->>'stage_key' as stage_key,
            ss.payload->>'group_key' as group_key,
            ss.payload->>'team_name' as team_name,
            coalesce((ss.payload->>'advanced')::boolean, false) as advanced
        from raw.standings_snapshots ss
        where ss.competition_key = %s
          and ss.season_label = %s
          and ss.payload->>'stage_key' = any(%s)
        order by
            case ss.payload->>'stage_key'
                when 'group_stage_1' then 1
                when 'group_stage_2' then 2
                when 'final_round' then 3
                else 99
            end,
            ss.position asc,
            ss.team_id asc;
        """,
        [WORLD_CUP_COMPETITION_KEY, season_label, list(GROUP_STAGE_SEQUENCE)],
    )


def _fetch_knockout_fixture_rows_for_season(season_label: str) -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            f.fixture_id,
            f.date_utc,
            f.date as match_date,
            f.venue_name,
            f.round_name,
            f.home_team_id,
            f.home_team_name,
            f.away_team_id,
            f.away_team_name,
            f.home_goals,
            f.away_goals
        from raw.fixtures f
        where f.competition_key = %s
          and f.season_label = %s
          and f.round_name = any(%s)
        order by
            case f.round_name
                when 'Round of 32' then 1
                when 'Round of 16' then 2
                when 'Quarter-finals' then 3
                when 'Semi-finals' then 4
                when 'Final' then 5
                else 99
            end,
            f.date_utc asc nulls last,
            f.fixture_id asc;
        """,
        [WORLD_CUP_COMPETITION_KEY, season_label, list(KNOCKOUT_ROUND_SEQUENCE)],
    )


def _fetch_team_match_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with team_matches as (
            select
                f.season_label,
                f.home_team_id as team_id,
                f.home_team_name as team_name,
                f.fixture_id
            from raw.fixtures f
            where f.competition_key = %s

            union all

            select
                f.season_label,
                f.away_team_id as team_id,
                f.away_team_name as team_name,
                f.fixture_id
            from raw.fixtures f
            where f.competition_key = %s
        )
        select
            tm.season_label,
            tm.team_id,
            max(tm.team_name) as team_name,
            count(*)::int as matches_count
        from team_matches tm
        where tm.team_id is not null
        group by tm.season_label, tm.team_id
        order by tm.season_label::int asc, max(tm.team_name) asc;
        """,
        [WORLD_CUP_COMPETITION_KEY, WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_team_stage_presence_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            ss.season_label,
            ss.team_id,
            max(ss.payload->>'team_name') as team_name,
            bool_or(ss.payload->>'stage_key' = 'group_stage_1') as has_group_stage_1,
            bool_or(ss.payload->>'stage_key' = 'group_stage_2') as has_group_stage_2,
            bool_or(ss.payload->>'stage_key' = 'final_round') as has_final_round,
            min(
                case
                    when ss.payload->>'stage_key' = 'final_round' then ss.position
                    else null
                end
            ) as final_round_position
        from raw.standings_snapshots ss
        where ss.competition_key = %s
        group by ss.season_label, ss.team_id
        order by ss.season_label::int asc, max(ss.payload->>'team_name') asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_team_knockout_presence_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with team_rounds as (
            select
                f.season_label,
                f.home_team_id as team_id,
                f.home_team_name as team_name,
                f.round_name
            from raw.fixtures f
            where f.competition_key = %s
              and f.round_name = any(%s)

            union all

            select
                f.season_label,
                f.away_team_id as team_id,
                f.away_team_name as team_name,
                f.round_name
            from raw.fixtures f
            where f.competition_key = %s
              and f.round_name = any(%s)
        )
        select
            tr.season_label,
            tr.team_id,
            max(tr.team_name) as team_name,
            bool_or(tr.round_name = 'Round of 32') as has_round_of_32,
            bool_or(tr.round_name = 'Round of 16') as has_round_of_16,
            bool_or(tr.round_name = 'Quarter-finals') as has_quarter_finals,
            bool_or(tr.round_name = 'Semi-finals') as has_semi_finals,
            bool_or(tr.round_name = 'Final') as has_final
        from team_rounds tr
        where tr.team_id is not null
        group by tr.season_label, tr.team_id
        order by tr.season_label::int asc, max(tr.team_name) asc;
        """,
        [
            WORLD_CUP_COMPETITION_KEY,
            list(KNOCKOUT_ROUND_SEQUENCE),
            WORLD_CUP_COMPETITION_KEY,
            list(KNOCKOUT_ROUND_SEQUENCE),
        ],
    )


def _fetch_team_top_scorers_by_season() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with scorer_totals as (
            select
                wg.season_label,
                wg.team_id,
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ) as scorer_key,
                max(wg.player_id) as player_id,
                max(wg.player_name) as player_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
              and wg.team_id is not null
            group by
                wg.season_label,
                wg.team_id,
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                )
        ),
        ranked_scorers as (
            select
                st.season_label,
                st.team_id,
                st.player_id,
                st.player_name,
                st.goals,
                row_number() over (
                    partition by st.season_label, st.team_id
                    order by st.goals desc, st.player_name asc
                ) as scorer_rank
            from scorer_totals st
            where st.goals > 0
        )
        select
            season_label,
            team_id,
            player_id,
            player_name,
            goals
        from ranked_scorers
        where scorer_rank = 1
        order by season_label::int asc, player_name asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_team_historical_scorers(team_ids: list[int]) -> list[dict[str, Any]]:
    if not team_ids:
        return []

    rows = db_client.fetch_all(
        """
        with scorer_totals as (
            select
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ) as scorer_key,
                max(wg.player_id) as player_id,
                max(wg.player_name) as player_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
              and wg.team_id = any(%s)
            group by
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                )
        )
        select
            dense_rank() over (order by goals desc) as scorer_rank,
            player_id,
            player_name,
            goals
        from scorer_totals
        where goals > 0
        order by goals desc, player_name asc;
        """,
        [WORLD_CUP_COMPETITION_KEY, team_ids],
    )

    profile_refs = _fetch_wc_player_profile_refs([_safe_int(row.get("player_id")) for row in rows])
    scorers_payload: list[dict[str, Any]] = []
    for row in rows:
        player_id = _safe_int(row.get("player_id"))
        profile_ref = _resolve_wc_player_profile_ref(profile_refs, player_id)
        scorers_payload.append(
            {
                "rank": int(row.get("scorer_rank") or 0),
                "playerId": _serialize_wc_player_id(player_id, profile_refs),
                "imageAssetId": str(player_id) if player_id is not None else None,
                "playerName": _sanitize_display_name(row.get("player_name")),
                "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
                "goals": int(row.get("goals") or 0),
            }
        )

    return scorers_payload


def _fetch_historical_scorer_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with scorer_totals as (
            select
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ) as scorer_key,
                max(wg.player_id) as player_id,
                max(wg.player_name) as player_name,
                max(wg.team_id) as team_id,
                max(wg.team_name) as team_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
            group by
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                )
        )
        select
            scorer_key,
            player_id,
            player_name,
            team_id,
            team_name,
            goals
        from scorer_totals
        where goals > 0
        order by goals desc, player_name asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_historical_scorer_edition_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with scorer_editions as (
            select
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ) as scorer_key,
                wg.season_label,
                max(wg.team_id) as team_id,
                max(wg.team_name) as team_name,
                count(*) filter (where coalesce(wg.is_own_goal, false) = false)::int as goals
            from raw.wc_goals wg
            where wg.competition_key = %s
            group by
                coalesce(
                    wg.player_id::text,
                    'name:' || lower(coalesce(nullif(trim(wg.player_name), ''), wg.source_goal_id))
                ),
                wg.season_label
        )
        select
            scorer_key,
            season_label,
            team_id,
            team_name,
            goals
        from scorer_editions
        where goals > 0
        order by season_label::int asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _fetch_ranking_fixture_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select
            f.fixture_id,
            f.season_label,
            f.stage_name,
            f.round_name,
            f.date_utc,
            f.venue_name,
            f.home_team_id,
            f.home_team_name,
            f.away_team_id,
            f.away_team_name,
            f.home_goals,
            f.away_goals
        from raw.fixtures f
        where f.competition_key = %s
        order by f.season_label::int asc, f.date_utc asc nulls last, f.fixture_id asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _ranking_fixture_sort_key(row: dict[str, Any]) -> tuple[int, Any, int]:
    fixture_date = row.get("date_utc")
    fixture_id = _safe_int(row.get("fixture_id")) or 0
    return (1 if fixture_date is not None else 0, fixture_date or "", fixture_id)


def _find_final_round_decider_fixture_row(
    edition: dict[str, Any],
    ranking_fixture_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if edition.get("resolutionType") != "final_round":
        return None

    season_label = edition.get("seasonLabel")
    champion_key = _team_reference_key_from_payload(edition.get("champion"))
    runner_up_key = _team_reference_key_from_payload(edition.get("runnerUp"))
    if season_label is None or champion_key is None or runner_up_key is None:
        return None

    candidate_rows: list[dict[str, Any]] = []
    for row in ranking_fixture_rows:
        if row.get("season_label") != season_label:
            continue

        stage_name = _normalize_compare_key(row.get("stage_name"))
        round_name = _normalize_compare_key(row.get("round_name"))
        if stage_name != "final round" and round_name != "final round":
            continue

        home_key = _team_reference_key(row.get("home_team_id"), row.get("home_team_name"))
        away_key = _team_reference_key(row.get("away_team_id"), row.get("away_team_name"))
        if {home_key, away_key} != {champion_key, runner_up_key}:
            continue

        candidate_rows.append(row)

    if not candidate_rows:
        return None

    return sorted(candidate_rows, key=_ranking_fixture_sort_key, reverse=True)[0]


def _orient_final_fixture_row_for_display(
    edition: dict[str, Any],
    fixture_row: dict[str, Any],
) -> dict[str, Any]:
    if edition.get("resolutionType") != "final_round":
        return fixture_row

    champion_key = _team_reference_key_from_payload(edition.get("champion"))
    runner_up_key = _team_reference_key_from_payload(edition.get("runnerUp"))
    home_key = _team_reference_key(fixture_row.get("home_team_id"), fixture_row.get("home_team_name"))
    away_key = _team_reference_key(fixture_row.get("away_team_id"), fixture_row.get("away_team_name"))

    if champion_key is None or runner_up_key is None:
        return fixture_row

    if home_key == champion_key and away_key == runner_up_key:
        return {
            **fixture_row,
            "home_team_id": fixture_row.get("away_team_id"),
            "home_team_name": fixture_row.get("away_team_name"),
            "away_team_id": fixture_row.get("home_team_id"),
            "away_team_name": fixture_row.get("home_team_name"),
            "home_goals": fixture_row.get("away_goals"),
            "away_goals": fixture_row.get("home_goals"),
        }

    return fixture_row


def _fetch_player_squad_appearance_rows() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        with player_editions as (
            select
                ws.player_id,
                max(ws.player_name) as player_name,
                ws.season_label,
                max(ws.team_id) as team_id,
                max(ws.team_name) as team_name
            from raw.wc_squads ws
            where ws.competition_key = %s
              and ws.player_id is not null
            group by ws.player_id, ws.season_label
        )
        select
            pe.player_id,
            pe.player_name,
            pe.season_label,
            pe.team_id,
            pe.team_name
        from player_editions pe
        order by pe.player_name asc, pe.season_label::int asc;
        """,
        [WORLD_CUP_COMPETITION_KEY],
    )


def _assign_dense_ranks(
    items: list[dict[str, Any]],
    ranking_key_builder: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    ranked_items: list[dict[str, Any]] = []
    current_rank = 0
    previous_ranking_key: Any = None

    for item in items:
        ranking_key = ranking_key_builder(item)
        if ranking_key != previous_ranking_key:
            current_rank += 1
            previous_ranking_key = ranking_key

        ranked_items.append(
            {
                "rank": current_rank,
                **item,
            }
        )

    return ranked_items


def _build_world_cup_titles_team_ranking(
    teams_payload: list[dict[str, Any]],
    editions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    finals_count_by_team_key: dict[str, int] = {}
    for edition in editions:
        champion_key = _team_reference_key_from_payload(edition.get("champion"))
        runner_up_key = _team_reference_key_from_payload(edition.get("runnerUp"))
        if champion_key is not None:
            finals_count_by_team_key[champion_key] = finals_count_by_team_key.get(champion_key, 0) + 1
        if runner_up_key is not None:
            finals_count_by_team_key[runner_up_key] = finals_count_by_team_key.get(runner_up_key, 0) + 1

    sorted_teams = sorted(
        teams_payload,
        key=lambda item: (
            -int(item["titlesCount"]),
            -int(finals_count_by_team_key.get(_team_reference_key(item["teamId"], item.get("teamName")) or "", 0)),
            -int(item["participationsCount"]),
            _normalize_compare_key(item.get("teamName")) or "",
        ),
    )

    team_rankings_payload: list[dict[str, Any]] = []
    current_team_rank = 0
    previous_team_key: tuple[int, int, int] | None = None
    for team in sorted_teams:
        team_key = _team_reference_key(team["teamId"], team.get("teamName"))
        finals_count = finals_count_by_team_key.get(team_key or "", 0)
        ranking_tuple = (
            int(team["titlesCount"]),
            finals_count,
            int(team["participationsCount"]),
        )
        if previous_team_key != ranking_tuple:
            current_team_rank += 1
            previous_team_key = ranking_tuple

        team_rankings_payload.append(
            {
                "rank": current_team_rank,
                "teamId": team["teamId"],
                "teamName": team["teamName"],
                "titlesCount": int(team["titlesCount"]),
                "participationsCount": int(team["participationsCount"]),
                "finalsCount": finals_count,
            }
        )

    return team_rankings_payload


def _build_world_cup_team_stat_rankings(
    teams_payload: list[dict[str, Any]],
    fixture_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    team_stats_by_key: dict[str, dict[str, Any]] = {}

    for team in teams_payload:
        team_key = _team_reference_key(team["teamId"], team.get("teamName"))
        if team_key is None:
            continue

        top_four_count = sum(
            1
            for participation in team.get("participations", [])
            if int(participation.get("resultRank") or TEAM_RESULT_PRIORITY["Participação"])
            <= TEAM_RESULT_PRIORITY["Semifinal"]
        )
        team_stats_by_key[team_key] = {
            "teamId": team["teamId"],
            "teamName": team.get("teamName"),
            "matches": 0,
            "wins": 0,
            "goalsScored": 0,
            "topFourCount": top_four_count,
            "participationsCount": int(team.get("participationsCount") or 0),
            "titlesCount": int(team.get("titlesCount") or 0),
        }

    def ensure_team_stats(team_id: Any, team_name: str | None) -> dict[str, Any] | None:
        team_key = _team_reference_key(_safe_int(team_id), team_name)
        serialized_team = _serialize_team(_safe_int(team_id), team_name)
        if team_key is None or serialized_team is None:
            return None

        return team_stats_by_key.setdefault(
            team_key,
            {
                "teamId": serialized_team["teamId"],
                "teamName": serialized_team.get("teamName"),
                "matches": 0,
                "wins": 0,
                "goalsScored": 0,
                "topFourCount": 0,
                "participationsCount": 0,
                "titlesCount": 0,
            },
        )

    for row in fixture_rows:
        home_stats = ensure_team_stats(row.get("home_team_id"), row.get("home_team_name"))
        away_stats = ensure_team_stats(row.get("away_team_id"), row.get("away_team_name"))
        home_goals = _safe_int(row.get("home_goals"))
        away_goals = _safe_int(row.get("away_goals"))

        if home_stats is not None:
            home_stats["matches"] += 1
        if away_stats is not None:
            away_stats["matches"] += 1

        if home_goals is None or away_goals is None:
            continue

        if home_stats is not None:
            home_stats["goalsScored"] += home_goals
        if away_stats is not None:
            away_stats["goalsScored"] += away_goals

        if home_goals > away_goals and home_stats is not None:
            home_stats["wins"] += 1
        if away_goals > home_goals and away_stats is not None:
            away_stats["wins"] += 1

    team_stats = [
        stats
        for stats in team_stats_by_key.values()
        if int(stats.get("matches") or 0) > 0 or int(stats.get("topFourCount") or 0) > 0
    ]

    sorted_by_wins = sorted(
        team_stats,
        key=lambda item: (
            -int(item["wins"]),
            -int(item["matches"]),
            -int(item["goalsScored"]),
            _normalize_compare_key(item.get("teamName")) or "",
        ),
    )
    sorted_by_matches = sorted(
        team_stats,
        key=lambda item: (
            -int(item["matches"]),
            -int(item["wins"]),
            -int(item["goalsScored"]),
            _normalize_compare_key(item.get("teamName")) or "",
        ),
    )
    sorted_by_goals = sorted(
        team_stats,
        key=lambda item: (
            -int(item["goalsScored"]),
            -int(item["wins"]),
            -int(item["matches"]),
            _normalize_compare_key(item.get("teamName")) or "",
        ),
    )
    sorted_by_top_four = sorted(
        team_stats,
        key=lambda item: (
            -int(item["topFourCount"]),
            -int(item["titlesCount"]),
            -int(item["participationsCount"]),
            _normalize_compare_key(item.get("teamName")) or "",
        ),
    )

    return {
        "wins": {
            "label": "Seleções com mais vitórias",
            "metricLabel": "Vitórias",
            "items": _assign_dense_ranks(
                [
                    {
                        "teamId": item["teamId"],
                        "teamName": item.get("teamName"),
                        "wins": int(item["wins"]),
                        "matches": int(item["matches"]),
                    }
                    for item in sorted_by_wins
                ],
                lambda item: (int(item["wins"]), int(item["matches"])),
            ),
        },
        "matches": {
            "label": "Seleções com mais jogos",
            "metricLabel": "Jogos",
            "items": _assign_dense_ranks(
                [
                    {
                        "teamId": item["teamId"],
                        "teamName": item.get("teamName"),
                        "matches": int(item["matches"]),
                        "wins": int(item["wins"]),
                    }
                    for item in sorted_by_matches
                ],
                lambda item: (int(item["matches"]), int(item["wins"])),
            ),
        },
        "goalsScored": {
            "label": "Seleções com mais gols marcados",
            "metricLabel": "Gols",
            "items": _assign_dense_ranks(
                [
                    {
                        "teamId": item["teamId"],
                        "teamName": item.get("teamName"),
                        "goalsScored": int(item["goalsScored"]),
                        "matches": int(item["matches"]),
                    }
                    for item in sorted_by_goals
                ],
                lambda item: (int(item["goalsScored"]), int(item["matches"])),
            ),
        },
        "topFourAppearances": {
            "label": "Seleções com mais semi-finais",
            "metricLabel": "Top 4",
            "items": _assign_dense_ranks(
                [
                    {
                        "teamId": item["teamId"],
                        "teamName": item.get("teamName"),
                        "topFourCount": int(item["topFourCount"]),
                        "titlesCount": int(item["titlesCount"]),
                    }
                    for item in sorted_by_top_four
                ],
                lambda item: (int(item["topFourCount"]), int(item["titlesCount"])),
            ),
        },
    }


def _build_world_cup_edition_rankings(
    editions: list[dict[str, Any]],
    fixture_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    edition_stats_by_season: dict[str, dict[str, Any]] = {
        edition["seasonLabel"]: {
            "seasonLabel": edition["seasonLabel"],
            "year": int(edition["year"]),
            "editionName": edition["editionName"],
            "matchesCount": 0,
            "goalsCount": 0,
        }
        for edition in editions
    }

    for row in fixture_rows:
        season_label = row.get("season_label")
        if season_label is None:
            continue

        edition_stats = edition_stats_by_season.get(season_label)
        if edition_stats is None:
            edition_stats = {
                "seasonLabel": season_label,
                "year": int(season_label),
                "editionName": build_world_cup_edition_name(season_label),
                "matchesCount": 0,
                "goalsCount": 0,
            }
            edition_stats_by_season[season_label] = edition_stats

        home_goals = _safe_int(row.get("home_goals"))
        away_goals = _safe_int(row.get("away_goals"))
        if home_goals is None or away_goals is None:
            continue

        edition_stats["matchesCount"] += 1
        edition_stats["goalsCount"] += home_goals + away_goals

    edition_stats = [
        item
        for item in edition_stats_by_season.values()
        if int(item.get("matchesCount") or 0) > 0
    ]

    sorted_by_goals = sorted(
        edition_stats,
        key=lambda item: (
            -int(item["goalsCount"]),
            -int(item["matchesCount"]),
            -int(item["year"]),
        ),
    )
    sorted_by_goal_average = sorted(
        edition_stats,
        key=lambda item: (
            -(int(item["goalsCount"]) / int(item["matchesCount"])),
            -int(item["goalsCount"]),
            -int(item["year"]),
        ),
    )

    return {
        "goalsPerMatch": {
            "label": "Edições com maior média de gols por jogo",
            "metricLabel": "Média",
            "items": _assign_dense_ranks(
                [
                    {
                        "seasonLabel": item["seasonLabel"],
                        "year": int(item["year"]),
                        "editionName": item["editionName"],
                        "matchesCount": int(item["matchesCount"]),
                        "goalsCount": int(item["goalsCount"]),
                        "goalsPerMatch": round(int(item["goalsCount"]) / int(item["matchesCount"]), 2),
                    }
                    for item in sorted_by_goal_average
                ],
                lambda item: item["goalsPerMatch"],
            ),
        },
        "goals": {
            "label": "Edições com mais gols",
            "metricLabel": "Gols",
            "items": _assign_dense_ranks(
                [
                    {
                        "seasonLabel": item["seasonLabel"],
                        "year": int(item["year"]),
                        "editionName": item["editionName"],
                        "matchesCount": int(item["matchesCount"]),
                        "goalsCount": int(item["goalsCount"]),
                    }
                    for item in sorted_by_goals
                ],
                lambda item: (int(item["goalsCount"]), int(item["matchesCount"])),
            ),
        },
    }


def _build_world_cup_squad_appearance_rankings(
    squad_rows: list[dict[str, Any]],
    profile_refs: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    players_by_key: dict[str, dict[str, Any]] = {}
    resolved_profile_refs = profile_refs or {}

    for row in squad_rows:
        player_id = _safe_int(row.get("player_id"))
        season_label = row.get("season_label")
        if player_id is None or season_label is None:
            continue

        player_key = _serialize_wc_player_id(player_id, resolved_profile_refs)
        if player_key is None:
            continue

        profile_ref = _resolve_wc_player_profile_ref(resolved_profile_refs, player_id)
        team = _serialize_team(_safe_int(row.get("team_id")), row.get("team_name"))
        player_entry = players_by_key.setdefault(
            player_key,
            {
                "playerId": player_key,
                "imageAssetId": str(player_id),
                "playerName": _sanitize_display_name(row.get("player_name")),
                "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
                "teamId": team.get("teamId") if team else None,
                "teamName": team.get("teamName") if team else None,
                "editions": [],
            },
        )

        if team is not None:
            player_entry["teamId"] = team.get("teamId")
            player_entry["teamName"] = team.get("teamName")

        player_entry["editions"].append(
            {
                "seasonLabel": season_label,
                "year": int(season_label),
            }
        )

    players_payload = sorted(
        players_by_key.values(),
        key=lambda item: (
            -len(item["editions"]),
            _normalize_compare_key(item.get("playerName")) or "",
        ),
    )

    return {
        "squadAppearances": {
            "label": "Jogadores com mais copas disputadas",
            "metricLabel": "Copas",
            "minimumAppearancesCount": MINIMUM_SQUAD_EDITIONS_FOR_PLAYER_RANKINGS,
            "items": _assign_dense_ranks(
                [
                    {
                        "playerId": item["playerId"],
                        "imageAssetId": item.get("imageAssetId"),
                        "playerName": item.get("playerName"),
                        "profileUrl": item.get("profileUrl"),
                        "teamId": item.get("teamId"),
                        "teamName": item.get("teamName"),
                        "appearancesCount": len(item["editions"]),
                        "editions": sorted(item["editions"], key=lambda edition: edition["year"]),
                    }
                    for item in players_payload
                    if len(item["editions"]) >= MINIMUM_SQUAD_EDITIONS_FOR_PLAYER_RANKINGS
                ],
                lambda item: int(item["appearancesCount"]),
            ),
        }
    }


def _build_world_cup_match_rankings(
    fixture_rows: list[dict[str, Any]],
    finals_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    highest_scoring_finals = _assign_dense_ranks(
        [
            {
                "seasonLabel": final["seasonLabel"],
                "year": int(final["year"]),
                "homeTeam": final.get("homeTeam"),
                "awayTeam": final.get("awayTeam"),
                "homeScore": int(final["homeScore"]),
                "awayScore": int(final["awayScore"]),
                "shootout": final.get("shootout"),
                "venueName": final.get("venueName"),
                "totalGoals": int(final["homeScore"]) + int(final["awayScore"]),
            }
            for final in sorted(
                [
                    final
                    for final in finals_payload
                    if final.get("homeScore") is not None and final.get("awayScore") is not None
                ],
                key=lambda item: (
                    -(int(item["homeScore"]) + int(item["awayScore"])),
                    -int(item["year"]),
                ),
            )
        ],
        lambda item: int(item["totalGoals"]),
    )

    biggest_wins = _assign_dense_ranks(
        [
            {
                "fixtureId": str(row["fixture_id"]),
                "seasonLabel": row["season_label"],
                "year": int(row["season_label"]),
                "homeTeam": _serialize_team(row.get("home_team_id"), row.get("home_team_name")),
                "awayTeam": _serialize_team(row.get("away_team_id"), row.get("away_team_name")),
                "homeScore": int(row["home_goals"]),
                "awayScore": int(row["away_goals"]),
                "goalDiff": abs(int(row["home_goals"]) - int(row["away_goals"])),
                "totalGoals": int(row["home_goals"]) + int(row["away_goals"]),
                "venueName": translate_world_cup_venue_name(_normalize_text(row.get("venue_name"))),
            }
            for row in sorted(
                [
                    row
                    for row in fixture_rows
                    if row.get("season_label") is not None
                    and row.get("fixture_id") is not None
                    and row.get("home_goals") is not None
                    and row.get("away_goals") is not None
                    and _safe_int(row.get("home_goals")) != _safe_int(row.get("away_goals"))
                ],
                key=lambda item: (
                    -abs(int(item["home_goals"]) - int(item["away_goals"])),
                    -(int(item["home_goals"]) + int(item["away_goals"])),
                    -int(item["season_label"]),
                ),
            )
        ],
        lambda item: (int(item["goalDiff"]), int(item["totalGoals"])),
    )

    return {
        "highestScoringFinals": {
            "label": "Finais com mais gols",
            "metricLabel": "Gols",
            "items": highest_scoring_finals[:10],
        },
        "biggestWins": {
            "label": "Maiores goleadas",
            "metricLabel": "Saldo",
            "items": biggest_wins[:10],
        },
    }


def _resolve_fixture_winner(
    fixture_row: dict[str, Any],
    penalty_scores_by_fixture: dict[int, dict[str, int]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, bool]:
    fixture_id = int(fixture_row["fixture_id"])
    home_team_id = _safe_int(fixture_row.get("home_team_id"))
    away_team_id = _safe_int(fixture_row.get("away_team_id"))
    home_team_name = _normalize_text(fixture_row.get("home_team_name"))
    away_team_name = _normalize_text(fixture_row.get("away_team_name"))
    home_goals = _safe_int(fixture_row.get("home_goals"))
    away_goals = _safe_int(fixture_row.get("away_goals"))

    if (
        home_team_id is not None
        and away_team_id is not None
        and home_goals is not None
        and away_goals is not None
        and home_goals != away_goals
    ):
        if home_goals > away_goals:
            return (
                _serialize_team(home_team_id, home_team_name),
                _serialize_team(away_team_id, away_team_name),
                "single_match",
                False,
            )

        return (
            _serialize_team(away_team_id, away_team_name),
            _serialize_team(home_team_id, home_team_name),
            "single_match",
            False,
        )

    penalty_scores = penalty_scores_by_fixture.get(fixture_id)
    home_compare_key = _normalize_compare_key(home_team_name)
    away_compare_key = _normalize_compare_key(away_team_name)

    if (
        penalty_scores is not None
        and home_compare_key in penalty_scores
        and away_compare_key in penalty_scores
    ):
        home_penalties = penalty_scores[home_compare_key]
        away_penalties = penalty_scores[away_compare_key]

        if home_penalties > away_penalties:
            return (
                _serialize_team(home_team_id, home_team_name),
                _serialize_team(away_team_id, away_team_name),
                "penalties",
                False,
            )

        if away_penalties > home_penalties:
            return (
                _serialize_team(away_team_id, away_team_name),
                _serialize_team(home_team_id, home_team_name),
                "penalties",
                False,
            )

    override = MATCH_OUTCOME_OVERRIDES_BY_FIXTURE.get(fixture_id)
    if override is not None:
        if override.winner_team_id == home_team_id:
            return (
                _serialize_team(home_team_id, home_team_name),
                _serialize_team(away_team_id, away_team_name),
                override.resolution_type,
                True,
            )

        if override.winner_team_id == away_team_id:
            return (
                _serialize_team(away_team_id, away_team_name),
                _serialize_team(home_team_id, home_team_name),
                override.resolution_type,
                True,
            )

    return None, None, None, False


def _infer_winner_from_next_round(
    fixture_row: dict[str, Any],
    next_round_team_keys: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home_team_id = _safe_int(fixture_row.get("home_team_id"))
    away_team_id = _safe_int(fixture_row.get("away_team_id"))
    home_team_name = _normalize_text(fixture_row.get("home_team_name"))
    away_team_name = _normalize_text(fixture_row.get("away_team_name"))

    home_key = _team_reference_key(home_team_id, home_team_name)
    away_key = _team_reference_key(away_team_id, away_team_name)

    if home_key and home_key in next_round_team_keys and (away_key is None or away_key not in next_round_team_keys):
        return _serialize_team(home_team_id, home_team_name), _serialize_team(away_team_id, away_team_name)

    if away_key and away_key in next_round_team_keys and (home_key is None or home_key not in next_round_team_keys):
        return _serialize_team(away_team_id, away_team_name), _serialize_team(home_team_id, home_team_name)

    return None, None


def _resolve_final_from_summary(
    fixture_row: dict[str, Any],
    edition_summary: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    champion_team = edition_summary.get("champion")
    runner_up_team = edition_summary.get("runnerUp")
    if champion_team is None or runner_up_team is None:
        return None, None

    home_team_key = _team_reference_key(fixture_row.get("home_team_id"), fixture_row.get("home_team_name"))
    away_team_key = _team_reference_key(fixture_row.get("away_team_id"), fixture_row.get("away_team_name"))
    champion_key = _team_reference_key_from_payload(champion_team)
    runner_up_key = _team_reference_key_from_payload(runner_up_team)

    if home_team_key == champion_key and away_team_key == runner_up_key:
        return champion_team, runner_up_team

    if away_team_key == champion_key and home_team_key == runner_up_key:
        return champion_team, runner_up_team

    return None, None


def _serialize_shootout(
    fixture_row: dict[str, Any],
    penalty_scores_by_fixture: dict[int, dict[str, int]],
) -> dict[str, Any] | None:
    fixture_id = _safe_int(fixture_row.get("fixture_id"))
    if fixture_id is None:
        return None

    penalty_scores = penalty_scores_by_fixture.get(fixture_id)
    if not penalty_scores:
        return None

    home_key = _normalize_compare_key(fixture_row.get("home_team_name"))
    away_key = _normalize_compare_key(fixture_row.get("away_team_name"))
    if home_key not in penalty_scores or away_key not in penalty_scores:
        return None

    return {
        "home": int(penalty_scores[home_key]),
        "away": int(penalty_scores[away_key]),
    }


def _serialize_knockout_match(
    fixture_row: dict[str, Any],
    penalty_scores_by_fixture: dict[int, dict[str, int]],
    *,
    is_replay: bool,
) -> dict[str, Any]:
    home_team_id = _safe_int(fixture_row.get("home_team_id"))
    away_team_id = _safe_int(fixture_row.get("away_team_id"))

    return {
        "fixtureId": str(fixture_row["fixture_id"]),
        "kickoffAt": _serialize_datetime(fixture_row.get("date_utc") or fixture_row.get("match_date")),
        "venueName": translate_world_cup_venue_name(_normalize_text(fixture_row.get("venue_name"))),
        "homeTeam": _serialize_team(home_team_id, fixture_row.get("home_team_name")),
        "awayTeam": _serialize_team(away_team_id, fixture_row.get("away_team_name")),
        "homeScore": _safe_int(fixture_row.get("home_goals")),
        "awayScore": _safe_int(fixture_row.get("away_goals")),
        "shootout": _serialize_shootout(fixture_row, penalty_scores_by_fixture),
        "isReplay": is_replay,
    }


def _build_world_cup_hub_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    edition_rows = _fetch_edition_rows()
    match_counts_by_season = _fetch_match_counts_by_season()
    final_fixture_rows = _fetch_final_fixture_rows()
    final_round_rows = _fetch_final_round_rows()
    penalty_scores_by_fixture = _fetch_penalty_shootout_scores_by_fixture()
    historical_top_scorer = _fetch_historical_top_scorer()

    editions: list[dict[str, Any]] = []
    distinct_champion_keys: set[str] = set()
    complete_editions_count = 0

    for season_row in edition_rows:
        season_label = season_row["season_label"]
        host_country = translate_world_cup_display_name(_normalize_text(season_row.get("host_country")))
        host_country_team = serialize_world_cup_display_team(None, host_country)
        matches_count = match_counts_by_season.get(season_label, 0)
        count_teams = _safe_int(season_row.get("count_teams"))
        format_flags = season_row.get("format_flags") or {}

        champion_team: dict[str, Any] | None = None
        runner_up_team: dict[str, Any] | None = None
        resolution_type: str | None = None
        coverage_note: str | None = None
        final_venue = None
        used_override = False

        season_final_round = final_round_rows.get(season_label)
        if season_final_round:
            champion_row = season_final_round.get(1)
            runner_up_row = season_final_round.get(2)
            champion_team = _serialize_team(
                _safe_int(champion_row.get("team_id")) if champion_row else None,
                champion_row.get("team_name") if champion_row else None,
            )
            runner_up_team = _serialize_team(
                _safe_int(runner_up_row.get("team_id")) if runner_up_row else None,
                runner_up_row.get("team_name") if runner_up_row else None,
            )
            resolution_type = "final_round"
        else:
            final_fixture_row = final_fixture_rows.get(season_label)
            if final_fixture_row:
                final_venue = translate_world_cup_venue_name(_normalize_text(final_fixture_row.get("venue_name")))
                champion_team, runner_up_team, resolution_type, used_override = _resolve_fixture_winner(
                    final_fixture_row,
                    penalty_scores_by_fixture,
                )
                if used_override:
                    coverage_note = MATCH_OUTCOME_OVERRIDES_BY_FIXTURE[int(final_fixture_row["fixture_id"])].note

        coverage, derived_coverage_note = _edition_coverage_payload(
            champion_team=champion_team,
            host_country=host_country,
            matches_count=matches_count,
            used_override=used_override,
        )
        if coverage["status"] == "complete":
            complete_editions_count += 1

        if coverage_note is None:
            coverage_note = derived_coverage_note

        champion_identity_key = _build_champion_identity_key(champion_team)
        if champion_identity_key is not None:
            distinct_champion_keys.add(champion_identity_key)

        editions.append(
            {
                "seasonLabel": season_label,
                "year": int(season_label),
                "editionName": build_world_cup_edition_name(season_label),
                "hostCountry": host_country,
                "hostCountryTeam": host_country_team,
                "teamsCount": count_teams,
                "matchesCount": matches_count,
                "champion": champion_team,
                "runnerUp": runner_up_team,
                "finalVenue": final_venue,
                "resolutionType": resolution_type,
                "coverage": coverage,
                "coverageNote": coverage_note,
                "formatFlags": format_flags if isinstance(format_flags, dict) else {},
            }
        )

    summary = {
        "editionsCount": len(editions),
        "matchesCount": sum(item["matchesCount"] for item in editions),
        "distinctChampionsCount": len(distinct_champion_keys),
        "topScorer": historical_top_scorer,
    }

    overall_coverage = build_coverage_from_counts(
        complete_editions_count,
        len(editions),
        "Cobertura das edições",
    )

    return (
        {
            "summary": summary,
            "editions": editions,
            "updatedAt": datetime.now(UTC).isoformat(),
        },
        overall_coverage,
    )


def _build_group_stage_payload(season_label: str) -> list[dict[str, Any]]:
    stage_rows = _fetch_group_stage_rows_for_season(season_label)
    if not stage_rows:
        return []

    grouped_stages: OrderedDict[str, OrderedDict[str, list[dict[str, Any]]]] = OrderedDict()
    for stage_key in GROUP_STAGE_SEQUENCE:
        grouped_stages[stage_key] = OrderedDict()

    for row in stage_rows:
        stage_key = row.get("stage_key")
        if stage_key not in grouped_stages:
            continue

        group_key = _normalize_text(row.get("group_key")) or ""
        grouped_stages[stage_key].setdefault(group_key, []).append(row)

    payload: list[dict[str, Any]] = []
    for stage_key in GROUP_STAGE_SEQUENCE:
        groups_map = grouped_stages.get(stage_key)
        if not groups_map:
            continue

        groups_payload: list[dict[str, Any]] = []
        for group_key in sorted(groups_map.keys(), key=_build_group_sort_key):
            rows = groups_map[group_key]
            groups_payload.append(
                {
                    "groupKey": group_key or None,
                    "groupLabel": _build_group_label(stage_key, group_key or None),
                    "rows": [
                        {
                            "teamId": (_serialize_team(_safe_int(row.get("team_id")), row.get("team_name")) or {}).get("teamId"),
                            "teamName": (_serialize_team(_safe_int(row.get("team_id")), row.get("team_name")) or {}).get("teamName"),
                            "position": int(row.get("position") or 0),
                            "matchesPlayed": int(row.get("games_played") or 0),
                            "wins": int(row.get("won") or 0),
                            "draws": int(row.get("draw") or 0),
                            "losses": int(row.get("lost") or 0),
                            "goalsFor": int(row.get("goals_for") or 0),
                            "goalsAgainst": int(row.get("goals_against") or 0),
                            "goalDiff": int(row.get("goal_diff") or 0),
                            "points": int(row.get("points") or 0),
                            "advanced": bool(row.get("advanced")),
                        }
                        for row in sorted(
                            rows,
                            key=lambda current_row: (
                                int(current_row.get("position") or 999),
                                _normalize_compare_key(current_row.get("team_name")) or "",
                            ),
                        )
                    ],
                }
            )

        payload.append(
            {
                "stageKey": stage_key,
                "stageLabel": GROUP_STAGE_LABELS.get(stage_key, stage_key),
                "groups": groups_payload,
            }
        )

    return payload


def _resolve_knockout_series(
    *,
    edition_summary: dict[str, Any],
    penalty_scores_by_fixture: dict[int, dict[str, int]],
    round_name: str,
    series_rows: list[dict[str, Any]],
    next_round_team_keys: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, str | None, bool]:
    deciding_row = series_rows[-1]
    resolved_winner, resolved_runner_up, resolution_type, used_override = _resolve_fixture_winner(
        deciding_row,
        penalty_scores_by_fixture,
    )

    if len(series_rows) > 1:
        if resolved_winner is not None:
            return (
                resolved_winner,
                resolved_runner_up,
                "replay",
                "Confronto decidido em replay histórico.",
                False,
            )

        inferred_winner, inferred_runner_up = _infer_winner_from_next_round(deciding_row, next_round_team_keys)
        if inferred_winner is not None:
            return (
                inferred_winner,
                inferred_runner_up,
                "replay_inferred",
                "Replay histórico sem resolução final detalhada na fonte bruta.",
                True,
            )

    if resolved_winner is not None:
        resolution_note = None
        if used_override:
            resolution_note = MATCH_OUTCOME_OVERRIDES_BY_FIXTURE[int(deciding_row["fixture_id"])].note

        return (
            resolved_winner,
            resolved_runner_up,
            resolution_type,
            resolution_note,
            used_override,
        )

    if round_name == "Final":
        final_winner, final_runner_up = _resolve_final_from_summary(deciding_row, edition_summary)
        if final_winner is not None:
            edition_note = _normalize_text(edition_summary.get("coverageNote"))
            is_partial = edition_summary.get("coverage", {}).get("status") == "partial"
            return (
                final_winner,
                final_runner_up,
                edition_summary.get("resolutionType") or "final_record",
                edition_note,
                is_partial,
            )

    inferred_winner, inferred_runner_up = _infer_winner_from_next_round(deciding_row, next_round_team_keys)
    if inferred_winner is not None:
        return (
            inferred_winner,
            inferred_runner_up,
            "advanced_to_next_round",
            INFERRED_KNOCKOUT_NOTE,
            True,
        )

    return (
        None,
        None,
        None,
        "Não foi possível identificar o classificado com segurança nesta chave.",
        True,
    )


def _build_knockout_rounds_payload(
    season_label: str,
    edition_summary: dict[str, Any],
    penalty_scores_by_fixture: dict[int, dict[str, int]],
) -> tuple[list[dict[str, Any]], list[str]]:
    fixture_rows = _fetch_knockout_fixture_rows_for_season(season_label)
    if not fixture_rows:
        return [], []

    rows_by_round: dict[str, list[dict[str, Any]]] = {}
    participant_keys_by_round: dict[str, set[str]] = {}
    for round_name in KNOCKOUT_ROUND_SEQUENCE:
        round_rows = [row for row in fixture_rows if row.get("round_name") == round_name]
        if not round_rows:
            continue

        rows_by_round[round_name] = round_rows
        participant_keys: set[str] = set()
        for row in round_rows:
            home_key = _team_reference_key(row.get("home_team_id"), row.get("home_team_name"))
            away_key = _team_reference_key(row.get("away_team_id"), row.get("away_team_name"))
            if home_key is not None:
                participant_keys.add(home_key)
            if away_key is not None:
                participant_keys.add(away_key)
        participant_keys_by_round[round_name] = participant_keys

    round_payloads: list[dict[str, Any]] = []
    coverage_notes: list[str] = []

    for round_index, round_name in enumerate(KNOCKOUT_ROUND_SEQUENCE):
        round_rows = rows_by_round.get(round_name)
        if not round_rows:
            continue

        next_round_name = None
        for candidate_round_name in KNOCKOUT_ROUND_SEQUENCE[round_index + 1 :]:
            if candidate_round_name in rows_by_round:
                next_round_name = candidate_round_name
                break
        next_round_team_keys = participant_keys_by_round.get(next_round_name, set())

        series_map: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for row in round_rows:
            pairing_key = _build_pairing_key(row)
            series_map.setdefault(pairing_key, []).append(row)

        round_ties: list[dict[str, Any]] = []
        for tie_position, (pairing_key, series_rows) in enumerate(series_map.items(), start=1):
            sorted_series_rows = sorted(
                series_rows,
                key=lambda row: (
                    _serialize_datetime(row.get("date_utc") or row.get("match_date")) or "",
                    int(row["fixture_id"]),
                ),
            )
            winner_team, runner_up_team, resolution_type, resolution_note, is_partial = _resolve_knockout_series(
                edition_summary=edition_summary,
                penalty_scores_by_fixture=penalty_scores_by_fixture,
                round_name=round_name,
                series_rows=sorted_series_rows,
                next_round_team_keys=next_round_team_keys,
            )
            if is_partial:
                _append_unique_note(coverage_notes, resolution_note)

            round_ties.append(
                {
                    "tieKey": f"{season_label}:{round_name}:{pairing_key}:{tie_position}",
                    "roundKey": round_name.casefold().replace(" ", "_").replace("-", "_"),
                    "roundLabel": KNOCKOUT_ROUND_LABELS.get(round_name, round_name),
                    "winner": winner_team,
                    "runnerUp": runner_up_team,
                    "resolutionType": resolution_type,
                    "resolutionNote": resolution_note,
                    "matches": [
                        _serialize_knockout_match(
                            row,
                            penalty_scores_by_fixture,
                            is_replay=len(sorted_series_rows) > 1 and match_index > 0,
                        )
                        for match_index, row in enumerate(sorted_series_rows)
                    ],
                }
            )

        round_payloads.append(
            {
                "roundKey": round_name.casefold().replace(" ", "_").replace("-", "_"),
                "roundLabel": KNOCKOUT_ROUND_LABELS.get(round_name, round_name),
                "ties": round_ties,
            }
        )

    return round_payloads, coverage_notes


def _build_world_cup_edition_payload(season_label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    hub_payload, _ = _build_world_cup_hub_payload()
    editions = hub_payload["editions"]
    current_index = next(
        (index for index, edition in enumerate(editions) if edition["seasonLabel"] == season_label),
        None,
    )
    if current_index is None:
        raise HTTPException(status_code=404, detail="Edição da Copa do Mundo não encontrada.")

    edition_summary = dict(editions[current_index])
    edition_top_scorers = _fetch_edition_top_scorers(season_label)
    group_stage_payload = _build_group_stage_payload(season_label)
    penalty_scores_by_fixture = _fetch_penalty_shootout_scores_by_fixture()
    knockout_round_payload, knockout_coverage_notes = _build_knockout_rounds_payload(
        season_label,
        edition_summary,
        penalty_scores_by_fixture,
    )

    coverage_notes: list[str] = []
    _append_unique_note(coverage_notes, edition_summary.get("coverageNote"))
    for note in knockout_coverage_notes:
        _append_unique_note(coverage_notes, note)

    if not edition_top_scorers:
        _append_unique_note(
            coverage_notes,
            "Artilharia da edição indisponível nas fontes brutas.",
        )

    filtered_edition_scorers = _filter_scorer_list_by_minimum_goals(edition_top_scorers)

    edition_summary["topScorer"] = edition_top_scorers[0] if edition_top_scorers else None
    edition_summary["coverageNotes"] = coverage_notes
    edition_summary["coverage"] = _edition_page_coverage_payload(coverage_notes)

    previous_edition = editions[current_index - 1] if current_index > 0 else None
    next_edition = editions[current_index + 1] if current_index + 1 < len(editions) else None

    return (
        {
            "edition": edition_summary,
            "navigation": {
                "previousEdition": _serialize_navigation_edition(previous_edition),
                "nextEdition": _serialize_navigation_edition(next_edition),
            },
            "groupStages": group_stage_payload,
            "knockoutRounds": knockout_round_payload,
            "scorers": filtered_edition_scorers,
            "updatedAt": datetime.now(UTC).isoformat(),
        },
        edition_summary["coverage"],
    )


def _resolve_team_edition_result(
    *,
    edition_summary: dict[str, Any] | None,
    knockout_presence: dict[str, Any] | None,
    stage_presence: dict[str, Any] | None,
    team_id: int,
    team_name: str | None,
) -> tuple[str, int]:
    team_key = _team_reference_key(team_id, team_name)
    champion_key = _team_reference_key_from_payload(edition_summary.get("champion") if edition_summary else None)
    runner_up_key = _team_reference_key_from_payload(edition_summary.get("runnerUp") if edition_summary else None)

    if team_key is not None and team_key == champion_key:
        return "Campeão", TEAM_RESULT_PRIORITY["Campeão"]

    if team_key is not None and team_key == runner_up_key:
        return "Vice-campeão", TEAM_RESULT_PRIORITY["Vice-campeão"]

    final_round_position = _safe_int(stage_presence.get("final_round_position") if stage_presence else None)
    if final_round_position is not None:
        return _build_team_final_round_label(final_round_position), TEAM_RESULT_PRIORITY["Fase final"]

    if knockout_presence and knockout_presence.get("has_semi_finals"):
        return "Semifinal", TEAM_RESULT_PRIORITY["Semifinal"]

    if knockout_presence and knockout_presence.get("has_quarter_finals"):
        return "Quartas de final", TEAM_RESULT_PRIORITY["Quartas de final"]

    if stage_presence and stage_presence.get("has_group_stage_2"):
        return "Segunda fase de grupos", TEAM_RESULT_PRIORITY["Segunda fase de grupos"]

    if knockout_presence and knockout_presence.get("has_round_of_16"):
        return "Oitavas de final", TEAM_RESULT_PRIORITY["Oitavas de final"]

    if knockout_presence and knockout_presence.get("has_round_of_32"):
        return "16 avos de final", TEAM_RESULT_PRIORITY["16 avos de final"]

    if stage_presence and stage_presence.get("has_group_stage_1"):
        return "Fase de grupos", TEAM_RESULT_PRIORITY["Fase de grupos"]

    return "Participação", TEAM_RESULT_PRIORITY["Participação"]


def _build_world_cup_team_catalog() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    hub_payload, _ = _build_world_cup_hub_payload()
    edition_summaries_by_season = {
        edition["seasonLabel"]: edition
        for edition in hub_payload["editions"]
    }

    team_match_rows = _fetch_team_match_rows()
    team_stage_rows = _fetch_team_stage_presence_rows()
    team_knockout_rows = _fetch_team_knockout_presence_rows()
    team_top_scorer_rows = _fetch_team_top_scorers_by_season()
    top_scorer_profile_refs = _fetch_wc_player_profile_refs(
        [_safe_int(row.get("player_id")) for row in team_top_scorer_rows]
    )

    stage_index = {
        (row["season_label"], int(row["team_id"])): row
        for row in team_stage_rows
        if row.get("season_label") is not None and row.get("team_id") is not None
    }
    knockout_index = {
        (row["season_label"], int(row["team_id"])): row
        for row in team_knockout_rows
        if row.get("season_label") is not None and row.get("team_id") is not None
    }
    top_scorer_index: dict[tuple[Any, int], dict[str, Any]] = {}
    for row in team_top_scorer_rows:
        if row.get("season_label") is None or row.get("team_id") is None:
            continue

        player_id = _safe_int(row.get("player_id"))
        profile_ref = _resolve_wc_player_profile_ref(top_scorer_profile_refs, player_id)
        top_scorer_index[(row["season_label"], int(row["team_id"]))] = {
            "playerId": _serialize_wc_player_id(player_id, top_scorer_profile_refs),
            "imageAssetId": str(player_id) if player_id is not None else None,
            "playerName": _sanitize_display_name(row.get("player_name")),
            "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
            "goals": int(row.get("goals") or 0),
        }

    teams_by_id: dict[str, dict[str, Any]] = {}

    for row in team_match_rows:
        season_label = row.get("season_label")
        team_id = _safe_int(row.get("team_id"))
        if season_label is None or team_id is None:
            continue

        team_name = _normalize_text(row.get("team_name"))
        participation_key = (season_label, team_id)
        edition_summary = edition_summaries_by_season.get(season_label)
        stage_presence = stage_index.get(participation_key)
        knockout_presence = knockout_index.get(participation_key)
        result_label, result_rank = _resolve_team_edition_result(
            edition_summary=edition_summary,
            knockout_presence=knockout_presence,
            stage_presence=stage_presence,
            team_id=team_id,
            team_name=team_name,
        )
        serialized_team = _serialize_team(team_id, team_name)
        display_team_id = serialized_team.get("teamId") if serialized_team else str(team_id)
        display_team_name = serialized_team.get("teamName") if serialized_team else translate_world_cup_display_name(team_name)

        teams_by_id.setdefault(
            display_team_id,
            {
                "teamId": display_team_id,
                "teamName": display_team_name,
                "participations": [],
                "sourceTeamIds": set(),
            },
        )
        team_entry = teams_by_id[display_team_id]
        if team_entry.get("teamName") is None and team_name is not None:
            team_entry["teamName"] = display_team_name
        team_entry["sourceTeamIds"].add(team_id)

        team_entry["participations"].append(
            {
                "seasonLabel": season_label,
                "year": int(season_label),
                "editionName": edition_summary.get("editionName") if edition_summary else build_world_cup_edition_name(season_label),
                "matchesCount": int(row.get("matches_count") or 0),
                "resultLabel": result_label,
                "resultRank": result_rank,
                "topScorer": top_scorer_index.get(participation_key),
            }
        )

    teams_payload: list[dict[str, Any]] = []
    for team_entry in teams_by_id.values():
        participations = sorted(
            team_entry["participations"],
            key=lambda participation: participation["year"],
        )
        if not participations:
            continue

        titles_count = sum(1 for participation in participations if participation["resultLabel"] == "Campeão")
        best_participation = min(
            participations,
            key=lambda participation: (
                participation["resultRank"],
                participation["year"],
            ),
        )
        team_payload = {
            "teamId": team_entry["teamId"],
            "teamName": team_entry["teamName"],
            "participationsCount": len(participations),
            "titlesCount": titles_count,
            "bestResultLabel": best_participation["resultLabel"],
            "firstEdition": participations[0]["year"],
            "lastEdition": participations[-1]["year"],
            "participations": participations,
            "sourceTeamIds": sorted(team_entry["sourceTeamIds"]),
        }
        teams_payload.append(team_payload)

    teams_payload.sort(
        key=lambda team: (
            -int(team["titlesCount"]),
            -int(team["participationsCount"]),
            TEAM_RESULT_PRIORITY.get(team["bestResultLabel"].split(" (")[0], TEAM_RESULT_PRIORITY["Participação"]),
            _normalize_compare_key(team.get("teamName")) or "",
        )
    )

    team_index: dict[str, dict[str, Any]] = {}
    for team in teams_payload:
        team_index[team["teamId"]] = team
        for source_team_id in team.get("sourceTeamIds", []):
            team_index[str(source_team_id)] = team

    return teams_payload, team_index


def _build_world_cup_team_list_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    teams_payload, _ = _build_world_cup_team_catalog()
    return (
        {
            "teams": [
                {
                    "teamId": team["teamId"],
                    "teamName": team["teamName"],
                    "participationsCount": team["participationsCount"],
                    "titlesCount": team["titlesCount"],
                    "bestResultLabel": team["bestResultLabel"],
                    "firstEdition": team["firstEdition"],
                    "lastEdition": team["lastEdition"],
                }
                for team in teams_payload
            ],
            "updatedAt": datetime.now(UTC).isoformat(),
        },
        build_coverage_from_counts(len(teams_payload), len(teams_payload), "Seleções com participação"),
    )


def _build_world_cup_team_detail_payload(team_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _, team_index = _build_world_cup_team_catalog()
    normalized_team_id = _normalize_text(team_id)
    if normalized_team_id is None:
        raise HTTPException(status_code=404, detail="Seleção da Copa do Mundo não encontrada.")

    team_payload = team_index.get(normalized_team_id)
    if team_payload is None:
        numeric_team_id = _safe_int(normalized_team_id)
        if numeric_team_id is not None:
            team_payload = team_index.get(str(numeric_team_id))
    if team_payload is None:
        raise HTTPException(status_code=404, detail="Seleção da Copa do Mundo não encontrada.")

    source_team_ids = [int(source_team_id) for source_team_id in team_payload.get("sourceTeamIds", [])]
    historical_scorers = _filter_scorer_list_by_minimum_goals(_fetch_team_historical_scorers(source_team_ids))

    return (
        {
            "team": {
                "teamId": team_payload["teamId"],
                "teamName": team_payload["teamName"],
                "participationsCount": team_payload["participationsCount"],
                "titlesCount": team_payload["titlesCount"],
                "bestResultLabel": team_payload["bestResultLabel"],
                "firstEdition": team_payload["firstEdition"],
                "lastEdition": team_payload["lastEdition"],
            },
            "participations": team_payload["participations"],
            "historicalScorers": historical_scorers,
            "updatedAt": datetime.now(UTC).isoformat(),
        },
        {
            "status": "complete",
            "label": "Cobertura completa",
            "percentage": 100,
        },
    )


def _build_world_cup_rankings_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    hub_payload, _ = _build_world_cup_hub_payload()
    editions = hub_payload["editions"]
    teams_payload, _ = _build_world_cup_team_catalog()
    historical_scorer_rows = _fetch_historical_scorer_rows()
    historical_scorer_edition_rows = _fetch_historical_scorer_edition_rows()
    ranking_fixture_rows = _fetch_ranking_fixture_rows()
    squad_appearance_rows = _fetch_player_squad_appearance_rows()
    squad_profile_refs = _fetch_wc_player_profile_refs(
        [_safe_int(row.get("player_id")) for row in squad_appearance_rows]
    )
    final_fixture_rows = _fetch_final_fixture_rows()
    penalty_scores_by_fixture = _fetch_penalty_shootout_scores_by_fixture()
    scorer_profile_refs = _fetch_wc_player_profile_refs(
        [_safe_int(row.get("player_id")) for row in historical_scorer_rows]
    )

    scorer_editions_index: dict[str, list[dict[str, Any]]] = {}
    for row in historical_scorer_edition_rows:
        scorer_key = row.get("scorer_key")
        season_label = row.get("season_label")
        if scorer_key is None or season_label is None:
            continue

        team = _serialize_team(_safe_int(row.get("team_id")), row.get("team_name"))
        scorer_editions_index.setdefault(scorer_key, []).append(
            {
                "seasonLabel": season_label,
                "year": int(season_label),
                "teamId": team.get("teamId") if team else None,
                "teamName": team.get("teamName") if team else None,
                "goals": int(row.get("goals") or 0),
            }
        )

    scorers_payload: list[dict[str, Any]] = []
    current_scorer_rank = 0
    previous_scorer_goals: int | None = None
    for scorer_row in historical_scorer_rows:
        goals = int(scorer_row.get("goals") or 0)
        if previous_scorer_goals != goals:
            current_scorer_rank += 1
            previous_scorer_goals = goals

        scorer_key = scorer_row.get("scorer_key")
        player_id = _safe_int(scorer_row.get("player_id"))
        profile_ref = _resolve_wc_player_profile_ref(scorer_profile_refs, player_id)
        team = _serialize_team(_safe_int(scorer_row.get("team_id")), scorer_row.get("team_name"))
        scorers_payload.append(
            {
                "rank": current_scorer_rank,
                "playerId": _serialize_wc_player_id(player_id, scorer_profile_refs),
                "imageAssetId": str(player_id) if player_id is not None else None,
                "playerName": _sanitize_display_name(scorer_row.get("player_name")),
                "profileUrl": profile_ref["profileUrl"] if profile_ref is not None else None,
                "teamId": team.get("teamId") if team else None,
                "teamName": team.get("teamName") if team else None,
                "goals": goals,
                "editions": sorted(
                    scorer_editions_index.get(scorer_key or "", []),
                    key=lambda edition: edition["year"],
                ),
            }
        )

    scorers_payload = _filter_scorer_list_by_minimum_goals(scorers_payload)

    team_rankings_payload = _build_world_cup_titles_team_ranking(teams_payload, editions)
    team_rankings = _build_world_cup_team_stat_rankings(teams_payload, ranking_fixture_rows)
    edition_rankings = _build_world_cup_edition_rankings(editions, ranking_fixture_rows)
    player_rankings = {
        "scorers": {
            "label": "Artilheiros históricos",
            "metricLabel": "Gols",
            "items": scorers_payload,
        },
        **_build_world_cup_squad_appearance_rankings(squad_appearance_rows, squad_profile_refs),
    }

    finals_payload: list[dict[str, Any]] = []
    omitted_editions: list[dict[str, Any]] = []
    for edition in sorted(editions, key=lambda item: int(item["year"]), reverse=True):
        final_fixture_row = final_fixture_rows.get(edition["seasonLabel"])
        if final_fixture_row is None:
            final_fixture_row = _find_final_round_decider_fixture_row(edition, ranking_fixture_rows)

        if final_fixture_row is None:
            if edition.get("resolutionType") == "final_round":
                omitted_editions.append(
                    {
                        "seasonLabel": edition["seasonLabel"],
                        "year": edition["year"],
                        "reason": "A edição foi decidida por fase final em grupos e não teve jogo decisivo localizável na base.",
                    }
                )
            continue

        displayed_final_fixture_row = _orient_final_fixture_row_for_display(edition, final_fixture_row)
        resolution_note = edition.get("coverageNote")
        if edition.get("resolutionType") == "final_round" and not resolution_note:
            resolution_note = "Jogo decisivo da fase final em grupos."

        finals_payload.append(
            {
                "seasonLabel": edition["seasonLabel"],
                "year": edition["year"],
                "homeTeam": _serialize_team(
                    displayed_final_fixture_row.get("home_team_id"),
                    displayed_final_fixture_row.get("home_team_name"),
                ),
                "awayTeam": _serialize_team(
                    displayed_final_fixture_row.get("away_team_id"),
                    displayed_final_fixture_row.get("away_team_name"),
                ),
                "homeScore": _safe_int(displayed_final_fixture_row.get("home_goals")),
                "awayScore": _safe_int(displayed_final_fixture_row.get("away_goals")),
                "shootout": _serialize_shootout(displayed_final_fixture_row, penalty_scores_by_fixture),
                "venueName": translate_world_cup_venue_name(_normalize_text(displayed_final_fixture_row.get("venue_name"))),
                "champion": edition.get("champion"),
                "runnerUp": edition.get("runnerUp"),
                "resolutionType": edition.get("resolutionType"),
                "resolutionNote": resolution_note,
            }
        )

    match_rankings = _build_world_cup_match_rankings(ranking_fixture_rows, finals_payload)

    return (
        {
            "scorers": scorers_payload,
            "teams": team_rankings_payload,
            "teamRankings": {
                "titles": {
                    "label": "Seleções com mais títulos",
                    "metricLabel": "Títulos",
                    "items": team_rankings_payload,
                },
                **team_rankings,
            },
            "editionRankings": edition_rankings,
            "playerRankings": player_rankings,
            "matchRankings": match_rankings,
            "finals": {
                "items": finals_payload,
                "omittedEditions": omitted_editions,
            },
            "updatedAt": datetime.now(UTC).isoformat(),
        },
        {
            "status": "complete",
            "label": "Cobertura completa",
            "percentage": 100,
        },
    )


@router.get("/api/v1/world-cup/hub")
def get_world_cup_hub(request: Request) -> dict[str, Any]:
    data, coverage = _build_world_cup_hub_payload()
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/api/v1/world-cup/editions/{season_label}")
def get_world_cup_edition(season_label: str, request: Request) -> dict[str, Any]:
    data, coverage = _build_world_cup_edition_payload(season_label)
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/api/v1/world-cup/teams")
def get_world_cup_team_list(request: Request) -> dict[str, Any]:
    data, coverage = _build_world_cup_team_list_payload()
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/api/v1/world-cup/teams/{team_id}")
def get_world_cup_team_detail(team_id: str, request: Request) -> dict[str, Any]:
    data, coverage = _build_world_cup_team_detail_payload(team_id)
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )


@router.get("/api/v1/world-cup/rankings")
def get_world_cup_rankings(request: Request) -> dict[str, Any]:
    data, coverage = _build_world_cup_rankings_payload()
    return build_api_response(
        data,
        request_id=_request_id(request),
        coverage=coverage,
    )
