#!/usr/bin/env python
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_DASHBOARDS = [
    "Ranking Mensal",
    "Forma Recente",
    "Desempenho Casa/Fora",
    "Gols por Minuto",
]


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value or ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_sort(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_json_sort(v) for v in obj]
    return obj


def _sanitize_card(card: dict[str, Any], collection_name_by_id: dict[int, str | None]) -> dict[str, Any]:
    dataset_query = card.get("dataset_query")
    return {
        "name": card.get("name"),
        "description": card.get("description"),
        "display": card.get("display"),
        "visualization_settings": card.get("visualization_settings") or {},
        "dataset_query": dataset_query,
        "collection_name": collection_name_by_id.get(card.get("collection_id")),
        "archived": bool(card.get("archived", False)),
    }


def _sanitize_dashboard(
    dashboard: dict[str, Any],
    card_name_by_id: dict[int, str],
    collection_name_by_id: dict[int, str | None],
) -> dict[str, Any]:
    dashcards = []
    for dcard in dashboard.get("ordered_cards", []):
        card = dcard.get("card") or {}
        card_id = card.get("id")
        card_name = card_name_by_id.get(card_id)
        if not card_name:
            continue

        dashcards.append(
            {
                "card_name": card_name,
                "row": dcard.get("row"),
                "col": dcard.get("col"),
                "size_x": dcard.get("size_x"),
                "size_y": dcard.get("size_y"),
                "parameter_mappings": dcard.get("parameter_mappings") or [],
                "visualization_settings": dcard.get("visualization_settings") or {},
            }
        )

    return {
        "name": dashboard.get("name"),
        "description": dashboard.get("description"),
        "parameters": dashboard.get("parameters") or [],
        "collection_name": collection_name_by_id.get(dashboard.get("collection_id")),
        "archived": bool(dashboard.get("archived", False)),
        "dashcards": sorted(dashcards, key=lambda x: (x.get("row", 0), x.get("col", 0), x.get("card_name", ""))),
    }


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


def main():
    parser = argparse.ArgumentParser(description="Exporta dashboards do Metabase para JSON versionavel.")
    parser.add_argument(
        "--out",
        default="tools/metabase/exports/metabase_export.json",
        help="Arquivo de saida JSON.",
    )
    parser.add_argument(
        "--dashboards",
        default=",".join(DEFAULT_DASHBOARDS),
        help="Lista separada por virgula dos nomes de dashboards para exportar.",
    )
    args = parser.parse_args()

    base_url = _env("METABASE_URL", "http://localhost:3000")
    username = _env("METABASE_USERNAME", required=True)
    password = _env("METABASE_PASSWORD", required=True)

    dashboard_names = [name.strip() for name in args.dashboards.split(",") if name.strip()]

    session = _login(base_url, username, password)

    dashboards = _get_json(session, f"{base_url}/api/dashboard")
    dashboards_by_name = {d.get("name"): d for d in dashboards}

    selected = []
    missing = []
    for name in dashboard_names:
        dash = dashboards_by_name.get(name)
        if dash:
            selected.append(dash)
        else:
            missing.append(name)

    if not selected:
        raise RuntimeError(
            "Nenhum dashboard encontrado para exportacao. "
            f"Solicitados={dashboard_names}"
        )

    card_ids = set()
    dashboards_full = []
    for dash in selected:
        full = _get_json(session, f"{base_url}/api/dashboard/{dash['id']}")
        dashboards_full.append(full)
        for dcard in full.get("ordered_cards", []):
            card = dcard.get("card") or {}
            if card.get("id"):
                card_ids.add(int(card["id"]))

    cards_full = []
    for card_id in sorted(card_ids):
        cards_full.append(_get_json(session, f"{base_url}/api/card/{card_id}"))

    collection_ids = set()
    for card in cards_full:
        if card.get("collection_id") is not None:
            collection_ids.add(int(card["collection_id"]))
    for dash in dashboards_full:
        if dash.get("collection_id") is not None:
            collection_ids.add(int(dash["collection_id"]))

    collections = {}
    for collection_id in sorted(collection_ids):
        detail = _get_json(session, f"{base_url}/api/collection/{collection_id}")
        collections[collection_id] = {
            "name": detail.get("name"),
            "description": detail.get("description"),
            "slug": detail.get("slug"),
            "archived": bool(detail.get("archived", False)),
        }

    collection_name_by_id = {k: v.get("name") for k, v in collections.items()}

    cards_by_name = {}
    for card in cards_full:
        cards_by_name[card.get("name")] = _sanitize_card(card, collection_name_by_id)

    card_name_by_id = {int(card["id"]): card.get("name") for card in cards_full if card.get("id")}

    dashboards_payload = {}
    for dash in dashboards_full:
        dashboards_payload[dash.get("name")] = _sanitize_dashboard(
            dash,
            card_name_by_id=card_name_by_id,
            collection_name_by_id=collection_name_by_id,
        )

    payload = {
        "meta": {
            "exported_at": _now_iso(),
            "source": base_url,
            "dashboard_names": dashboard_names,
            "missing_dashboards": missing,
            "format_version": 1,
        },
        "collections": _json_sort({v["name"]: v for v in collections.values() if v.get("name")}),
        "cards": _json_sort(cards_by_name),
        "dashboards": _json_sort(dashboards_payload),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "Export concluido | "
        f"dashboards={len(dashboards_payload)} | cards={len(cards_by_name)} | collections={len(payload['collections'])} | "
        f"missing={missing} | out={out}"
    )


if __name__ == "__main__":
    main()
