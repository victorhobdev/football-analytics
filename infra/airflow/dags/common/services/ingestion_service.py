from __future__ import annotations

from datetime import datetime
import os
import re

import boto3
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.observability import StepMetrics, log_event
from common.providers import get_provider, provider_env_prefix
from common.raw_writer import write_raw_payload
from common.runtime import resolve_fixture_windows, resolve_runtime_params


BRONZE_BUCKET = "football-bronze"
FINAL_STATUSES = ("FT", "PEN", "AET")
FIXTURE_KEY_PATTERN = re.compile(r"/fixture_id=(\d+)/")


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _read_env_setting(
    primary: str,
    *,
    provider_name: str,
    provider_suffix: str,
    default: str,
    legacy_envs: tuple[str, ...] = (),
) -> str:
    primary_value = os.getenv(primary)
    if primary_value and primary_value.strip():
        return primary_value

    scoped_env = f"{provider_env_prefix(provider_name)}_{provider_suffix}"
    scoped_value = os.getenv(scoped_env)
    if scoped_value and scoped_value.strip():
        return scoped_value

    for legacy_env in legacy_envs:
        legacy_value = os.getenv(legacy_env)
        if legacy_value and legacy_value.strip():
            return legacy_value
    return default


def _get_int_env(
    primary: str,
    *,
    provider_name: str,
    provider_suffix: str,
    default: str,
    legacy_envs: tuple[str, ...] = (),
) -> int:
    return int(
        _read_env_setting(
            primary,
            provider_name=provider_name,
            provider_suffix=provider_suffix,
            default=default,
            legacy_envs=legacy_envs,
        )
    )


def _get_bool_env(
    primary: str,
    *,
    provider_name: str,
    provider_suffix: str,
    default: str,
    legacy_envs: tuple[str, ...] = (),
) -> bool:
    raw = _read_env_setting(
        primary,
        provider_name=provider_name,
        provider_suffix=provider_suffix,
        default=default,
        legacy_envs=legacy_envs,
    ).strip().lower()
    return raw in {"1", "true", "yes", "y"}


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_get_required_env("MINIO_ENDPOINT_URL"),
        aws_access_key_id=_get_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_get_required_env("MINIO_SECRET_KEY"),
    )


def _list_ingested_fixture_ids(s3_client, *, prefix: str) -> set[int]:
    fixture_ids: set[int] = set()
    continuation_token = None

    while True:
        kwargs = {"Bucket": BRONZE_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3_client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = item.get("Key", "")
            match = FIXTURE_KEY_PATTERN.search(key)
            if match:
                fixture_ids.add(int(match.group(1)))

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    return fixture_ids


def _is_fatal_api_error(exc: Exception) -> bool:
    text_value = str(exc).lower()
    fatal_markers = [
        "account is suspended",
        "your account is suspended",
        "invalid api key",
        "invalid key",
        "unauthorized",
        "forbidden",
        "access denied",
    ]
    return any(marker in text_value for marker in fatal_markers)


def _is_daily_limit_error(exc: Exception) -> bool:
    text_value = str(exc).lower()
    return "daily limit" in text_value or "quota" in text_value


def _fetch_finished_fixture_ids(engine, league_id: int, season: int) -> list[int]:
    sql = text(
        """
        SELECT DISTINCT fixture_id
        FROM raw.fixtures
        WHERE league_id = :league_id
          AND season = :season
          AND fixture_id IS NOT NULL
          AND status_short IN ('FT', 'PEN', 'AET')
        ORDER BY fixture_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"league_id": league_id, "season": season}).fetchall()
    return [int(row[0]) for row in rows]


def ingest_fixtures_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    windows = resolve_fixture_windows(context, season)

    requests_per_minute = _get_int_env(
        "INGEST_FIXTURES_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="FIXTURES_REQUESTS_PER_MINUTE",
        default="10",
        legacy_envs=("APIFOOTBALL_FIXTURES_REQUESTS_PER_MINUTE",),
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")

    requests_used = 0
    total_results = 0

    with StepMetrics(
        service="airflow",
        module="ingestion_service",
        step="ingest_fixtures_raw",
        context=context,
        dataset="fixtures",
        table="football-bronze",
    ) as metric:
        for date_from, date_to in windows:
            source_params = {
                "league_id": league_id,
                "season": season,
                "date_from": date_from,
                "date_to": date_to,
            }
            payload, headers = provider.get_fixtures(
                league_id=league_id,
                season=season,
                date_from=date_from,
                date_to=date_to,
            )
            requests_used += 1

            key = (
                f"fixtures/league={league_id}/season={season}"
                f"/from={date_from}/to={date_to}"
                f"/run={run_utc}/data.json"
            )
            write_result = write_raw_payload(
                s3_client=s3_client,
                bucket=BRONZE_BUCKET,
                key=key,
                payload=payload,
                provider=provider.name,
                endpoint="fixtures",
                source_params=source_params,
                entity_type="fixtures",
            )
            total_results += int(write_result["results"])

            rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
            print(
                f"[{provider.name}] [{date_from}..{date_to}] "
                f"league_id={league_id} season={season} results={write_result['results']} | rate_headers={rate_headers}"
            )

        metric.set_counts(rows_in=requests_used, rows_out=total_results, row_count=total_results)

    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status="success",
        context=context,
        dataset="fixtures",
        rows_in=requests_used,
        rows_out=total_results,
        row_count=total_results,
        message=(
            f"Raw fixtures concluido | provider={provider_name} | league_id={league_id} | season={season} "
            f"| windows={len(windows)} | requests={requests_used} | fixtures={total_results}"
        ),
    )


def ingest_statistics_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]

    requests_per_minute = _get_int_env(
        "INGEST_STATISTICS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="STATISTICS_REQUESTS_PER_MINUTE",
        default="10",
        legacy_envs=("APIFOOTBALL_STATISTICS_REQUESTS_PER_MINUTE",),
    )
    skip_ingested = _get_bool_env(
        "INGEST_STATISTICS_SKIP_INGESTED",
        provider_name=provider_name,
        provider_suffix="STATISTICS_SKIP_INGESTED",
        default="true",
        legacy_envs=("APIFOOTBALL_STATISTICS_SKIP_INGESTED",),
    )
    fail_on_partial = _get_bool_env(
        "INGEST_STATISTICS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="STATISTICS_FAIL_ON_PARTIAL",
        default="true",
        legacy_envs=("APIFOOTBALL_STATISTICS_FAIL_ON_PARTIAL",),
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_STATISTICS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="STATISTICS_MAX_CONSECUTIVE_FAILURES",
        default="5",
        legacy_envs=("APIFOOTBALL_STATISTICS_MAX_CONSECUTIVE_FAILURES",),
    )

    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    fixture_ids = _fetch_finished_fixture_ids(engine, league_id, season)

    if not fixture_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_statistics_raw",
            status="success",
            context=context,
            dataset="statistics",
            row_count=0,
            message=(
                "Nenhum fixture finalizado encontrado "
                f"| provider={provider_name} | league_id={league_id} | season={season} | statuses={FINAL_STATUSES}"
            ),
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    ingested_fixture_ids = (
        _list_ingested_fixture_ids(
            s3_client,
            prefix=f"statistics/league={league_id}/season={season}/",
        )
        if skip_ingested
        else set()
    )
    pending_fixture_ids = [fixture_id for fixture_id in fixture_ids if fixture_id not in ingested_fixture_ids]

    if not pending_fixture_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_statistics_raw",
            status="success",
            context=context,
            dataset="statistics",
            row_count=0,
            rows_in=len(fixture_ids),
            rows_out=0,
            message=(
                "Todos os fixtures finalizados ja possuem dados no bronze "
                f"| provider={provider_name} | total={len(fixture_ids)} | ingeridos_previamente={len(ingested_fixture_ids)}"
            ),
        )
        return

    succeeded = 0
    failed = 0
    attempted = 0
    consecutive_failures = 0
    daily_limit_reached = False
    stop_reason = ""

    with StepMetrics(
        service="airflow",
        module="ingestion_service",
        step="ingest_statistics_raw",
        context=context,
        dataset="statistics",
        table="football-bronze",
    ) as metric:
        for idx, fixture_id in enumerate(pending_fixture_ids, start=1):
            try:
                attempted += 1
                payload, headers = provider.get_fixture_statistics(fixture_id=fixture_id)

                key = (
                    f"statistics/league={league_id}/season={season}"
                    f"/fixture_id={fixture_id}/run={run_utc}/data.json"
                )
                write_result = write_raw_payload(
                    s3_client=s3_client,
                    bucket=BRONZE_BUCKET,
                    key=key,
                    payload=payload,
                    provider=provider.name,
                    endpoint="fixtures/statistics",
                    source_params={"fixture": fixture_id},
                    entity_type="statistics",
                )
                succeeded += 1
                consecutive_failures = 0

                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(pending_fixture_ids)}] provider={provider.name} fixture_id={fixture_id} "
                    f"salvo em s3://{BRONZE_BUCKET}/{key} | results={write_result['results']} "
                    f"| rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += 1
                consecutive_failures += 1
                if _is_fatal_api_error(exc):
                    stop_reason = f"erro_fatal_api={exc}"
                    break
                if _is_daily_limit_error(exc):
                    daily_limit_reached = True
                    stop_reason = f"limite_diario={exc}"
                    break
                print(f"[{idx}/{len(pending_fixture_ids)}] erro fixture_id={fixture_id}: {exc}")

            if consecutive_failures >= max_consecutive_failures:
                stop_reason = f"falhas_consecutivas={consecutive_failures}"
                break

        metric.set_counts(rows_in=attempted, rows_out=succeeded, row_count=succeeded)

    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status="success",
        context=context,
        dataset="statistics",
        rows_in=attempted,
        rows_out=succeeded,
        row_count=succeeded,
        message=(
            "Raw statistics concluido "
            f"| provider={provider_name} | league_id={league_id} | season={season} "
            f"| fixtures_total={len(fixture_ids)} | pendentes={len(pending_fixture_ids)} "
            f"| tentativas={attempted} | sucesso={succeeded} | falhas={failed} "
            f"| limite_diario={daily_limit_reached} | motivo={stop_reason}"
        ),
    )

    if fail_on_partial and succeeded < len(pending_fixture_ids):
        raise RuntimeError(
            "Ingestao raw statistics parcial. "
            f"pendentes={len(pending_fixture_ids)} | tentativas={attempted} | sucesso={succeeded} | falhas={failed} | "
            f"limite_diario={daily_limit_reached}."
        )


def ingest_match_events_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]

    requests_per_minute = _get_int_env(
        "INGEST_EVENTS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="EVENTS_REQUESTS_PER_MINUTE",
        default="10",
        legacy_envs=("APIFOOTBALL_EVENTS_REQUESTS_PER_MINUTE",),
    )
    skip_ingested = _get_bool_env(
        "INGEST_EVENTS_SKIP_INGESTED",
        provider_name=provider_name,
        provider_suffix="EVENTS_SKIP_INGESTED",
        default="true",
        legacy_envs=("APIFOOTBALL_EVENTS_SKIP_INGESTED",),
    )
    fail_on_partial = _get_bool_env(
        "INGEST_EVENTS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="EVENTS_FAIL_ON_PARTIAL",
        default="true",
        legacy_envs=("APIFOOTBALL_EVENTS_FAIL_ON_PARTIAL",),
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_EVENTS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="EVENTS_MAX_CONSECUTIVE_FAILURES",
        default="5",
        legacy_envs=("APIFOOTBALL_EVENTS_MAX_CONSECUTIVE_FAILURES",),
    )

    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    fixture_ids = _fetch_finished_fixture_ids(engine, league_id, season)

    if not fixture_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_match_events_raw",
            status="success",
            context=context,
            dataset="match_events",
            row_count=0,
            message=(
                "Nenhum fixture finalizado encontrado "
                f"| provider={provider_name} | league_id={league_id} | season={season} | statuses={FINAL_STATUSES}"
            ),
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    ingested_fixture_ids = (
        _list_ingested_fixture_ids(
            s3_client,
            prefix=f"events/league={league_id}/season={season}/",
        )
        if skip_ingested
        else set()
    )
    pending_fixture_ids = [fixture_id for fixture_id in fixture_ids if fixture_id not in ingested_fixture_ids]

    if not pending_fixture_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_match_events_raw",
            status="success",
            context=context,
            dataset="match_events",
            row_count=0,
            rows_in=len(fixture_ids),
            rows_out=0,
            message=(
                "Todos os fixtures finalizados ja possuem dados no bronze "
                f"| provider={provider_name} | total={len(fixture_ids)} | ingeridos_previamente={len(ingested_fixture_ids)}"
            ),
        )
        return

    succeeded = 0
    failed = 0
    attempted = 0
    total_events = 0
    consecutive_failures = 0
    daily_limit_reached = False
    stop_reason = ""

    with StepMetrics(
        service="airflow",
        module="ingestion_service",
        step="ingest_match_events_raw",
        context=context,
        dataset="match_events",
        table="football-bronze",
    ) as metric:
        for idx, fixture_id in enumerate(pending_fixture_ids, start=1):
            try:
                attempted += 1
                payload, headers = provider.get_fixture_events(fixture_id=fixture_id)
                events_count = len(payload.get("response", []) or [])
                total_events += events_count

                key = (
                    f"events/league={league_id}/season={season}"
                    f"/fixture_id={fixture_id}/run={run_utc}/data.json"
                )
                write_result = write_raw_payload(
                    s3_client=s3_client,
                    bucket=BRONZE_BUCKET,
                    key=key,
                    payload=payload,
                    provider=provider.name,
                    endpoint="fixtures/events",
                    source_params={"fixture": fixture_id},
                    entity_type="match_events",
                )
                succeeded += 1
                consecutive_failures = 0

                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(pending_fixture_ids)}] provider={provider.name} fixture_id={fixture_id} "
                    f"eventos={events_count} salvo em s3://{BRONZE_BUCKET}/{key} "
                    f"| results={write_result['results']} | rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += 1
                consecutive_failures += 1
                if _is_fatal_api_error(exc):
                    stop_reason = f"erro_fatal_api={exc}"
                    break
                if _is_daily_limit_error(exc):
                    daily_limit_reached = True
                    stop_reason = f"limite_diario={exc}"
                    break
                print(f"[{idx}/{len(pending_fixture_ids)}] erro fixture_id={fixture_id}: {exc}")

            if consecutive_failures >= max_consecutive_failures:
                stop_reason = f"falhas_consecutivas={consecutive_failures}"
                break

        metric.set_counts(rows_in=attempted, rows_out=total_events, row_count=total_events)

    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status="success",
        context=context,
        dataset="match_events",
        rows_in=attempted,
        rows_out=total_events,
        row_count=total_events,
        message=(
            "Raw match_events concluido "
            f"| provider={provider_name} | league_id={league_id} | season={season} "
            f"| fixtures_total={len(fixture_ids)} | pendentes={len(pending_fixture_ids)} "
            f"| tentativas={attempted} | sucesso={succeeded} | falhas={failed} | eventos={total_events} "
            f"| limite_diario={daily_limit_reached} | motivo={stop_reason}"
        ),
    )

    if fail_on_partial and succeeded < len(pending_fixture_ids):
        raise RuntimeError(
            "Ingestao raw match_events parcial. "
            f"pendentes={len(pending_fixture_ids)} | tentativas={attempted} | sucesso={succeeded} | falhas={failed} | "
            f"limite_diario={daily_limit_reached}."
        )
