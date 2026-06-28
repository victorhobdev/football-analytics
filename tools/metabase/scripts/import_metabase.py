#!/usr/bin/env python
import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value or ""


def _login(base_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{base_url}/api/session",
        json={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("id")
    if not token:
        raise RuntimeError("Falha ao autenticar no Metabase: token de sessao ausente")
    session.headers.update({"X-Metabase-Session": token})
    return session


def _get_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _post_json(session: requests.Session, url: str, payload: dict[str, Any]) -> Any:
    response = session.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def _put_json(session: requests.Session, url: str, payload: dict[str, Any]) -> Any:
    response = session.put(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def _delete(session: requests.Session, url: str) -> None:
    response = session.delete(url, timeout=30)
    response.raise_for_status()


def _ensure_collection(session: requests.Session, base_url: str, name: str | None) -> int | None:
    if not name:
        return None

    all_collections = _get_json(session, f"{base_url}/api/collection")
    for c in all_collections:
        if c.get("name") == name:
            return c.get("id")

    created = _post_json(session, f"{base_url}/api/collection", {"name": name})
    return created.get("id")


def _get_database_id(session: requests.Session, base_url: str, database_name: str) -> int:
    databases = _get_json(session, f"{base_url}/api/database")
    for db in databases.get("data", databases):
        if db.get("name") == database_name:
            return int(db["id"])
    raise RuntimeError(f"Database '{database_name}' nao encontrado no Metabase")


def _patch_dataset_query_database(dataset_query: dict[str, Any], target_db_id: int) -> dict[str, Any]:
    query = json.loads(json.dumps(dataset_query))
    if not isinstance(query, dict):
        return query

    if "database" in query and isinstance(query["database"], int):
        query["database"] = target_db_id

    if "query" in query and isinstance(query["query"], dict):
        nested = query["query"]
        if "source-table" in nested and isinstance(nested.get("source-table"), str):
            pass

    return query


def main():
    parser = argparse.ArgumentParser(description="Importa artefatos versionados do Metabase.")
    parser.add_argument(
        "--in-file",
        default="tools/metabase/exports/metabase_export.json",
        help="Arquivo exportado do Metabase.",
    )
    args = parser.parse_args()

    base_url = _env("METABASE_URL", "http://localhost:3000")
    username = _env("METABASE_USERNAME", required=True)
    password = _env("METABASE_PASSWORD", required=True)
    database_name = _env("METABASE_DATABASE_NAME", "football_dw")

    payload = json.loads(Path(args.in_file).read_text(encoding="utf-8"))

    session = _login(base_url, username, password)
    target_db_id = _get_database_id(session, base_url, database_name)

    collection_name_to_id: dict[str, int] = {}
    for collection_name in sorted(payload.get("collections", {}).keys()):
        cid = _ensure_collection(session, base_url, collection_name)
        if cid is not None:
            collection_name_to_id[collection_name] = int(cid)

    existing_cards = _get_json(session, f"{base_url}/api/card")
    card_by_name = {c.get("name"): c for c in existing_cards}

    created_cards = 0
    updated_cards = 0
    card_name_to_id: dict[str, int] = {}

    for card_name, card in payload.get("cards", {}).items():
        collection_id = collection_name_to_id.get(card.get("collection_name"))
        dataset_query = _patch_dataset_query_database(card.get("dataset_query") or {}, target_db_id)

        body = {
            "name": card_name,
            "description": card.get("description"),
            "display": card.get("display") or "table",
            "visualization_settings": card.get("visualization_settings") or {},
            "dataset_query": dataset_query,
            "collection_id": collection_id,
            "archived": bool(card.get("archived", False)),
        }

        if card_name in card_by_name:
            card_id = int(card_by_name[card_name]["id"])
            _put_json(session, f"{base_url}/api/card/{card_id}", body)
            updated_cards += 1
            card_name_to_id[card_name] = card_id
        else:
            created = _post_json(session, f"{base_url}/api/card", body)
            created_cards += 1
            card_name_to_id[card_name] = int(created["id"])

    dashboards_existing = _get_json(session, f"{base_url}/api/dashboard")
    dashboard_by_name = {d.get("name"): d for d in dashboards_existing}

    created_dashboards = 0
    updated_dashboards = 0

    for dashboard_name, dashboard in payload.get("dashboards", {}).items():
        collection_id = collection_name_to_id.get(dashboard.get("collection_name"))
        base_body = {
            "name": dashboard_name,
            "description": dashboard.get("description"),
            "parameters": dashboard.get("parameters") or [],
            "collection_id": collection_id,
            "archived": bool(dashboard.get("archived", False)),
        }

        if dashboard_name in dashboard_by_name:
            dashboard_id = int(dashboard_by_name[dashboard_name]["id"])
            _put_json(session, f"{base_url}/api/dashboard/{dashboard_id}", base_body)
            updated_dashboards += 1
        else:
            created = _post_json(session, f"{base_url}/api/dashboard", base_body)
            dashboard_id = int(created["id"])
            updated_dashboards += 1
            created_dashboards += 1

        full = _get_json(session, f"{base_url}/api/dashboard/{dashboard_id}")
        for dcard in full.get("ordered_cards", []):
            _delete(session, f"{base_url}/api/dashboard/{dashboard_id}/cards/{dcard['id']}")

        for dashcard in dashboard.get("dashcards", []):
            card_id = card_name_to_id.get(dashcard.get("card_name"))
            if not card_id:
                continue
            _post_json(
                session,
                f"{base_url}/api/dashboard/{dashboard_id}/cards",
                {
                    "cardId": card_id,
                    "row": dashcard.get("row", 0),
                    "col": dashcard.get("col", 0),
                    "sizeX": dashcard.get("size_x", 6),
                    "sizeY": dashcard.get("size_y", 4),
                    "parameter_mappings": dashcard.get("parameter_mappings") or [],
                    "visualization_settings": dashcard.get("visualization_settings") or {},
                },
            )

    print(
        "Import concluido | "
        f"cards_created={created_cards} | cards_updated={updated_cards} | "
        f"dashboards_created={created_dashboards} | dashboards_updated={updated_dashboards}"
    )


if __name__ == "__main__":
    main()
