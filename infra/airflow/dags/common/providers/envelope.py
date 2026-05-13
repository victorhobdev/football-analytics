from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


CANONICAL_SCHEMA_VERSION = "2.0.0"


def _stable_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_envelope(
    *,
    provider: str,
    entity_type: str,
    response: list[dict[str, Any]],
    source_params: dict[str, Any],
    errors: list[Any] | dict[str, Any] | None = None,
    provider_meta: dict[str, Any] | None = None,
    schema_version: str = CANONICAL_SCHEMA_VERSION,
) -> dict[str, Any]:
    ingested_at = datetime.now(timezone.utc).isoformat()
    normalized_errors = errors if errors is not None else []
    payload_no_hash: dict[str, Any] = {
        "provider": provider,
        "entity_type": entity_type,
        "schema_version": schema_version,
        "ingested_at": ingested_at,
        "source_params": source_params,
        "provider_meta": provider_meta or {},
        "results": len(response),
        "errors": normalized_errors,
        "response": response,
    }
    payload_no_hash["payload_hash"] = _stable_json_hash(payload_no_hash)
    return payload_no_hash
