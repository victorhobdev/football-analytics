from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from common.http_client import ProviderHttpClient

from .base import ProviderAdapter
from .envelope import build_envelope


SPORTMONKS_TO_APIFOOTBALL_STAT_NAME = {
    "SHOTS_ON_TARGET": "Shots on Goal",
    "SHOTS_OFF_TARGET": "Shots off Goal",
    "SHOTS_TOTAL": "Total Shots",
    "SHOTS_BLOCKED": "Blocked Shots",
    "SHOTS_INSIDEBOX": "Shots insidebox",
    "SHOTS_OUTSIDEBOX": "Shots outsidebox",
    "FOULS": "Fouls",
    "CORNERS": "Corner Kicks",
    "OFFSIDES": "Offsides",
    "BALL_POSSESSION": "Ball Possession",
    "YELLOWCARDS": "Yellow Cards",
    "REDCARDS": "Red Cards",
    "SAVES": "Goalkeeper Saves",
    "PASSES": "Total passes",
    "SUCCESSFUL_PASSES": "Passes accurate",
    "SUCCESSFUL_PASSES_PERCENTAGE": "Passes %",
}


class SportMonksProvider(ProviderAdapter):
    name = "sportmonks"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        requests_per_minute: int | None = None,
    ):
        self._api_key = api_key
        self._client = ProviderHttpClient.from_env(
            provider=self.name,
            base_url=base_url,
            requests_per_minute=requests_per_minute,
        )

    def _request(
        self,
        *,
        endpoint: str,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload, headers = self._client.request_json(
            endpoint=endpoint,
            params={"api_token": self._api_key, **params},
        )
        return payload, headers

    @staticmethod
    def _resolve_home_away(participants: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        home = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
        away = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)
        if home and away:
            return home, away

        fallback = list(participants[:2]) + [{}, {}]
        return fallback[0], fallback[1]

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _paginate_fixtures_between(
        self,
        *,
        date_from: str,
        date_to: str,
    ) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
        page = 1
        rows: list[dict[str, Any]] = []
        last_headers: dict[str, str] = {}
        last_meta: dict[str, Any] = {}

        while True:
            payload, headers = self._request(
                endpoint=f"/fixtures/between/{date_from}/{date_to}",
                params={
                    "include": "participants;scores;scores.type;league;season;venue;state;round;stage",
                    "per_page": 100,
                    "page": page,
                },
            )
            data = payload.get("data") or []
            if isinstance(data, dict):
                rows.append(data)
            elif isinstance(data, list):
                rows.extend(data)

            pagination = payload.get("pagination") or {}
            last_headers = headers
            last_meta = {
                "pagination": pagination,
                "subscription": payload.get("subscription", {}),
                "rate_limit": payload.get("rate_limit", {}),
                "timezone": payload.get("timezone"),
            }
            if not pagination.get("has_more"):
                break
            page += 1

        return rows, last_headers, last_meta

    @staticmethod
    def _extract_goals(
        scores: list[dict[str, Any]],
        *,
        home_team_id: int | None,
        away_team_id: int | None,
    ) -> tuple[int | None, int | None]:
        preferred = {"CURRENT", "FT", "FULLTIME"}
        score_rows = [s for s in scores if str(s.get("description", "")).upper() in preferred]
        if not score_rows:
            score_rows = scores

        home_goals = None
        away_goals = None
        for row in score_rows:
            participant_id = row.get("participant_id")
            goals = (row.get("score") or {}).get("goals")
            if participant_id == home_team_id:
                home_goals = goals
            elif participant_id == away_team_id:
                away_goals = goals
            elif participant_id is None:
                participant_side = ((row.get("score") or {}).get("participant") or "").lower()
                if participant_side == "home":
                    home_goals = goals
                elif participant_side == "away":
                    away_goals = goals
        return home_goals, away_goals

    def _map_fixture_row(self, row: dict[str, Any], season: int) -> dict[str, Any]:
        participants = row.get("participants") or []
        home_team, away_team = self._resolve_home_away(participants)
        home_team_id = self._as_int(home_team.get("id"))
        away_team_id = self._as_int(away_team.get("id"))

        scores = row.get("scores") or []
        home_goals, away_goals = self._extract_goals(
            scores,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )

        state = row.get("state") or {}
        venue = row.get("venue") or {}
        league = row.get("league") or {}
        round_info = row.get("round") or {}
        stage_info = row.get("stage") or {}

        round_name = round_info.get("name")
        stage_name = stage_info.get("name")
        if round_name and stage_name:
            league_round = f"{stage_name} - {round_name}"
        else:
            league_round = round_name or stage_name

        kickoff_raw = row.get("starting_at")
        kickoff_utc = None
        if isinstance(kickoff_raw, str):
            try:
                kickoff_utc = (
                    datetime.strptime(kickoff_raw, "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=timezone.utc)
                    .isoformat()
                )
            except ValueError:
                kickoff_utc = kickoff_raw

        return {
            "fixture": {
                "id": self._as_int(row.get("id")),
                "date": kickoff_utc,
                "timestamp": self._as_int(row.get("starting_at_timestamp")),
                "timezone": "UTC",
                "referee": None,
                "venue": {
                    "id": self._as_int(venue.get("id")),
                    "name": venue.get("name"),
                    "city": venue.get("city_name"),
                },
                "status": {
                    "short": state.get("short_name") or state.get("developer_name"),
                    "long": state.get("name"),
                },
            },
            "league": {
                "id": self._as_int(row.get("league_id")),
                "name": league.get("name"),
                "season": season,
                "round": league_round,
            },
            "teams": {
                "home": {"id": home_team_id, "name": home_team.get("name")},
                "away": {"id": away_team_id, "name": away_team.get("name")},
            },
            "goals": {"home": self._as_int(home_goals), "away": self._as_int(away_goals)},
        }

    @staticmethod
    def _season_matches(row: dict[str, Any], season: int) -> bool:
        if str(row.get("season_id")) == str(season):
            return True
        season_obj = row.get("season") or {}
        season_name = str(season_obj.get("name") or "")
        start_at = str(season_obj.get("starting_at") or "")
        end_at = str(season_obj.get("ending_at") or "")
        season_text = str(season)
        return season_text in season_name or start_at.startswith(season_text) or end_at.startswith(season_text)

    @staticmethod
    def _season_row_matches(season_row: dict[str, Any], season: int) -> bool:
        season_text = str(season)
        if str(season_row.get("id")) == season_text:
            return True
        if str(season_row.get("year")) == season_text:
            return True
        name = str(season_row.get("name") or "")
        start_at = str(season_row.get("starting_at") or "")
        end_at = str(season_row.get("ending_at") or "")
        return season_text in name or start_at.startswith(season_text) or end_at.startswith(season_text)

    def _resolve_season_id(self, *, league_id: int, season: int) -> int:
        payload, _headers = self._request(
            endpoint=f"/leagues/{league_id}",
            params={"include": "seasons"},
        )
        league_data = payload.get("data") or {}
        seasons = league_data.get("seasons") or []
        if isinstance(seasons, dict):
            seasons = [seasons]
        for season_row in seasons:
            if self._season_row_matches(season_row, season):
                season_id = self._as_int(season_row.get("id"))
                if season_id is not None:
                    return season_id
        raise RuntimeError(
            "Nao foi possivel resolver season_id no SportMonks "
            f"para league_id={league_id} season={season}."
        )

    def get_fixtures(
        self,
        *,
        league_id: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        rows, headers, provider_meta = self._paginate_fixtures_between(
            date_from=date_from,
            date_to=date_to,
        )
        filtered = [
            row
            for row in rows
            if str(row.get("league_id")) == str(league_id) and self._season_matches(row, season)
        ]
        mapped_rows = [self._map_fixture_row(row, season) for row in filtered]
        payload = build_envelope(
            provider=self.name,
            entity_type="fixtures",
            response=mapped_rows,
            source_params={
                "league_id": league_id,
                "season": season,
                "date_from": date_from,
                "date_to": date_to,
            },
            provider_meta={**provider_meta, "endpoint": "/fixtures/between/{from}/{to}"},
        )
        return payload, headers

    @staticmethod
    def _metric_name(stat_type: dict[str, Any]) -> str:
        developer_name = stat_type.get("developer_name")
        if developer_name in SPORTMONKS_TO_APIFOOTBALL_STAT_NAME:
            return SPORTMONKS_TO_APIFOOTBALL_STAT_NAME[developer_name]
        return stat_type.get("name") or str(stat_type.get("id") or "unknown")

    @staticmethod
    def _extract_stat_value(raw: Any) -> Any:
        if isinstance(raw, dict):
            if "value" in raw:
                return raw.get("value")
            if len(raw) == 1:
                return next(iter(raw.values()))
            return raw
        return raw

    def get_fixture_statistics(
        self,
        *,
        fixture_id: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = f"/fixtures/{fixture_id}"
        payload, headers = self._request(
            endpoint=endpoint,
            params={"include": "statistics;statistics.type;statistics.participant"},
        )
        fixture_data = payload.get("data") or {}
        stats_rows = fixture_data.get("statistics") or []
        grouped: dict[int, dict[str, Any]] = defaultdict(
            lambda: {"team": {"id": None, "name": None}, "statistics": []}
        )

        for stat in stats_rows:
            participant = stat.get("participant") or {}
            participant_id = self._as_int(stat.get("participant_id")) or self._as_int(participant.get("id"))
            if participant_id is None:
                continue
            group = grouped[participant_id]
            group["team"]["id"] = participant_id
            group["team"]["name"] = participant.get("name")

            stat_type = stat.get("type") or {}
            group["statistics"].append(
                {
                    "type": self._metric_name(stat_type),
                    "value": self._extract_stat_value(stat.get("data")),
                }
            )

        response_rows = list(grouped.values())
        canonical = build_envelope(
            provider=self.name,
            entity_type="statistics",
            response=response_rows,
            source_params={"fixture": fixture_id},
            provider_meta={
                "endpoint": endpoint,
                "rate_limit": payload.get("rate_limit", {}),
                "subscription": payload.get("subscription", {}),
                "timezone": payload.get("timezone"),
            },
        )
        return canonical, headers

    def get_fixture_events(
        self,
        *,
        fixture_id: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        endpoint = f"/fixtures/{fixture_id}"
        payload, headers = self._request(
            endpoint=endpoint,
            params={
                "include": "events;events.type;events.participant;events.player;events.relatedplayer"
            },
        )
        fixture_data = payload.get("data") or {}
        events = fixture_data.get("events") or []
        response_rows = []
        for event in events:
            participant = event.get("participant") or {}
            event_type = event.get("type") or {}
            player = event.get("player") or {}
            related_player = event.get("relatedplayer") or {}
            detail = event.get("info") or event.get("addition") or event_type.get("name")
            response_rows.append(
                {
                    "time": {
                        "elapsed": self._as_int(event.get("minute")),
                        "extra": self._as_int(event.get("extra_minute")),
                    },
                    "team": {
                        "id": self._as_int(event.get("participant_id")) or self._as_int(participant.get("id")),
                        "name": participant.get("name"),
                    },
                    "player": {
                        "id": self._as_int(event.get("player_id")) or self._as_int(player.get("id")),
                        "name": event.get("player_name") or player.get("name"),
                    },
                    "assist": {
                        "id": self._as_int(event.get("related_player_id")) or self._as_int(related_player.get("id")),
                        "name": event.get("related_player_name") or related_player.get("name"),
                    },
                    "type": event_type.get("name") or event_type.get("developer_name"),
                    "detail": detail,
                    "comments": event.get("result"),
                }
            )

        canonical = build_envelope(
            provider=self.name,
            entity_type="match_events",
            response=response_rows,
            source_params={"fixture": fixture_id},
            provider_meta={
                "endpoint": endpoint,
                "rate_limit": payload.get("rate_limit", {}),
                "subscription": payload.get("subscription", {}),
                "timezone": payload.get("timezone"),
            },
        )
        return canonical, headers

    def get_standings(
        self,
        *,
        league_id: int,
        season: int,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        season_id = self._resolve_season_id(league_id=league_id, season=season)
        endpoint = f"/standings/seasons/{season_id}"
        payload, headers = self._request(
            endpoint=endpoint,
            params={"include": "participant;details.type"},
        )
        response_rows = payload.get("data") or []
        if isinstance(response_rows, dict):
            response_rows = [response_rows]
        canonical = build_envelope(
            provider=self.name,
            entity_type="standings",
            response=response_rows,
            source_params={
                "league_id": league_id,
                "season": season,
                "season_id": season_id,
            },
            provider_meta={
                "endpoint": endpoint,
                "rate_limit": payload.get("rate_limit", {}),
                "subscription": payload.get("subscription", {}),
                "timezone": payload.get("timezone"),
            },
        )
        return canonical, headers
