from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalCompetition:
    competition_id: int
    competition_key: str
    default_name: str
    source_ids: tuple[int, ...]
    season_calendar: str


_CANONICAL_COMPETITIONS = (
    CanonicalCompetition(
        competition_id=71,
        competition_key="brasileirao_a",
        default_name="Campeonato Brasileiro Série A",
        source_ids=(71, 648),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=651,
        competition_key="brasileirao_b",
        default_name="Campeonato Brasileiro Série B",
        source_ids=(651,),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=390,
        competition_key="libertadores",
        default_name="Copa Libertadores da América",
        source_ids=(390, 1122),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=1116,
        competition_key="sudamericana",
        default_name="Copa Sudamericana",
        source_ids=(1116,),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=732,
        competition_key="copa_do_brasil",
        default_name="Copa do Brasil",
        source_ids=(732, 654),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=1798,
        competition_key="supercopa_do_brasil",
        default_name="Supercopa do Brasil",
        source_ids=(1798,),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=1452,
        competition_key="fifa_intercontinental_cup",
        default_name="FIFA Intercontinental Cup",
        source_ids=(1452,),
        season_calendar="annual",
    ),
    CanonicalCompetition(
        competition_id=8,
        competition_key="premier_league",
        default_name="Premier League",
        source_ids=(8,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=2,
        competition_key="champions_league",
        default_name="UEFA Champions League",
        source_ids=(2,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=564,
        competition_key="la_liga",
        default_name="La Liga",
        source_ids=(564,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=384,
        competition_key="serie_a_italy",
        default_name="Serie A (Itália)",
        source_ids=(384,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=82,
        competition_key="bundesliga",
        default_name="Bundesliga",
        source_ids=(82,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=301,
        competition_key="ligue_1",
        default_name="Ligue 1",
        source_ids=(301,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=462,
        competition_key="primeira_liga",
        default_name="Liga Portugal",
        source_ids=(462,),
        season_calendar="split_year",
    ),
    CanonicalCompetition(
        competition_id=0,
        competition_key="fifa_world_cup_mens",
        default_name="Copa do Mundo FIFA",
        source_ids=(7000547241627854950,),
        season_calendar="annual",
    ),
)

_CANONICAL_COMPETITIONS_BY_ID: dict[int, CanonicalCompetition] = {
    competition.competition_id: competition for competition in _CANONICAL_COMPETITIONS
}
_CANONICAL_COMPETITIONS_BY_KEY: dict[str, CanonicalCompetition] = {
    competition.competition_key: competition for competition in _CANONICAL_COMPETITIONS
}
_CANONICAL_COMPETITIONS_BY_SOURCE_ID: dict[int, CanonicalCompetition] = {
    source_id: competition
    for competition in _CANONICAL_COMPETITIONS
    for source_id in competition.source_ids
}


def get_canonical_competition(competition_id: int | None) -> CanonicalCompetition | None:
    if competition_id is None:
        return None
    return _CANONICAL_COMPETITIONS_BY_SOURCE_ID.get(competition_id) or _CANONICAL_COMPETITIONS_BY_ID.get(
        competition_id
    )


def get_canonical_competition_by_key(competition_key: str | None) -> CanonicalCompetition | None:
    if competition_key is None:
        return None
    normalized_key = competition_key.strip()
    if normalized_key == "":
        return None
    return _CANONICAL_COMPETITIONS_BY_KEY.get(normalized_key)


def list_canonical_competition_ids() -> tuple[int, ...]:
    return tuple(_CANONICAL_COMPETITIONS_BY_ID.keys())


def list_supported_competition_source_ids() -> tuple[int, ...]:
    return tuple(_CANONICAL_COMPETITIONS_BY_SOURCE_ID.keys())


def expand_competition_ids_for_query(competition_id: int | None) -> tuple[int, ...]:
    canonical_competition = get_canonical_competition(competition_id)
    if canonical_competition is None:
        return (competition_id,) if competition_id is not None else tuple()
    return canonical_competition.source_ids


def normalize_competition_id(competition_id: int | None) -> int | None:
    canonical_competition = get_canonical_competition(competition_id)
    if canonical_competition is None:
        return competition_id
    return canonical_competition.competition_id


def _format_season_label(
    canonical_competition: CanonicalCompetition,
    normalized_season_id: str,
) -> str:
    if "/" in normalized_season_id:
        return normalized_season_id

    if canonical_competition.season_calendar != "split_year":
        return normalized_season_id

    if not normalized_season_id.isdigit() or len(normalized_season_id) != 4:
        return normalized_season_id

    season_start = int(normalized_season_id)
    return f"{season_start}/{season_start + 1}"


def build_canonical_context(
    *,
    competition_id: int | None,
    competition_name: str | None,
    season_id: int | str | None,
) -> dict[str, str] | None:
    canonical_competition = get_canonical_competition(competition_id)
    if canonical_competition is None or season_id is None:
        return None

    normalized_season_id = str(season_id).strip()
    if normalized_season_id == "":
        return None

    use_default_name = competition_id != canonical_competition.competition_id

    return {
        "competitionId": str(canonical_competition.competition_id),
        "competitionKey": canonical_competition.competition_key,
        "competitionName": canonical_competition.default_name
        if use_default_name or not isinstance(competition_name, str) or competition_name.strip() == ""
        else competition_name.strip(),
        "seasonId": normalized_season_id,
        "seasonLabel": _format_season_label(canonical_competition, normalized_season_id),
    }


def select_default_context(
    available_contexts: list[dict[str, str]],
    *,
    preferred_competition_id: int | None,
    preferred_season_id: int | None,
) -> dict[str, str] | None:
    if not available_contexts:
        return None

    normalized_preferred_competition_id = normalize_competition_id(preferred_competition_id)
    preferred_competition = (
        str(normalized_preferred_competition_id)
        if normalized_preferred_competition_id is not None
        else None
    )
    preferred_season = str(preferred_season_id) if preferred_season_id is not None else None

    if preferred_competition is not None and preferred_season is not None:
        for context in available_contexts:
            if (
                context.get("competitionId") == preferred_competition
                and context.get("seasonId") == preferred_season
            ):
                return context

    if preferred_competition is not None:
        for context in available_contexts:
            if context.get("competitionId") == preferred_competition:
                return context

    if preferred_season is not None:
        for context in available_contexts:
            if context.get("seasonId") == preferred_season:
                return context

    return available_contexts[0]
