from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_REPORT_PATH = ROOT / "quality" / "sportmonks_probe_report.md"
DEFAULT_JSON_PATH = ROOT / "quality" / "sportmonks_probe_payload_sample.json"

FINAL_STATUSES = ("FT", "AET", "PEN", "FTP")
SPORTMONKS_PROVIDER = "sportmonks"


@dataclass(frozen=True)
class FixtureTarget:
    fixture_id: int
    match_date: date | None
    league_id: int | None
    season: int | None
    home_team_id: int | None
    away_team_id: int | None
    home_team_name: str | None
    away_team_name: str | None


@dataclass(frozen=True)
class ProbeResult:
    kind: str
    key: str
    status: str
    rows: int
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingestao piloto SportMonks para validar fixture coaches e transfer events "
            "antes de promover dados para superficies publicas."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--team-id", type=int, default=1024, help="SportMonks/local team_id alvo. Default: Flamengo.")
    parser.add_argument(
        "--coach-seasons",
        nargs="+",
        type=int,
        default=[2021, 2022, 2024],
        help="Temporadas locais para buscar fixtures do time alvo.",
    )
    parser.add_argument(
        "--max-fixtures-per-season",
        type=int,
        default=10,
        help="Limite por temporada para o probe. Use 0 para sem limite.",
    )
    parser.add_argument("--player-id", type=int, default=215915, help="SportMonks player_id alvo. Default: Everton Ribeiro.")
    parser.add_argument("--transfer-start", default="2023-12-01")
    parser.add_argument("--transfer-end", default="2023-12-31")
    parser.add_argument("--max-transfer-pages", type=int, default=2)
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--json-path", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Busca API e gera relatorio sem escrever no banco.")
    return parser.parse_args()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


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


def resolve_setting(name: str, env_file_values: dict[str, str], default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return env_file_values.get(name, default)


def resolve_pg_dsn(env_values: dict[str, str]) -> str:
    dsn = (
        resolve_setting("FOOTBALL_PG_DSN", env_values)
        or resolve_setting("DATABASE_URL", env_values)
        or "postgresql://football:football@localhost:5432/football_dw"
    )
    if "@postgres:" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres:", "@localhost:")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    return dsn


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


class SportMonksClient:
    def __init__(self, *, base_url: str, api_token: str, timeout_seconds: int = 45, sleep_seconds: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds
        self.requests_total = 0

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = {"api_token": self.api_token, **(params or {})}
        url = f"{self.base_url}{endpoint}?{urlencode(query)}"
        request = Request(url, headers={"User-Agent": "football-analytics-sportmonks-ingest/1.0"})
        if self.sleep_seconds > 0 and self.requests_total > 0:
            time.sleep(self.sleep_seconds)
        self.requests_total += 1
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"SportMonks HTTP {exc.code} endpoint={endpoint} body={body}") from exc
        except URLError as exc:
            raise RuntimeError(f"SportMonks network error endpoint={endpoint}: {exc}") from exc

    def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        max_pages: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        payloads: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self.get(endpoint, {**params, "page": page})
            payloads.append(payload)
            data = payload.get("data") or []
            if isinstance(data, dict):
                rows.append(data)
            elif isinstance(data, list):
                rows.extend(data)
            pagination = payload.get("pagination") or {}
            if not pagination.get("has_more"):
                break
            page += 1
            if max_pages > 0 and page > max_pages:
                break
        return rows, payloads


def fetch_fixture_targets(
    conn: psycopg.Connection[Any],
    *,
    team_id: int,
    seasons: list[int],
    max_per_season: int,
) -> list[FixtureTarget]:
    season_placeholders = ", ".join(["%s"] * len(seasons))
    limit_filter = "where rn <= %s" if max_per_season > 0 else ""
    params: list[Any] = [
        *seasons,
        team_id,
        team_id,
        *FINAL_STATUSES,
    ]
    if max_per_season > 0:
        params.append(max_per_season)
    sql = f"""
        with ranked as (
            select
                fixture_id,
                date_utc::date as match_date,
                league_id,
                season,
                home_team_id,
                away_team_id,
                home_team_name,
                away_team_name,
                row_number() over (partition by season order by date_utc, fixture_id) as rn
            from raw.fixtures
            where season in ({season_placeholders})
              and (home_team_id = %s or away_team_id = %s)
              and status_short in (%s, %s, %s, %s)
              and fixture_id is not null
        )
        select *
        from ranked
        {limit_filter}
        order by season, match_date, fixture_id;
    """
    rows = conn.execute(sql, params).fetchall()
    return [
        FixtureTarget(
            fixture_id=int(row["fixture_id"]),
            match_date=row.get("match_date"),
            league_id=as_int(row.get("league_id")),
            season=as_int(row.get("season")),
            home_team_id=as_int(row.get("home_team_id")),
            away_team_id=as_int(row.get("away_team_id")),
            home_team_name=row.get("home_team_name"),
            away_team_name=row.get("away_team_name"),
        )
        for row in rows
    ]


def participant_location(participant: dict[str, Any] | None) -> str | None:
    if not participant:
        return None
    meta = participant.get("meta") or {}
    value = meta.get("location")
    return str(value) if value is not None else None


def valid_name(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip().lower() not in {"unknown", "n/a", "null"})


def extract_fixture_coach_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return []
    fixture_id = as_int(data.get("id"))
    fixture_date = as_date(data.get("starting_at"))
    season_id = as_int(data.get("season_id"))
    participants = data.get("participants") or []
    participants_by_id = {as_int(item.get("id")): item for item in participants if as_int(item.get("id")) is not None}
    rows: list[dict[str, Any]] = []
    for coach in data.get("coaches") or []:
        coach_id = as_int(coach.get("id"))
        meta = coach.get("meta") or {}
        team_id = as_int(meta.get("participant_id"))
        if fixture_id is None or coach_id is None or team_id is None:
            continue
        participant = participants_by_id.get(team_id)
        rows.append(
            {
                "fixture_id": fixture_id,
                "team_id": team_id,
                "coach_id": coach_id,
                "fixture_date": fixture_date,
                "season_id": season_id,
                "participant_location": participant_location(participant),
                "coach_name": coach.get("name"),
                "coach_display_name": coach.get("display_name"),
                "payload": data,
                "coach_payload": coach,
                "participant_payload": participant or {},
            }
        )
    return rows


def extract_transfer_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for row in rows:
        transfer_id = as_int(row.get("id"))
        if transfer_id is None:
            continue
        type_payload = row.get("type") or {}
        extracted.append(
            {
                "transfer_id": transfer_id,
                "player_id": as_int(row.get("player_id")),
                "type_id": as_int(row.get("type_id")),
                "from_team_id": as_int(row.get("from_team_id")),
                "to_team_id": as_int(row.get("to_team_id")),
                "position_id": as_int(row.get("position_id")),
                "detailed_position_id": as_int(row.get("detailed_position_id")),
                "transfer_date": as_date(row.get("date")),
                "completed": row.get("completed"),
                "completed_at": row.get("completed_at"),
                "career_ended": row.get("career_ended"),
                "amount": as_float(row.get("amount")),
                "transfer_type_code": type_payload.get("code"),
                "transfer_type_name": type_payload.get("name"),
                "transfer_type_developer_name": type_payload.get("developer_name"),
                "payload": row,
            }
        )
    return extracted


def upsert_fixture_coaches(
    conn: psycopg.Connection[Any],
    *,
    rows: list[dict[str, Any]],
    run_id: str,
    cutoff: date,
) -> None:
    conflict_counts = Counter((row["fixture_id"], row["team_id"]) for row in rows)
    for row in rows:
        source_endpoint = f"/fixtures/{row['fixture_id']}?include=coaches;participants;state"
        conn.execute(
            """
            insert into raw.sportmonks_fixture_coaches (
                provider, fixture_id, team_id, coach_id, fixture_date, season_id,
                participant_location, coach_name, coach_display_name, source_endpoint,
                payload, coach_payload, participant_payload, ingested_run
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (provider, fixture_id, team_id, coach_id) do update set
                fixture_date = excluded.fixture_date,
                season_id = excluded.season_id,
                participant_location = excluded.participant_location,
                coach_name = excluded.coach_name,
                coach_display_name = excluded.coach_display_name,
                source_endpoint = excluded.source_endpoint,
                payload = excluded.payload,
                coach_payload = excluded.coach_payload,
                participant_payload = excluded.participant_payload,
                ingested_run = excluded.ingested_run,
                updated_at = now()
            """,
            (
                SPORTMONKS_PROVIDER,
                row["fixture_id"],
                row["team_id"],
                row["coach_id"],
                row["fixture_date"],
                row["season_id"],
                row["participant_location"],
                row["coach_name"],
                row["coach_display_name"],
                source_endpoint,
                Jsonb(row["payload"]),
                Jsonb(row["coach_payload"]),
                Jsonb(row["participant_payload"]),
                run_id,
            ),
        )
        conn.execute(
            """
            insert into raw.sportmonks_coaches (
                provider, coach_id, player_id, coach_name, display_name,
                image_path, date_of_birth, payload, ingested_run
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (provider, coach_id) do update set
                player_id = excluded.player_id,
                coach_name = excluded.coach_name,
                display_name = excluded.display_name,
                image_path = excluded.image_path,
                date_of_birth = excluded.date_of_birth,
                payload = excluded.payload,
                ingested_run = excluded.ingested_run,
                updated_at = now()
            """,
            (
                SPORTMONKS_PROVIDER,
                row["coach_id"],
                as_int(row["coach_payload"].get("player_id")),
                row["coach_name"],
                row["coach_display_name"],
                row["coach_payload"].get("image_path"),
                as_date(row["coach_payload"].get("date_of_birth")),
                Jsonb(row["coach_payload"]),
                run_id,
            ),
        )
        conflict_reason = None
        source_confidence = 0.95
        is_public_eligible = True
        if conflict_counts[(row["fixture_id"], row["team_id"])] > 1:
            conflict_reason = "multiple_coaches_for_fixture_team"
            source_confidence = 0.0
            is_public_eligible = False
        if not valid_name(row.get("coach_display_name") or row.get("coach_name")):
            conflict_reason = "invalid_coach_name"
            source_confidence = 0.0
            is_public_eligible = False
        if row.get("fixture_date") and row["fixture_date"] > cutoff:
            conflict_reason = "after_product_cutoff"
            is_public_eligible = False
        source_record_id = f"{row['fixture_id']}:{row['team_id']}:{row['coach_id']}"
        conn.execute(
            """
            insert into mart.stg_sportmonks_fixture_coach_assignments (
                source_record_id, provider, fixture_id, match_id, team_id,
                provider_coach_id, coach_name, coach_display_name, role,
                assignment_method, source_confidence, is_public_eligible,
                conflict_reason, source_payload, ingested_run
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (source_record_id) do update set
                coach_name = excluded.coach_name,
                coach_display_name = excluded.coach_display_name,
                source_confidence = excluded.source_confidence,
                is_public_eligible = excluded.is_public_eligible,
                conflict_reason = excluded.conflict_reason,
                source_payload = excluded.source_payload,
                ingested_run = excluded.ingested_run,
                updated_at = now()
            """,
            (
                source_record_id,
                SPORTMONKS_PROVIDER,
                row["fixture_id"],
                row["fixture_id"],
                row["team_id"],
                row["coach_id"],
                row["coach_name"],
                row["coach_display_name"],
                "head_coach",
                "lineup_source",
                source_confidence,
                is_public_eligible,
                conflict_reason,
                Jsonb(row["coach_payload"]),
                run_id,
            ),
        )


def upsert_transfers(
    conn: psycopg.Connection[Any],
    *,
    rows: list[dict[str, Any]],
    run_id: str,
    cutoff: date,
    source_endpoint: str,
) -> None:
    for row in rows:
        conn.execute(
            """
            insert into raw.sportmonks_transfer_events (
                provider, transfer_id, player_id, type_id, from_team_id, to_team_id,
                position_id, detailed_position_id, transfer_date, completed,
                completed_at, career_ended, amount, source_endpoint, payload, ingested_run
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (provider, transfer_id) do update set
                player_id = excluded.player_id,
                type_id = excluded.type_id,
                from_team_id = excluded.from_team_id,
                to_team_id = excluded.to_team_id,
                position_id = excluded.position_id,
                detailed_position_id = excluded.detailed_position_id,
                transfer_date = excluded.transfer_date,
                completed = excluded.completed,
                completed_at = excluded.completed_at,
                career_ended = excluded.career_ended,
                amount = excluded.amount,
                source_endpoint = excluded.source_endpoint,
                payload = excluded.payload,
                ingested_run = excluded.ingested_run,
                updated_at = now()
            """,
            (
                SPORTMONKS_PROVIDER,
                row["transfer_id"],
                row["player_id"],
                row["type_id"],
                row["from_team_id"],
                row["to_team_id"],
                row["position_id"],
                row["detailed_position_id"],
                row["transfer_date"],
                row["completed"],
                row["completed_at"],
                row["career_ended"],
                row["amount"],
                source_endpoint,
                Jsonb(row["payload"]),
                run_id,
            ),
        )
        is_public_eligible = bool(row.get("transfer_date") and row["transfer_date"] <= cutoff)
        conn.execute(
            """
            insert into mart.stg_sportmonks_transfer_events (
                provider, transfer_id, player_id, from_team_id, to_team_id,
                transfer_date, transfer_type_id, transfer_type_code,
                transfer_type_name, transfer_type_developer_name, is_loan,
                is_loan_return, fee_amount, fee_currency, completed,
                completed_at, career_ended, season_id, season_resolution_method,
                is_public_eligible, source_payload, ingested_run
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (provider, transfer_id) do update set
                player_id = excluded.player_id,
                from_team_id = excluded.from_team_id,
                to_team_id = excluded.to_team_id,
                transfer_date = excluded.transfer_date,
                transfer_type_id = excluded.transfer_type_id,
                transfer_type_code = excluded.transfer_type_code,
                transfer_type_name = excluded.transfer_type_name,
                transfer_type_developer_name = excluded.transfer_type_developer_name,
                is_loan = excluded.is_loan,
                is_loan_return = excluded.is_loan_return,
                fee_amount = excluded.fee_amount,
                fee_currency = excluded.fee_currency,
                completed = excluded.completed,
                completed_at = excluded.completed_at,
                career_ended = excluded.career_ended,
                season_id = excluded.season_id,
                season_resolution_method = excluded.season_resolution_method,
                is_public_eligible = excluded.is_public_eligible,
                source_payload = excluded.source_payload,
                ingested_run = excluded.ingested_run,
                updated_at = now()
            """,
            (
                SPORTMONKS_PROVIDER,
                row["transfer_id"],
                row["player_id"],
                row["from_team_id"],
                row["to_team_id"],
                row["transfer_date"],
                row["type_id"],
                row["transfer_type_code"],
                row["transfer_type_name"],
                row["transfer_type_developer_name"],
                row["type_id"] == 218,
                row["type_id"] == 9688,
                row["amount"],
                None,
                row["completed"],
                row["completed_at"],
                row["career_ended"],
                None,
                "unresolved",
                is_public_eligible,
                Jsonb(row["payload"]),
                run_id,
            ),
        )


def write_json_sample(path: Path, sample: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(
    path: Path,
    *,
    run_id: str,
    args: argparse.Namespace,
    dry_run: bool,
    requests_total: int,
    fixture_results: list[ProbeResult],
    fixture_rows: list[dict[str, Any]],
    player_transfer_rows: list[dict[str, Any]],
    window_transfer_rows: list[dict[str, Any]],
    api_errors: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fixture_status = Counter(result.status for result in fixture_results)
    fixture_by_season: dict[str, Counter[str]] = defaultdict(Counter)
    for result in fixture_results:
        _, _, season = result.key.partition("season=")
        season_key = season.split()[0] if season else "unknown"
        fixture_by_season[season_key][result.status] += 1
    assignment_pairs = Counter((row["fixture_id"], row["team_id"]) for row in fixture_rows)
    conflicts = sum(1 for count in assignment_pairs.values() if count > 1)
    type_counts = Counter(row.get("type_id") for row in [*player_transfer_rows, *window_transfer_rows])
    missing_currency = len(player_transfer_rows) + len(window_transfer_rows)

    lines = [
        "# SportMonks reliability ingest report",
        "",
        "## Run",
        "",
        f"- run_id: `{run_id}`",
        f"- dry_run: `{str(dry_run).lower()}`",
        f"- api_requests: `{requests_total}`",
        f"- team_id: `{args.team_id}`",
        f"- coach_seasons: `{', '.join(str(item) for item in args.coach_seasons)}`",
        f"- max_fixtures_per_season: `{args.max_fixtures_per_season}`",
        f"- player_id: `{args.player_id}`",
        f"- transfer_window: `{args.transfer_start}` to `{args.transfer_end}`",
        "",
        "## Fixture coaches",
        "",
        f"- fixture probes: `{len(fixture_results)}`",
        f"- status counts: `{dict(fixture_status)}`",
        f"- extracted fixture coach rows: `{len(fixture_rows)}`",
        f"- fixture/team duplicate coach conflicts: `{conflicts}`",
        "",
        "### By season",
        "",
    ]
    if fixture_by_season:
        for season, counts in sorted(fixture_by_season.items()):
            lines.append(f"- `{season}`: `{dict(counts)}`")
    else:
        lines.append("- No fixture probes executed.")

    lines.extend(
        [
            "",
            "## Transfers",
            "",
            f"- player transfer rows: `{len(player_transfer_rows)}`",
            f"- window transfer rows: `{len(window_transfer_rows)}`",
            f"- transfer type counts: `{dict(type_counts)}`",
            f"- rows with fee_currency absent by provider contract: `{missing_currency}`",
            "",
            "## API errors / access blockers",
            "",
        ]
    )
    lines.extend([f"- {error}" for error in api_errors] or ["- None"])
    lines.extend(
        [
            "",
            "## Operational reading",
            "",
            "- Fixture-level `coaches` is usable only where the API returns historical fixture payloads with coach meta participant binding.",
            "- Transfer events are ingestible as provider events, but `fee_currency` and local `season_id` remain unresolved by design.",
            "- This ingest intentionally does not promote rows to public facts or rankings.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_id = utc_run_id()
    env_values = load_env_file(Path(args.env_file))
    api_token = resolve_setting("API_KEY_SPORTMONKS", env_values)
    if not api_token:
        raise RuntimeError("API_KEY_SPORTMONKS ausente no ambiente ou .env.")
    base_url = resolve_setting("SPORTMONKS_BASE_URL", env_values, "https://api.sportmonks.com/v3/football")
    product_cutoff = as_date(resolve_setting("PRODUCT_DATA_CUTOFF", env_values, "2025-12-31"))
    if product_cutoff is None:
        raise RuntimeError("PRODUCT_DATA_CUTOFF invalido.")

    client = SportMonksClient(base_url=str(base_url), api_token=api_token)
    fixture_results: list[ProbeResult] = []
    fixture_rows: list[dict[str, Any]] = []
    player_transfer_rows: list[dict[str, Any]] = []
    window_transfer_rows: list[dict[str, Any]] = []
    api_errors: list[str] = []
    sample_payloads: dict[str, Any] = {}

    with psycopg.connect(resolve_pg_dsn(env_values), row_factory=dict_row) as conn:
        targets = fetch_fixture_targets(
            conn,
            team_id=args.team_id,
            seasons=args.coach_seasons,
            max_per_season=args.max_fixtures_per_season,
        )
        for target in targets:
            endpoint = f"/fixtures/{target.fixture_id}"
            key = f"fixture={target.fixture_id} season={target.season}"
            try:
                payload = client.get(endpoint, {"include": "coaches;participants;state"})
                rows = extract_fixture_coach_rows(payload)
                data = payload.get("data")
                if data is None:
                    message = str(payload.get("message") or "no data")
                    fixture_results.append(ProbeResult("fixture_coaches", key, "no_data", 0, message))
                    api_errors.append(f"{key}: {message}")
                    continue
                status = "pass" if rows else "partial"
                fixture_results.append(ProbeResult("fixture_coaches", key, status, len(rows), ""))
                fixture_rows.extend(rows)
                sample_payloads.setdefault("fixture_coaches", payload)
            except Exception as exc:
                fixture_results.append(ProbeResult("fixture_coaches", key, "error", 0, str(exc)[:400]))
                api_errors.append(f"{key}: {exc}")

        player_endpoint = f"/transfers/players/{args.player_id}"
        try:
            rows, payloads = client.get_paginated(
                player_endpoint,
                {"include": "type;fromTeam;toTeam;player", "per_page": 50, "order": "asc"},
                max_pages=5,
            )
            player_transfer_rows = extract_transfer_rows(rows)
            if payloads:
                sample_payloads.setdefault("player_transfers", payloads[0])
        except Exception as exc:
            api_errors.append(f"{player_endpoint}: {exc}")

        window_endpoint = f"/transfers/between/{args.transfer_start}/{args.transfer_end}"
        try:
            rows, payloads = client.get_paginated(
                window_endpoint,
                {"include": "type;fromTeam;toTeam;player", "per_page": 50, "order": "asc"},
                max_pages=args.max_transfer_pages,
            )
            window_transfer_rows = extract_transfer_rows(rows)
            if payloads:
                sample_payloads.setdefault("window_transfers", payloads[0])
        except Exception as exc:
            api_errors.append(f"{window_endpoint}: {exc}")

        if not args.dry_run:
            upsert_fixture_coaches(conn, rows=fixture_rows, run_id=run_id, cutoff=product_cutoff)
            upsert_transfers(
                conn,
                rows=player_transfer_rows,
                run_id=run_id,
                cutoff=product_cutoff,
                source_endpoint=player_endpoint,
            )
            upsert_transfers(
                conn,
                rows=window_transfer_rows,
                run_id=run_id,
                cutoff=product_cutoff,
                source_endpoint=window_endpoint,
            )
            conn.commit()

    write_json_sample(Path(args.json_path), sample_payloads)
    write_report(
        Path(args.report_path),
        run_id=run_id,
        args=args,
        dry_run=args.dry_run,
        requests_total=client.requests_total,
        fixture_results=fixture_results,
        fixture_rows=fixture_rows,
        player_transfer_rows=player_transfer_rows,
        window_transfer_rows=window_transfer_rows,
        api_errors=api_errors,
    )
    print(f"run_id={run_id}")
    print(f"fixture_probes={len(fixture_results)} fixture_coach_rows={len(fixture_rows)}")
    print(f"player_transfer_rows={len(player_transfer_rows)} window_transfer_rows={len(window_transfer_rows)}")
    print(f"api_requests={client.requests_total}")
    print(f"report={Path(args.report_path)}")
    print(f"json={Path(args.json_path)}")


if __name__ == "__main__":
    main()
