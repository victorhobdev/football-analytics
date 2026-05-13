from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from io import BytesIO

import boto3


BRONZE_BUCKET = "football-bronze"


def write_raw(
    provider: str,
    endpoint: str,
    params: dict,
    payload: dict,
) -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=_required_env("MINIO_ENDPOINT_URL"),
        aws_access_key_id=_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_required_env("MINIO_SECRET_KEY"),
    )

    ingested_at = datetime.now(timezone.utc).isoformat()
    normalized = dict(payload)
    normalized["provider"] = provider
    normalized["endpoint"] = endpoint
    normalized["request_params"] = params
    normalized["ingested_at"] = ingested_at
    normalized["payload_hash"] = _payload_hash(normalized)

    key = _build_key(endpoint=endpoint, params=params)
    body = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
    s3.upload_fileobj(BytesIO(body), BRONZE_BUCKET, key)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_key(*, endpoint: str, params: dict) -> str:
    run_utc = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    endpoint_name = endpoint.strip("/").lower()

    if endpoint_name == "fixtures":
        league = params.get("league") or params.get("league_id") or "unknown"
        season = params.get("season") or "unknown"
        date_from = params.get("from") or params.get("date_from")
        date_to = params.get("to") or params.get("date_to")
        if date_from and date_to:
            return (
                f"fixtures/league={league}/season={season}"
                f"/from={date_from}/to={date_to}/run={run_utc}/data.json"
            )
        return f"fixtures/league={league}/season={season}/run={run_utc}/data.json"

    if endpoint_name == "standings":
        league = params.get("league") or params.get("league_id") or "unknown"
        season = params.get("season") or "unknown"
        return f"standings/league={league}/season={season}/run={run_utc}/data.json"

    sanitized = endpoint_name.replace("/", "_")
    return f"{sanitized}/run={run_utc}/data.json"

