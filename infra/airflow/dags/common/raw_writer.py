from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from io import BytesIO
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def enrich_raw_payload(
    *,
    payload: dict[str, Any],
    provider: str,
    endpoint: str,
    source_params: dict[str, Any],
    entity_type: str,
    schema_version: str = "2.0.0",
) -> dict[str, Any]:
    out = dict(payload)
    out["provider"] = provider
    out["entity_type"] = entity_type
    out["source_endpoint"] = endpoint
    out["source_params"] = source_params
    out.setdefault("schema_version", schema_version)
    out.setdefault("ingested_at", _utc_now())

    hash_payload = dict(out)
    hash_payload.pop("payload_hash", None)
    out["payload_hash"] = _stable_hash(hash_payload)
    out["results"] = int(out.get("results", len(out.get("response", []) or [])) or 0)
    return out


def write_raw_payload(
    *,
    s3_client,
    bucket: str,
    key: str,
    payload: dict[str, Any],
    provider: str,
    endpoint: str,
    source_params: dict[str, Any],
    entity_type: str,
) -> dict[str, Any]:
    normalized = enrich_raw_payload(
        payload=payload,
        provider=provider,
        endpoint=endpoint,
        source_params=source_params,
        entity_type=entity_type,
    )
    raw = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
    s3_client.upload_fileobj(BytesIO(raw), bucket, key)
    return {
        "key": key,
        "results": int(normalized.get("results", 0) or 0),
        "payload_hash": normalized.get("payload_hash"),
        "ingested_at": normalized.get("ingested_at"),
    }
