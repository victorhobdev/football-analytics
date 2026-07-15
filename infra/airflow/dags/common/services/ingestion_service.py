from __future__ import annotations

from datetime import datetime
import hashlib
import os
import re
from typing import Any, Callable

import boto3
from airflow.operators.python import get_current_context
from sqlalchemy import create_engine, text

from common.fixture_status import FINAL_STATUSES, FINAL_STATUSES_SQL
from common.observability import StepMetrics, log_event
from common.providers import get_provider, provider_env_prefix
from common.raw_writer import write_raw_payload
from common.runtime import resolve_fixture_windows, resolve_runtime_params


BRONZE_BUCKET = "football-bronze"


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


def _raw_runtime_inputs(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    params = context.get("params") or {}
    dag_run = context.get("dag_run")
    conf = dag_run.conf if dag_run and dag_run.conf else {}
    return params, conf


def _safe_int(value: Any, default_value: int, field_name: str) -> int:
    if value is None:
        return default_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametro invalido para {field_name}: {value}") from exc


def _parse_fixture_ids(raw_fixture_ids: Any) -> list[int]:
    if raw_fixture_ids is None:
        return []

    values: list[Any]
    if isinstance(raw_fixture_ids, (list, tuple, set)):
        values = list(raw_fixture_ids)
    elif isinstance(raw_fixture_ids, str):
        raw = raw_fixture_ids.strip()
        if not raw:
            return []
        normalized = raw.replace("[", "").replace("]", "")
        values = [token.strip() for token in normalized.split(",") if token.strip()]
    else:
        raise ValueError(
            "fixture_ids deve ser lista de inteiros ou string separada por virgula. "
            f"Valor recebido: {raw_fixture_ids}"
        )

    parsed: list[int] = []
    for value in values:
        parsed_value = _safe_int(value, 0, "fixture_ids")
        if parsed_value <= 0:
            raise ValueError(f"fixture_id invalido em fixture_ids: {value}")
        parsed.append(parsed_value)

    return sorted(set(parsed))


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
    return _list_ingested_numeric_ids(s3_client, prefix=prefix, id_name="fixture_id")


def _list_ingested_numeric_ids(s3_client, *, prefix: str, id_name: str) -> set[int]:
    key_pattern = re.compile(rf"/{re.escape(id_name)}=(\d+)/")
    item_ids: set[int] = set()
    continuation_token = None

    while True:
        kwargs = {"Bucket": BRONZE_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3_client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = item.get("Key", "")
            match = key_pattern.search(key)
            if match:
                item_ids.add(int(match.group(1)))

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    return item_ids


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
        f"""
        SELECT DISTINCT fixture_id
        FROM raw.fixtures
        WHERE league_id = :league_id
          AND season = :season
          AND fixture_id IS NOT NULL
          AND status_short IN ({FINAL_STATUSES_SQL})
        ORDER BY fixture_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"league_id": league_id, "season": season}).fetchall()
    return [int(row[0]) for row in rows]


def _resolve_statistics_targets(
    *,
    context: dict[str, Any],
    default_league_id: int,
    default_season: int,
    fetch_finished_fixture_ids,
) -> dict[str, Any]:
    params, conf = _raw_runtime_inputs(context)

    raw_mode = conf.get("mode", params.get("mode", "incremental"))
    mode = str(raw_mode or "incremental").strip().lower()
    if mode not in {"incremental", "backfill"}:
        raise ValueError(f"Parametro invalido para mode: {raw_mode}. Use 'incremental' ou 'backfill'.")

    league_id = _safe_int(
        conf.get("league_id", params.get("league_id", default_league_id)),
        default_league_id,
        "league_id",
    )
    season = _safe_int(
        conf.get("season", conf.get("season_id", params.get("season", params.get("season_id", default_season)))),
        default_season,
        "season",
    )

    fixture_ids = _parse_fixture_ids(conf.get("fixture_ids", params.get("fixture_ids")))
    if mode == "incremental" and fixture_ids:
        raise ValueError("fixture_ids so pode ser usado com mode='backfill'.")

    if mode == "backfill" and fixture_ids:
        return {
            "mode": mode,
            "league_id": league_id,
            "season": season,
            "fixture_ids": fixture_ids,
            "target_source": "explicit_fixture_ids",
        }

    target_fixture_ids = fetch_finished_fixture_ids(league_id, season)
    return {
        "mode": mode,
        "league_id": league_id,
        "season": season,
        "fixture_ids": target_fixture_ids,
        "target_source": "season_scope",
    }


def _sync_scope_key(
    *,
    league_id: int,
    season: int,
    mode: str = "incremental",
    fixture_ids: list[int] | None = None,
) -> str:
    base_scope = f"league={league_id}/season={season}"
    if mode != "backfill":
        return base_scope
    if fixture_ids:
        digest_input = ",".join(str(value) for value in fixture_ids)
        digest = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]
        return f"{base_scope}/mode=backfill/fixture_hash={digest}/fixture_count={len(fixture_ids)}"
    return f"{base_scope}/mode=backfill"


def _read_sync_cursor(
    engine,
    *,
    provider_name: str,
    entity_type: str,
    scope_key: str,
) -> int | None:
    sql = text(
        """
        SELECT cursor
        FROM raw.provider_sync_state
        WHERE provider = :provider
          AND entity_type = :entity_type
          AND scope_key = :scope_key
        """
    )
    params = {
        "provider": provider_name,
        "entity_type": entity_type,
        "scope_key": scope_key,
    }
    try:
        with engine.begin() as conn:
            row = conn.execute(sql, params).first()
    except Exception as exc:
        log_event(
            level="error",
            service="airflow",
            module="ingestion_service",
            step="read_sync_state",
            status="failed",
            dataset=entity_type,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            message=(
                "Falha ao ler provider_sync_state; a ingestao sera interrompida "
                f"| provider={provider_name} entity_type={entity_type} scope={scope_key}"
            ),
        )
        raise RuntimeError(
            "Falha ao ler provider_sync_state "
            f"| provider={provider_name} entity_type={entity_type} scope={scope_key} erro={exc}"
        ) from exc

    if not row:
        return None
    raw_cursor = row[0]
    if raw_cursor is None:
        return None
    try:
        return int(raw_cursor)
    except (TypeError, ValueError):
        print(
            "[sync_state] cursor invalido; ignorando estado e usando full-scan "
            f"| provider={provider_name} entity_type={entity_type} scope={scope_key} cursor={raw_cursor}"
        )
        return None


def _upsert_sync_state(
    engine,
    *,
    provider_name: str,
    entity_type: str,
    scope_key: str,
    league_id: int,
    season: int,
    cursor: int | None,
    status: str,
    update_last_successful_sync: bool,
) -> None:
    sql = text(
        """
        INSERT INTO raw.provider_sync_state (
            provider,
            entity_type,
            scope_key,
            league_id,
            season,
            last_successful_sync,
            cursor,
            status,
            updated_at
        )
        VALUES (
            :provider,
            :entity_type,
            :scope_key,
            :league_id,
            :season,
            :last_successful_sync,
            :cursor,
            :status,
            now()
        )
        ON CONFLICT (provider, entity_type, scope_key)
        DO UPDATE SET
            league_id = EXCLUDED.league_id,
            season = EXCLUDED.season,
            last_successful_sync = COALESCE(
                EXCLUDED.last_successful_sync,
                raw.provider_sync_state.last_successful_sync
            ),
            cursor = COALESCE(EXCLUDED.cursor, raw.provider_sync_state.cursor),
            status = EXCLUDED.status,
            updated_at = now()
        """
    )
    params = {
        "provider": provider_name,
        "entity_type": entity_type,
        "scope_key": scope_key,
        "league_id": league_id,
        "season": season,
        "last_successful_sync": datetime.utcnow() if update_last_successful_sync else None,
        "cursor": str(cursor) if cursor is not None else None,
        "status": status,
    }
    try:
        with engine.begin() as conn:
            conn.execute(sql, params)
    except Exception as exc:
        log_event(
            level="error",
            service="airflow",
            module="ingestion_service",
            step="write_sync_state",
            status="failed",
            dataset=entity_type,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            message=(
                "Falha ao persistir provider_sync_state; a ingestao sera marcada como falha "
                f"| provider={provider_name} entity_type={entity_type} scope={scope_key} status={status}"
            ),
        )
        raise RuntimeError(
            "Falha ao persistir provider_sync_state "
            f"| provider={provider_name} entity_type={entity_type} scope={scope_key} status={status} erro={exc}"
        ) from exc


def _resolve_pending_fixture_ids(
    *,
    s3_client,
    fixture_ids: list[int],
    skip_ingested: bool,
    s3_prefix: str,
    cursor: int | None,
    cursor_only: bool = False,
) -> tuple[list[int], set[int], str]:
    if not skip_ingested:
        return fixture_ids, set(), "skip_ingested=false"

    if cursor is not None:
        pending_fixture_ids = [fixture_id for fixture_id in fixture_ids if fixture_id > cursor]
        return pending_fixture_ids, set(), f"sync_state_cursor>{cursor}"

    if cursor_only:
        return fixture_ids, set(), "sync_state_only_cursor_missing"

    ingested_fixture_ids = _list_ingested_fixture_ids(s3_client, prefix=s3_prefix)
    pending_fixture_ids = [fixture_id for fixture_id in fixture_ids if fixture_id not in ingested_fixture_ids]
    return pending_fixture_ids, ingested_fixture_ids, "full_scan_s3"


def _list_completed_fixture_ids_for_prefixes(
    *,
    s3_client,
    required_s3_prefixes: list[str],
) -> set[int]:
    completed_fixture_ids: set[int] | None = None
    for prefix in required_s3_prefixes:
        prefix_fixture_ids = _list_ingested_fixture_ids(s3_client, prefix=prefix)
        if completed_fixture_ids is None:
            completed_fixture_ids = set(prefix_fixture_ids)
        else:
            completed_fixture_ids &= prefix_fixture_ids
        if not completed_fixture_ids:
            return set()
    return completed_fixture_ids or set()


def _resolve_pending_fixture_ids_for_complete_artifacts(
    *,
    s3_client,
    fixture_ids: list[int],
    skip_ingested: bool,
    required_s3_prefixes: list[str],
    cursor: int | None,
) -> tuple[list[int], set[int], str]:
    if not skip_ingested:
        return fixture_ids, set(), "skip_ingested=false"

    completed_fixture_ids = _list_completed_fixture_ids_for_prefixes(
        s3_client=s3_client,
        required_s3_prefixes=required_s3_prefixes,
    )
    pending_fixture_ids = [fixture_id for fixture_id in fixture_ids if fixture_id not in completed_fixture_ids]
    if cursor is not None:
        return pending_fixture_ids, completed_fixture_ids, f"required_prefixes_full_scan+cursor={cursor}"
    return pending_fixture_ids, completed_fixture_ids, "required_prefixes_full_scan"


def _missing_fixture_ids_from_multi_enrichments(
    *,
    requested_fixture_ids: list[int],
    enrichments_map: dict[int, dict[str, Any]],
) -> list[int]:
    returned_fixture_ids = {int(fixture_id) for fixture_id in enrichments_map}
    return [fixture_id for fixture_id in requested_fixture_ids if fixture_id not in returned_fixture_ids]


def _calculate_next_cursor(
    *,
    current_cursor: int | None,
    pending_fixture_ids: list[int],
    attempt_success_flags: list[bool],
) -> int | None:
    if not pending_fixture_ids or not attempt_success_flags:
        return current_cursor

    successful_prefix_size = 0
    for is_success in attempt_success_flags:
        if not is_success:
            break
        successful_prefix_size += 1

    if successful_prefix_size == 0:
        return current_cursor

    candidate_cursor = pending_fixture_ids[successful_prefix_size - 1]
    if current_cursor is None:
        return candidate_cursor
    return max(current_cursor, candidate_cursor)


def ingest_fixtures_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    windows = resolve_fixture_windows(context, season, provider_name=provider_name, league_id=league_id)

    requests_per_minute = _get_int_env(
        "INGEST_FIXTURES_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="FIXTURES_REQUESTS_PER_MINUTE",
        default="0",
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
    default_league_id = runtime["league_id"]
    default_season = runtime["season"]
    provider_name = runtime["provider"]

    requests_per_minute = _get_int_env(
        "INGEST_STATISTICS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="STATISTICS_REQUESTS_PER_MINUTE",
        default="0",
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

    targets = _resolve_statistics_targets(
        context=context,
        default_league_id=default_league_id,
        default_season=default_season,
        fetch_finished_fixture_ids=lambda league, year: _fetch_finished_fixture_ids(engine, league, year),
    )
    mode = targets["mode"]
    league_id = targets["league_id"]
    season = targets["season"]
    fixture_ids = targets["fixture_ids"]
    target_source = targets["target_source"]

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
                f"| provider={provider_name} | mode={mode} | league_id={league_id} | season={season} "
                f"| source={target_source} | statuses={FINAL_STATUSES}"
            ),
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    entity_type = "statistics"
    explicit_scope_fixture_ids = fixture_ids if (mode == "backfill" and target_source == "explicit_fixture_ids") else None
    scope_key = _sync_scope_key(
        league_id=league_id,
        season=season,
        mode=mode,
        fixture_ids=explicit_scope_fixture_ids,
    )
    current_cursor = _read_sync_cursor(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
    )
    effective_skip_ingested = True if mode == "backfill" else skip_ingested
    pending_fixture_ids, ingested_fixture_ids, pending_strategy = _resolve_pending_fixture_ids(
        s3_client=s3_client,
        fixture_ids=fixture_ids,
        skip_ingested=effective_skip_ingested,
        s3_prefix=f"statistics/league={league_id}/season={season}/",
        cursor=current_cursor,
        cursor_only=(mode == "backfill"),
    )

    if not pending_fixture_ids:
        bootstrap_cursor = fixture_ids[-1] if (effective_skip_ingested and current_cursor is None and fixture_ids) else current_cursor
        _upsert_sync_state(
            engine,
            provider_name=provider_name,
            entity_type=entity_type,
            scope_key=scope_key,
            league_id=league_id,
            season=season,
            cursor=bootstrap_cursor,
            status="idle",
            update_last_successful_sync=bootstrap_cursor is not None and bootstrap_cursor != current_cursor,
        )
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
                "Todos os fixtures alvo ja possuem dados no bronze "
                f"| provider={provider_name} | mode={mode} | source={target_source} "
                f"| total={len(fixture_ids)} | ingeridos_previamente={len(ingested_fixture_ids)} "
                f"| estrategia={pending_strategy} | skip_ingested_efetivo={effective_skip_ingested} "
                f"| cursor_atual={current_cursor} | cursor_persistido={bootstrap_cursor}"
            ),
        )
        return

    succeeded = 0
    failed = 0
    attempted = 0
    attempt_success_flags: list[bool] = []
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
                attempt_success_flags.append(True)
                consecutive_failures = 0

                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(pending_fixture_ids)}] provider={provider.name} fixture_id={fixture_id} "
                    f"salvo em s3://{BRONZE_BUCKET}/{key} | results={write_result['results']} "
                    f"| rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += 1
                attempt_success_flags.append(False)
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

    next_cursor = _calculate_next_cursor(
        current_cursor=current_cursor,
        pending_fixture_ids=pending_fixture_ids,
        attempt_success_flags=attempt_success_flags,
    )
    sync_status = "success" if succeeded == len(pending_fixture_ids) else ("failed" if succeeded == 0 else "partial")
    _upsert_sync_state(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
        league_id=league_id,
        season=season,
        cursor=next_cursor,
        status=sync_status,
        update_last_successful_sync=next_cursor is not None and next_cursor != current_cursor,
    )

    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status=sync_status,
        context=context,
        dataset="statistics",
        rows_in=attempted,
        rows_out=succeeded,
        row_count=succeeded,
        message=(
            "Raw statistics concluido "
            f"| provider={provider_name} | mode={mode} | source={target_source} "
            f"| league_id={league_id} | season={season} "
            f"| fixtures_total={len(fixture_ids)} | pendentes={len(pending_fixture_ids)} "
            f"| tentativas={attempted} | sucesso={succeeded} | falhas={failed} "
            f"| limite_diario={daily_limit_reached} | motivo={stop_reason} "
            f"| estrategia={pending_strategy} | skip_ingested_efetivo={effective_skip_ingested} "
            f"| cursor_anterior={current_cursor} | cursor_novo={next_cursor}"
        ),
    )

    if fail_on_partial and succeeded < len(pending_fixture_ids):
        raise RuntimeError(
            "Ingestao raw statistics parcial. "
            f"mode={mode} | source={target_source} | "
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
        default="0",
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
    entity_type = "match_events"
    scope_key = _sync_scope_key(league_id=league_id, season=season)
    current_cursor = _read_sync_cursor(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
    )
    pending_fixture_ids, ingested_fixture_ids, pending_strategy = _resolve_pending_fixture_ids(
        s3_client=s3_client,
        fixture_ids=fixture_ids,
        skip_ingested=skip_ingested,
        s3_prefix=f"events/league={league_id}/season={season}/",
        cursor=current_cursor,
    )

    if not pending_fixture_ids:
        bootstrap_cursor = fixture_ids[-1] if (skip_ingested and current_cursor is None and fixture_ids) else current_cursor
        _upsert_sync_state(
            engine,
            provider_name=provider_name,
            entity_type=entity_type,
            scope_key=scope_key,
            league_id=league_id,
            season=season,
            cursor=bootstrap_cursor,
            status="idle",
            update_last_successful_sync=bootstrap_cursor is not None and bootstrap_cursor != current_cursor,
        )
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
                f"| provider={provider_name} | total={len(fixture_ids)} | ingeridos_previamente={len(ingested_fixture_ids)} "
                f"| estrategia={pending_strategy} | cursor_atual={current_cursor} | cursor_persistido={bootstrap_cursor}"
            ),
        )
        return

    succeeded = 0
    failed = 0
    attempted = 0
    attempt_success_flags: list[bool] = []
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
                attempt_success_flags.append(True)
                consecutive_failures = 0

                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(pending_fixture_ids)}] provider={provider.name} fixture_id={fixture_id} "
                    f"eventos={events_count} salvo em s3://{BRONZE_BUCKET}/{key} "
                    f"| results={write_result['results']} | rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += 1
                attempt_success_flags.append(False)
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

    next_cursor = _calculate_next_cursor(
        current_cursor=current_cursor,
        pending_fixture_ids=pending_fixture_ids,
        attempt_success_flags=attempt_success_flags,
    )
    sync_status = "success" if succeeded == len(pending_fixture_ids) else ("failed" if succeeded == 0 else "partial")
    _upsert_sync_state(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
        league_id=league_id,
        season=season,
        cursor=next_cursor,
        status=sync_status,
        update_last_successful_sync=next_cursor is not None and next_cursor != current_cursor,
    )

    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status=sync_status,
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
            f"| limite_diario={daily_limit_reached} | motivo={stop_reason} "
            f"| estrategia={pending_strategy} | cursor_anterior={current_cursor} | cursor_novo={next_cursor}"
        ),
    )

    if fail_on_partial and succeeded < len(pending_fixture_ids):
        raise RuntimeError(
            "Ingestao raw match_events parcial. "
            f"pendentes={len(pending_fixture_ids)} | tentativas={attempted} | sucesso={succeeded} | falhas={failed} | "
            f"limite_diario={daily_limit_reached}."
        )


def _fetch_team_ids(engine, *, league_id: int, season: int) -> list[int]:
    sql = text(
        """
        SELECT DISTINCT team_id
        FROM (
          SELECT home_team_id AS team_id
          FROM raw.fixtures
          WHERE league_id = :league_id
            AND season = :season
            AND home_team_id IS NOT NULL
          UNION
          SELECT away_team_id AS team_id
          FROM raw.fixtures
          WHERE league_id = :league_id
            AND season = :season
            AND away_team_id IS NOT NULL
        ) t
        ORDER BY team_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"league_id": league_id, "season": season}).fetchall()
    return [int(row[0]) for row in rows]


def _fetch_player_ids_for_scope(engine, *, league_id: int, season: int) -> list[int]:
    lineup_sql = text(
        """
        SELECT DISTINCT fl.player_id
        FROM raw.fixture_lineups fl
        JOIN raw.fixtures f ON f.fixture_id = fl.fixture_id
        WHERE f.league_id = :league_id
          AND f.season = :season
          AND fl.player_id IS NOT NULL
        ORDER BY fl.player_id
        """
    )
    try:
        with engine.begin() as conn:
            rows = conn.execute(lineup_sql, {"league_id": league_id, "season": season}).fetchall()
        if rows:
            return [int(row[0]) for row in rows]
    except Exception:
        pass

    event_sql = text(
        """
        SELECT DISTINCT player_id
        FROM (
          SELECT e.player_id AS player_id
          FROM raw.match_events e
          JOIN raw.fixtures f ON f.fixture_id = e.fixture_id
          WHERE f.league_id = :league_id
            AND f.season = :season
            AND e.player_id IS NOT NULL
          UNION
          SELECT e.assist_id AS player_id
          FROM raw.match_events e
          JOIN raw.fixtures f ON f.fixture_id = e.fixture_id
          WHERE f.league_id = :league_id
            AND f.season = :season
            AND e.assist_id IS NOT NULL
        ) p
        ORDER BY player_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(event_sql, {"league_id": league_id, "season": season}).fetchall()
    return [int(row[0]) for row in rows]


def _fetch_coach_ids_for_scope(engine, *, provider_name: str, league_id: int, season: int) -> list[int]:
    sql = text(
        """
        SELECT DISTINCT tc.coach_id
        FROM raw.team_coaches tc
        WHERE tc.provider = :provider
          AND tc.coach_id IS NOT NULL
        ORDER BY tc.coach_id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {"provider": provider_name, "league_id": league_id, "season": season},
        ).fetchall()
    return [int(row[0]) for row in rows]


def _resolve_catalog_season_scope(
    engine,
    *,
    provider_name: str,
    league_id: int,
    season: int,
) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT
          cpm.competition_key,
          sc.season_label,
          sc.provider_season_id,
          sc.season_start_date,
          sc.season_end_date
        FROM control.competition_provider_map cpm
        JOIN control.season_catalog sc
          ON sc.provider = cpm.provider
         AND sc.competition_key = cpm.competition_key
        WHERE cpm.provider = :provider
          AND cpm.provider_league_id = :league_id
          AND LEFT(sc.season_label, 4) = :season_prefix
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "provider": provider_name,
                "league_id": league_id,
                "season_prefix": str(season),
            },
        ).mappings().all()

    if not rows:
        return None
    if len(rows) > 1:
        sample = [dict(row) for row in rows[:10]]
        raise RuntimeError(
            "Catalogo de seasons ambiguo para ingestao "
            f"provider={provider_name} league_id={league_id} season={season}. Escopos: {sample}"
        )

    scope = dict(rows[0])
    provider_season_id = scope.get("provider_season_id")
    if provider_season_id is not None:
        scope["provider_season_id"] = int(provider_season_id)
    for field_name in ("season_start_date", "season_end_date"):
        raw_value = scope.get(field_name)
        if raw_value is not None:
            scope[field_name] = raw_value.isoformat() if hasattr(raw_value, "isoformat") else str(raw_value)
    return scope


def _resolve_fixture_scope_identity(
    engine,
    *,
    provider_name: str,
    league_id: int,
    season: int,
) -> dict[str, Any]:
    sql = text(
        """
        SELECT DISTINCT
          f.source_provider AS provider,
          f.league_id AS provider_league_id,
          f.competition_key,
          f.season_label,
          f.provider_season_id
        FROM raw.fixtures f
        JOIN control.season_catalog sc
          ON sc.provider = f.source_provider
         AND sc.competition_key = f.competition_key
         AND sc.season_label = f.season_label
         AND sc.provider_season_id = f.provider_season_id
        WHERE f.source_provider = :provider
          AND f.league_id = :league_id
          AND f.season = :season
          AND f.competition_key IS NOT NULL
          AND f.season_label IS NOT NULL
          AND f.provider_season_id IS NOT NULL
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {"provider": provider_name, "league_id": league_id, "season": season},
        ).mappings().all()

    if not rows:
        raise RuntimeError(
            "Nao foi possivel resolver identidade semantica do escopo "
            f"via raw.fixtures + control.season_catalog para provider={provider_name} "
            f"league_id={league_id} season={season}."
        )
    if len(rows) > 1:
        sample = [dict(row) for row in rows[:10]]
        raise RuntimeError(
            "Escopo semantico ambiguo em raw.fixtures para ingestao "
            f"provider={provider_name} league_id={league_id} season={season}. Escopos: {sample}"
        )
    return dict(rows[0])


def _fetch_team_pairs(engine, *, league_id: int, season: int) -> list[tuple[int, int]]:
    sql = text(
        """
        SELECT DISTINCT
          LEAST(home_team_id, away_team_id) AS pair_team_id,
          GREATEST(home_team_id, away_team_id) AS pair_opponent_id
        FROM raw.fixtures
        WHERE league_id = :league_id
          AND season = :season
          AND home_team_id IS NOT NULL
          AND away_team_id IS NOT NULL
        ORDER BY 1, 2
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"league_id": league_id, "season": season}).fetchall()
    return [(int(row[0]), int(row[1])) for row in rows]


def _ingest_entity_by_numeric_ids(
    *,
    context: dict[str, Any],
    provider_name: str,
    provider,
    engine,
    s3_client,
    league_id: int,
    season: int,
    entity_type: str,
    endpoint: str,
    target_ids: list[int],
    key_prefix: str,
    id_name: str,
    fetch_fn: Callable[[int], tuple[dict[str, Any], dict[str, str]]],
    source_params_fn: Callable[[int], dict[str, Any]],
    scope_key: str,
    fail_on_partial: bool,
    max_consecutive_failures: int,
    force_reingest_ids: bool = False,
    use_cursor_state: bool = True,
) -> None:
    sorted_ids = sorted(set(target_ids))
    if not sorted_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step=f"ingest_{entity_type}_raw",
            status="success",
            context=context,
            dataset=entity_type,
            row_count=0,
            message=(
                f"Nenhum alvo encontrado para entity={entity_type} "
                f"| provider={provider_name} | league_id={league_id} | season={season}"
            ),
        )
        return

    current_cursor = _read_sync_cursor(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
    )
    if force_reingest_ids:
        pending_ids = sorted_ids
        pending_strategy = "explicit_fixture_ids_reingest"
    elif not use_cursor_state:
        ingested_ids = _list_ingested_numeric_ids(s3_client, prefix=f"{key_prefix}/", id_name=id_name)
        pending_ids = [item_id for item_id in sorted_ids if item_id not in ingested_ids]
        pending_strategy = f"full_scan_s3/{id_name}"
    elif current_cursor is None:
        ingested_ids = _list_ingested_numeric_ids(s3_client, prefix=f"{key_prefix}/", id_name=id_name)
        pending_ids = [item_id for item_id in sorted_ids if item_id not in ingested_ids]
        pending_strategy = f"full_scan_s3/{id_name}"
    else:
        pending_ids = [item_id for item_id in sorted_ids if item_id > current_cursor]
        pending_strategy = f"sync_state_cursor>{current_cursor}"

    if not pending_ids:
        cursor_to_store = sorted_ids[-1] if current_cursor is None else current_cursor
        _upsert_sync_state(
            engine,
            provider_name=provider_name,
            entity_type=entity_type,
            scope_key=scope_key,
            league_id=league_id,
            season=season,
            cursor=cursor_to_store,
            status="idle",
            update_last_successful_sync=cursor_to_store is not None and cursor_to_store != current_cursor,
        )
        log_event(
            service="airflow",
            module="ingestion_service",
            step=f"ingest_{entity_type}_raw",
            status="success",
            context=context,
            dataset=entity_type,
            rows_in=len(sorted_ids),
            rows_out=0,
            row_count=0,
            message=(
                f"Todos os alvos ja ingeridos para entity={entity_type} "
                f"| provider={provider_name} | total={len(sorted_ids)} | estrategia={pending_strategy} "
                f"| cursor_atual={current_cursor} | cursor_persistido={cursor_to_store}"
            ),
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    succeeded = 0
    failed = 0
    attempted = 0
    attempt_success_flags: list[bool] = []
    consecutive_failures = 0
    daily_limit_reached = False
    stop_reason = ""

    with StepMetrics(
        service="airflow",
        module="ingestion_service",
        step=f"ingest_{entity_type}_raw",
        context=context,
        dataset=entity_type,
        table="football-bronze",
    ) as metric:
        for idx, item_id in enumerate(pending_ids, start=1):
            try:
                attempted += 1
                payload, headers = fetch_fn(item_id)
                key = f"{key_prefix}/{id_name}={item_id}/run={run_utc}/data.json"
                write_result = write_raw_payload(
                    s3_client=s3_client,
                    bucket=BRONZE_BUCKET,
                    key=key,
                    payload=payload,
                    provider=provider.name,
                    endpoint=endpoint,
                    source_params=source_params_fn(item_id),
                    entity_type=entity_type,
                )
                succeeded += 1
                attempt_success_flags.append(True)
                consecutive_failures = 0
                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(pending_ids)}] entity={entity_type} provider={provider.name} {id_name}={item_id} "
                    f"salvo em s3://{BRONZE_BUCKET}/{key} | results={write_result['results']} | rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += 1
                attempt_success_flags.append(False)
                consecutive_failures += 1
                if _is_fatal_api_error(exc):
                    stop_reason = f"erro_fatal_api={exc}"
                    break
                if _is_daily_limit_error(exc):
                    daily_limit_reached = True
                    stop_reason = f"limite_diario={exc}"
                    break
                print(f"[{idx}/{len(pending_ids)}] erro entity={entity_type} {id_name}={item_id}: {exc}")

            if consecutive_failures >= max_consecutive_failures:
                stop_reason = f"falhas_consecutivas={consecutive_failures}"
                break

        metric.set_counts(rows_in=attempted, rows_out=succeeded, row_count=succeeded)

    next_cursor = _calculate_next_cursor(
        current_cursor=current_cursor,
        pending_fixture_ids=pending_ids,
        attempt_success_flags=attempt_success_flags,
    )
    sync_status = "success" if succeeded == len(pending_ids) else ("failed" if succeeded == 0 else "partial")
    _upsert_sync_state(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
        league_id=league_id,
        season=season,
        cursor=next_cursor,
        status=sync_status,
        update_last_successful_sync=next_cursor is not None and next_cursor != current_cursor,
    )
    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status=sync_status,
        context=context,
        dataset=entity_type,
        rows_in=attempted,
        rows_out=succeeded,
        row_count=succeeded,
        message=(
            f"Raw {entity_type} concluido | provider={provider_name} | league_id={league_id} | season={season} "
            f"| total={len(sorted_ids)} | pendentes={len(pending_ids)} | tentativas={attempted} "
            f"| sucesso={succeeded} | falhas={failed} | limite_diario={daily_limit_reached} "
            f"| motivo={stop_reason} | estrategia={pending_strategy} "
            f"| cursor_anterior={current_cursor} | cursor_novo={next_cursor}"
        ),
    )

    if fail_on_partial and succeeded < len(pending_ids):
        raise RuntimeError(
            f"Ingestao raw {entity_type} parcial. "
            f"pendentes={len(pending_ids)} | tentativas={attempted} | sucesso={succeeded} | falhas={failed}."
        )


def ingest_competition_structure_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_COMPETITION_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="COMPETITION_REQUESTS_PER_MINUTE",
        default="0",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    catalog_scope = _resolve_catalog_season_scope(
        engine,
        provider_name=provider_name,
        league_id=league_id,
        season=season,
    )
    provider_kwargs = {"league_id": league_id, "season": season}
    source_params = {"league_id": league_id, "season": season}
    if catalog_scope:
        provider_kwargs.update(
            {
                "season_label": catalog_scope["season_label"],
                "provider_season_id": catalog_scope["provider_season_id"],
                "season_start_date": catalog_scope["season_start_date"],
                "season_end_date": catalog_scope["season_end_date"],
            }
        )
        source_params.update(
            {
                "competition_key": catalog_scope["competition_key"],
                "season_label": catalog_scope["season_label"],
                "provider_season_id": catalog_scope["provider_season_id"],
            }
        )
    payload, headers = provider.get_competition_structure(**provider_kwargs)
    key = f"competition_structure/league={league_id}/season={season}/run={run_utc}/data.json"
    write_result = write_raw_payload(
        s3_client=s3_client,
        bucket=BRONZE_BUCKET,
        key=key,
        payload=payload,
        provider=provider.name,
        endpoint="competition/structure",
        source_params=source_params,
        entity_type="competition_structure",
    )
    rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status="success",
        context=context,
        dataset="competition_structure",
        rows_in=1,
        rows_out=write_result["results"],
        row_count=write_result["results"],
        message=(
            f"Raw competition_structure concluido | provider={provider_name} | league_id={league_id} | season={season} "
            f"| key={key} | rate_headers={rate_headers}"
        ),
    )


def ingest_standings_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_STANDINGS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="STANDINGS_REQUESTS_PER_MINUTE",
        default="0",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    catalog_scope = _resolve_catalog_season_scope(
        engine,
        provider_name=provider_name,
        league_id=league_id,
        season=season,
    )
    provider_kwargs = {"league_id": league_id, "season": season}
    source_params = {"league_id": league_id, "season": season}
    if catalog_scope:
        provider_kwargs.update(
            {
                "season_label": catalog_scope["season_label"],
                "provider_season_id": catalog_scope["provider_season_id"],
                "season_start_date": catalog_scope["season_start_date"],
                "season_end_date": catalog_scope["season_end_date"],
            }
        )
        source_params.update(
            {
                "competition_key": catalog_scope["competition_key"],
                "season_label": catalog_scope["season_label"],
                "provider_season_id": catalog_scope["provider_season_id"],
            }
        )
    payload, headers = provider.get_standings(**provider_kwargs)
    key = f"standings/league={league_id}/season={season}/run={run_utc}/data.json"
    write_result = write_raw_payload(
        s3_client=s3_client,
        bucket=BRONZE_BUCKET,
        key=key,
        payload=payload,
        provider=provider.name,
        endpoint="standings",
        source_params=source_params,
        entity_type="standings",
    )
    rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
    log_event(
        service="airflow",
        module="ingestion_service",
        step="summary",
        status="success",
        context=context,
        dataset="standings",
        rows_in=1,
        rows_out=write_result["results"],
        row_count=write_result["results"],
        message=(
            f"Raw standings concluido | provider={provider_name} | league_id={league_id} | season={season} "
            f"| key={key} | rate_headers={rate_headers}"
        ),
    )


def ingest_fixture_lineups_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    default_league_id = runtime["league_id"]
    default_season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_LINEUPS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="LINEUPS_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_LINEUPS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="LINEUPS_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_LINEUPS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="LINEUPS_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    targets = _resolve_statistics_targets(
        context=context,
        default_league_id=default_league_id,
        default_season=default_season,
        fetch_finished_fixture_ids=lambda league, year: _fetch_finished_fixture_ids(engine, league, year),
    )
    mode = targets["mode"]
    league_id = targets["league_id"]
    season = targets["season"]
    fixture_ids = targets["fixture_ids"]
    target_source = targets["target_source"]
    explicit_scope_fixture_ids = fixture_ids if (mode == "backfill" and target_source == "explicit_fixture_ids") else None
    scope_key = (
        _sync_scope_key(
            league_id=league_id,
            season=season,
            mode=mode,
            fixture_ids=explicit_scope_fixture_ids,
        )
        + "/entity=fixture_lineups"
    )

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="fixture_lineups",
        endpoint="fixtures/lineups",
        target_ids=fixture_ids,
        key_prefix=f"lineups/league={league_id}/season={season}",
        id_name="fixture_id",
        fetch_fn=lambda fixture_id: provider.get_fixture_lineups(fixture_id=fixture_id),
        source_params_fn=lambda fixture_id: {
            "league_id": league_id,
            "season": season,
            "fixture": fixture_id,
            "mode": mode,
            "source": target_source,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_fixture_player_statistics_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    default_league_id = runtime["league_id"]
    default_season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_PLAYER_STATS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="PLAYER_STATS_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_PLAYER_STATS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="PLAYER_STATS_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_PLAYER_STATS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="PLAYER_STATS_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    targets = _resolve_statistics_targets(
        context=context,
        default_league_id=default_league_id,
        default_season=default_season,
        fetch_finished_fixture_ids=lambda league, year: _fetch_finished_fixture_ids(engine, league, year),
    )
    mode = targets["mode"]
    league_id = targets["league_id"]
    season = targets["season"]
    fixture_ids = targets["fixture_ids"]
    target_source = targets["target_source"]
    explicit_scope_fixture_ids = fixture_ids if (mode == "backfill" and target_source == "explicit_fixture_ids") else None
    scope_key = (
        _sync_scope_key(
            league_id=league_id,
            season=season,
            mode=mode,
            fixture_ids=explicit_scope_fixture_ids,
        )
        + "/entity=fixture_player_statistics"
    )

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="fixture_player_statistics",
        endpoint="fixtures/player_statistics",
        target_ids=fixture_ids,
        key_prefix=f"fixture_player_statistics/league={league_id}/season={season}",
        id_name="fixture_id",
        fetch_fn=lambda fixture_id: provider.get_fixture_player_statistics(fixture_id=fixture_id),
        source_params_fn=lambda fixture_id: {
            "league_id": league_id,
            "season": season,
            "fixture": fixture_id,
            "mode": mode,
            "source": target_source,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
        force_reingest_ids=bool(explicit_scope_fixture_ids),
    )


def ingest_player_season_statistics_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_PLAYER_SEASON_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="PLAYER_SEASON_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_PLAYER_SEASON_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="PLAYER_SEASON_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_PLAYER_SEASON_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="PLAYER_SEASON_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    scope_identity = _resolve_fixture_scope_identity(
        engine,
        provider_name=provider_name,
        league_id=league_id,
        season=season,
    )
    player_ids = _fetch_player_ids_for_scope(engine, league_id=league_id, season=season)
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=player_season_statistics"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="player_season_statistics",
        endpoint="players/statistics",
        target_ids=player_ids,
        key_prefix=f"player_season_statistics/league={league_id}/season={season}",
        id_name="player_id",
        fetch_fn=lambda player_id: provider.get_player_season_statistics(
            player_id=player_id,
            season=season,
            league_id=league_id,
            season_label=scope_identity["season_label"],
            provider_season_id=int(scope_identity["provider_season_id"]),
        ),
        source_params_fn=lambda player_id: {
            "league_id": league_id,
            "season": season,
            "competition_key": scope_identity["competition_key"],
            "season_label": scope_identity["season_label"],
            "provider_season_id": int(scope_identity["provider_season_id"]),
            "player_id": player_id,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_player_transfers_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_TRANSFERS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="TRANSFERS_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_TRANSFERS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="TRANSFERS_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_TRANSFERS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="TRANSFERS_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    player_ids = _fetch_player_ids_for_scope(engine, league_id=league_id, season=season)
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=player_transfers"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="player_transfers",
        endpoint="players/transfers",
        target_ids=player_ids,
        key_prefix=f"player_transfers/league={league_id}/season={season}",
        id_name="player_id",
        fetch_fn=lambda player_id: provider.get_player_transfers(player_id=player_id),
        source_params_fn=lambda player_id: {
            "league_id": league_id,
            "season": season,
            "player_id": player_id,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_team_sidelined_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_SIDELINED_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="SIDELINED_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_SIDELINED_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="SIDELINED_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_SIDELINED_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="SIDELINED_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    team_ids = _fetch_team_ids(engine, league_id=league_id, season=season)
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=team_sidelined"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="team_sidelined",
        endpoint="teams/sidelined",
        target_ids=team_ids,
        key_prefix=f"team_sidelined/league={league_id}/season={season}",
        id_name="team_id",
        fetch_fn=lambda team_id: provider.get_team_sidelined(team_id=team_id, season=season),
        source_params_fn=lambda team_id: {
            "league_id": league_id,
            "season": season,
            "team_id": team_id,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_team_coaches_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_COACHES_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="COACHES_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_COACHES_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="COACHES_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_COACHES_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="COACHES_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    team_ids = _fetch_team_ids(engine, league_id=league_id, season=season)
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=team_coaches"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="team_coaches",
        endpoint="teams/coaches",
        target_ids=team_ids,
        key_prefix=f"team_coaches/league={league_id}/season={season}",
        id_name="team_id",
        fetch_fn=lambda team_id: provider.get_team_coaches(team_id=team_id),
        source_params_fn=lambda team_id: {
            "league_id": league_id,
            "season": season,
            "team_id": team_id,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_coaches_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_COACH_IDENTITIES_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="COACH_IDENTITIES_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_COACH_IDENTITIES_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="COACH_IDENTITIES_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_COACH_IDENTITIES_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="COACH_IDENTITIES_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    coach_ids = _fetch_coach_ids_for_scope(
        engine,
        provider_name=provider_name,
        league_id=league_id,
        season=season,
    )
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=coaches"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="coaches",
        endpoint="coaches",
        target_ids=coach_ids,
        key_prefix=f"coaches/league={league_id}/season={season}",
        id_name="coach_id",
        fetch_fn=lambda coach_id: provider.get_coach(coach_id=coach_id),
        source_params_fn=lambda coach_id: {
            "league_id": league_id,
            "season": season,
            "coach_id": coach_id,
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
        use_cursor_state=False,
    )


def ingest_head_to_head_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    league_id = runtime["league_id"]
    season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_H2H_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="H2H_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_H2H_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="H2H_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_H2H_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="H2H_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))
    scope_identity = _resolve_fixture_scope_identity(
        engine,
        provider_name=provider_name,
        league_id=league_id,
        season=season,
    )
    team_pairs = _fetch_team_pairs(engine, league_id=league_id, season=season)
    if not team_pairs:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_head_to_head_raw",
            status="success",
            context=context,
            dataset="head_to_head",
            row_count=0,
            message=f"Nenhum par de times encontrado para h2h | league_id={league_id} season={season}",
        )
        return

    pair_indices = list(range(1, len(team_pairs) + 1))
    pair_map = dict(zip(pair_indices, team_pairs))
    scope_key = _sync_scope_key(league_id=league_id, season=season) + "/entity=head_to_head"

    _ingest_entity_by_numeric_ids(
        context=context,
        provider_name=provider_name,
        provider=provider,
        engine=engine,
        s3_client=s3_client,
        league_id=league_id,
        season=season,
        entity_type="head_to_head",
        endpoint="fixtures/head-to-head",
        target_ids=pair_indices,
        key_prefix=f"head_to_head/league={league_id}/season={season}",
        id_name="pair_index",
        fetch_fn=lambda pair_index: provider.get_head_to_head(
            team_id=pair_map[pair_index][0],
            opponent_id=pair_map[pair_index][1],
            league_id=league_id,
            season=season,
            season_label=scope_identity["season_label"],
            provider_season_id=int(scope_identity["provider_season_id"]),
        ),
        source_params_fn=lambda pair_index: {
            "league_id": league_id,
            "season": season,
            "competition_key": scope_identity["competition_key"],
            "season_label": scope_identity["season_label"],
            "provider_season_id": int(scope_identity["provider_season_id"]),
            "pair_team_id": pair_map[pair_index][0],
            "pair_opponent_id": pair_map[pair_index][1],
        },
        scope_key=scope_key,
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=max_consecutive_failures,
    )


def ingest_fixture_enrichments_raw():
    context = get_current_context()
    runtime = resolve_runtime_params(context)
    default_league_id = runtime["league_id"]
    default_season = runtime["season"]
    provider_name = runtime["provider"]
    requests_per_minute = _get_int_env(
        "INGEST_ENRICHMENTS_REQUESTS_PER_MINUTE",
        provider_name=provider_name,
        provider_suffix="ENRICHMENTS_REQUESTS_PER_MINUTE",
        default="0",
    )
    fail_on_partial = _get_bool_env(
        "INGEST_ENRICHMENTS_FAIL_ON_PARTIAL",
        provider_name=provider_name,
        provider_suffix="ENRICHMENTS_FAIL_ON_PARTIAL",
        default="true",
    )
    max_consecutive_failures = _get_int_env(
        "INGEST_ENRICHMENTS_MAX_CONSECUTIVE_FAILURES",
        provider_name=provider_name,
        provider_suffix="ENRICHMENTS_MAX_CONSECUTIVE_FAILURES",
        default="5",
    )
    chunk_size = _get_int_env(
        "INGEST_ENRICHMENTS_CHUNK_SIZE",
        provider_name=provider_name,
        provider_suffix="ENRICHMENTS_CHUNK_SIZE",
        default="30",
    )
    
    provider = get_provider(provider_name, requests_per_minute=requests_per_minute)
    s3_client = _s3_client()
    engine = create_engine(_get_required_env("FOOTBALL_PG_DSN"))

    targets = _resolve_statistics_targets(
        context=context,
        default_league_id=default_league_id,
        default_season=default_season,
        fetch_finished_fixture_ids=lambda league, year: _fetch_finished_fixture_ids(engine, league, year),
    )
    mode = targets["mode"]
    league_id = targets["league_id"]
    season = targets["season"]
    fixture_ids = targets["fixture_ids"]
    target_source = targets["target_source"]
    explicit_scope_fixture_ids = fixture_ids if (mode == "backfill" and target_source == "explicit_fixture_ids") else None

    entity_type = "fixture_enrichments"
    scope_key = _sync_scope_key(
        league_id=league_id,
        season=season,
        mode=mode,
        fixture_ids=explicit_scope_fixture_ids,
    )

    if not fixture_ids:
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_fixture_enrichments_raw",
            status="success",
            context=context,
            dataset="fixture_enrichments",
            row_count=0,
            message=(
                "Nenhum fixture finalizado encontrado para enriquecimento"
                f"| provider={provider_name} | mode={mode} | league_id={league_id} | season={season} "
                f"| source={target_source} | statuses={FINAL_STATUSES}"
            ),
        )
        return

    current_cursor = _read_sync_cursor(
        engine,
        provider_name=provider_name,
        entity_type=entity_type,
        scope_key=scope_key,
    )

    required_s3_prefixes = [
        f"events/league={league_id}/season={season}/",
        f"statistics/league={league_id}/season={season}/",
        f"lineups/league={league_id}/season={season}/",
        f"fixture_player_statistics/league={league_id}/season={season}/",
    ]

    pending_fixture_ids, ingested_fixture_ids, pending_strategy = _resolve_pending_fixture_ids_for_complete_artifacts(
        s3_client=s3_client,
        fixture_ids=fixture_ids,
        skip_ingested=True
        if mode == "backfill"
        else _get_bool_env(
            "INGEST_ENRICHMENTS_SKIP_INGESTED",
            provider_name=provider_name,
            provider_suffix="ENRICHMENTS_SKIP_INGESTED",
            default="true",
        ),
        required_s3_prefixes=required_s3_prefixes,
        cursor=current_cursor,
    )

    if not pending_fixture_ids:
        bootstrap_cursor = fixture_ids[-1] if (current_cursor is None and fixture_ids) else current_cursor
        _upsert_sync_state(
            engine,
            provider_name=provider_name,
            entity_type=entity_type,
            scope_key=scope_key,
            league_id=league_id,
            season=season,
            cursor=bootstrap_cursor,
            status="idle",
            update_last_successful_sync=bootstrap_cursor is not None and bootstrap_cursor != current_cursor,
        )
        log_event(
            service="airflow",
            module="ingestion_service",
            step="ingest_fixture_enrichments_raw",
            status="success",
            context=context,
            dataset="fixture_enrichments",
            row_count=0,
            rows_in=len(fixture_ids),
            rows_out=0,
            message=(
                "Todos os fixtures alvo ja possuem dados de enriquecimento no bronze "
                f"| provider={provider_name} | mode={mode} | source={target_source} "
                f"| total={len(fixture_ids)} | ingeridos_previamente={len(ingested_fixture_ids)} "
                f"| estrategia={pending_strategy} | cursor_atual={current_cursor} | cursor_persistido={bootstrap_cursor}"
            ),
        )
        return

    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    succeeded = 0
    failed = 0
    attempted = 0
    attempt_success_flags: list[bool] = []
    consecutive_failures = 0
    daily_limit_reached = False
    stop_reason = ""

    chunks = [pending_fixture_ids[i:i + chunk_size] for i in range(0, len(pending_fixture_ids), chunk_size)]

    with StepMetrics(
        service="airflow",
        module="ingestion_service",
        step="ingest_fixture_enrichments_raw",
        context=context,
        dataset="fixture_enrichments",
        table="football-bronze",
    ) as metric:
        for idx, chunk in enumerate(chunks, start=1):
            try:
                attempted += len(chunk)
                enrichments_map, headers = provider.get_fixtures_multi_enrichments(fixture_ids=chunk)
                missing_fixture_ids = _missing_fixture_ids_from_multi_enrichments(
                    requested_fixture_ids=chunk,
                    enrichments_map=enrichments_map,
                )
                if missing_fixture_ids:
                    returned_fixture_ids = sorted(int(fixture_id) for fixture_id in enrichments_map)
                    raise RuntimeError(
                        "Payload multi incompleto para fixture_enrichments "
                        f"| requested={chunk} | returned={returned_fixture_ids} | missing={missing_fixture_ids}"
                    )

                for fid in chunk:
                    fixture_enrichment = enrichments_map.get(fid)
                    if not fixture_enrichment:
                        continue
                    
                    for sub_entity, payload in fixture_enrichment.items():
                        if sub_entity == "match_events":
                            prefix = "events"
                            endpoint_name = "fixtures/events"
                        elif sub_entity == "statistics":
                            prefix = "statistics"
                            endpoint_name = "fixtures/statistics"
                        elif sub_entity == "fixture_lineups":
                            prefix = "lineups"
                            endpoint_name = "fixtures/lineups"
                        else:
                            prefix = "fixture_player_statistics"
                            endpoint_name = "fixtures/player_statistics"

                        key = f"{prefix}/league={league_id}/season={season}/fixture_id={fid}/run={run_utc}/data.json"
                        write_raw_payload(
                            s3_client=s3_client,
                            bucket=BRONZE_BUCKET,
                            key=key,
                            payload=payload,
                            provider=provider.name,
                            endpoint=endpoint_name,
                            source_params={"fixture": fid, "league_id": league_id, "season": season},
                            entity_type=sub_entity,
                        )
                
                succeeded += len(chunk)
                attempt_success_flags.extend([True] * len(chunk))
                consecutive_failures = 0

                rate_headers = {k: v for k, v in headers.items() if "rate" in k.lower() or "limit" in k.lower()}
                print(
                    f"[{idx}/{len(chunks)}] chunk_size={len(chunk)} provider={provider.name} "
                    f"salvo no s3 com sucesso | rate_headers={rate_headers}"
                )
            except Exception as exc:
                failed += len(chunk)
                attempt_success_flags.extend([False] * len(chunk))
                consecutive_failures += 1
                if _is_fatal_api_error(exc):
                    stop_reason = f"erro_fatal_api={exc}"
                    break
                if _is_daily_limit_error(exc):
                    daily_limit_reached = True
                    stop_reason = f"limite_diario={exc}"
                    break
                stop_reason = str(exc)
                print(f"[{idx}/{len(chunks)}] erro no chunk: {exc}")

            if consecutive_failures >= max_consecutive_failures:
                stop_reason = f"falhas_consecutivas={consecutive_failures}"
                break

        metric.set_counts(rows_in=attempted, rows_out=succeeded, row_count=succeeded)

        next_cursor = _calculate_next_cursor(
            current_cursor=current_cursor,
            pending_fixture_ids=pending_fixture_ids,
            attempt_success_flags=attempt_success_flags,
        )
        sync_status = "success" if succeeded == len(pending_fixture_ids) else ("failed" if succeeded == 0 else "partial")
        _upsert_sync_state(
            engine,
            provider_name=provider_name,
            entity_type=entity_type,
            scope_key=scope_key,
            league_id=league_id,
            season=season,
            cursor=next_cursor,
            status=sync_status,
            update_last_successful_sync=next_cursor is not None and next_cursor != current_cursor,
        )

        log_event(
            service="airflow",
            module="ingestion_service",
            step="summary",
            status=sync_status,
            context=context,
            dataset="fixture_enrichments",
            rows_in=attempted,
            rows_out=succeeded,
            row_count=succeeded,
            message=(
                "Raw fixture_enrichments concluido "
                f"| provider={provider_name} | mode={mode} | source={target_source} "
                f"| league_id={league_id} | season={season} "
                f"| fixtures_total={len(fixture_ids)} | pendentes={len(pending_fixture_ids)} "
                f"| tentativas={attempted} | sucesso={succeeded} | falhas={failed} "
                f"| limite_diario={daily_limit_reached} | motivo={stop_reason} "
                f"| estrategia={pending_strategy} "
                f"| cursor_anterior={current_cursor} | cursor_novo={next_cursor}"
            ),
        )

        if fail_on_partial and succeeded < len(pending_fixture_ids):
            raise RuntimeError(
                "Ingestao raw fixture_enrichments parcial. "
                f"mode={mode} | source={target_source} | "
                f"pendentes={len(pending_fixture_ids)} | tentativas={attempted} | sucesso={succeeded} | falhas={failed} | "
                f"limite_diario={daily_limit_reached}."
            )
