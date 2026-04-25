from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.src.db.client import db_client

SQL_PATH = ROOT / "quality" / "coach_assignment_audit.sql"
CSV_PATH = ROOT / "quality" / "coach_assignment_audit_sample.csv"
JSON_PATH = ROOT / "quality" / "coach_assignment_audit_sample.json"
SUMMARY_PATH = ROOT / "quality" / "coach_assignment_audit_summary.md"


def _to_int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    return int(value) if value is not None else 0


def _top_entries(rows: list[dict[str, object]], *, key: str, limit: int = 10) -> list[dict[str, object]]:
    ranked = [row for row in rows if _to_int(row, key) > 0]
    ranked.sort(
        key=lambda row: (
            -_to_int(row, key),
            -_to_int(row, "matches_without_assignment"),
            -_to_int(row, "matches_with_conflict"),
            str(row.get("competition_key") or ""),
            str(row.get("team_name") or ""),
        )
    )
    return ranked[:limit]


def _aggregate_by_competition(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, object, object], dict[str, object]] = {}
    for row in rows:
        key = (row.get("competition_key"), row.get("league_id"), row.get("season"))
        bucket = grouped.setdefault(
            key,
            {
                "competition_key": row.get("competition_key"),
                "league_id": row.get("league_id"),
                "season": row.get("season"),
                "teams": 0,
                "matches_total": 0,
                "matches_with_assignment": 0,
                "matches_without_assignment": 0,
                "matches_with_conflict": 0,
                "invalid_name_tenures": 0,
                "future_tenures_hidden": 0,
                "assistant_as_head_risk": 0,
                "impacted_teams": 0,
            },
        )
        bucket["teams"] = int(bucket["teams"]) + 1
        bucket["matches_total"] = int(bucket["matches_total"]) + _to_int(row, "matches_total")
        bucket["matches_with_assignment"] = int(bucket["matches_with_assignment"]) + _to_int(row, "matches_with_assignment")
        bucket["matches_without_assignment"] = int(bucket["matches_without_assignment"]) + _to_int(row, "matches_without_assignment")
        bucket["matches_with_conflict"] = int(bucket["matches_with_conflict"]) + _to_int(row, "matches_with_conflict")
        bucket["invalid_name_tenures"] = int(bucket["invalid_name_tenures"]) + _to_int(row, "invalid_name_tenures")
        bucket["future_tenures_hidden"] = int(bucket["future_tenures_hidden"]) + _to_int(row, "future_tenures_hidden")
        bucket["assistant_as_head_risk"] = int(bucket["assistant_as_head_risk"]) + _to_int(row, "assistant_as_head_risk")
        if bool(row.get("public_surface_impacted")):
            bucket["impacted_teams"] = int(bucket["impacted_teams"]) + 1

    summary = list(grouped.values())
    summary.sort(
        key=lambda row: (
            -int(row["matches_without_assignment"]),
            -int(row["matches_with_conflict"]),
            -int(row["matches_total"]),
            str(row["competition_key"] or ""),
        )
    )
    return summary[:10]


def _flamengo_slice(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    filtered = [
        row
        for row in rows
        if str(row.get("team_name") or "").strip().lower() == "flamengo"
        and row.get("season") in {2020, 2021, 2022, 2023, 2024, 2025}
    ]
    filtered.sort(key=lambda row: (int(row.get("season") or 0), str(row.get("competition_key") or "")))
    return filtered


def _write_csv(rows: list[dict[str, object]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "competition_key",
        "league_id",
        "season",
        "team_id",
        "team_name",
        "matches_total",
        "matches_with_assignment",
        "matches_without_assignment",
        "matches_with_conflict",
        "invalid_name_tenures",
        "future_tenures_hidden",
        "assistant_as_head_risk",
        "public_surface_impacted",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def _write_json(rows: list[dict[str, object]]) -> None:
    JSON_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_row(row: dict[str, object]) -> str:
    return (
        f"- `{row.get('competition_key')}` {row.get('season')} | {row.get('team_name')} | "
        f"sem técnico: {_to_int(row, 'matches_without_assignment')} | "
        f"conflitos: {_to_int(row, 'matches_with_conflict')} | "
        f"risco assistant: {_to_int(row, 'assistant_as_head_risk')}"
    )


def _write_summary(rows: list[dict[str, object]]) -> None:
    total_rows = len(rows)
    total_matches = sum(_to_int(row, "matches_total") for row in rows)
    matches_with_assignment = sum(_to_int(row, "matches_with_assignment") for row in rows)
    matches_without_assignment = sum(_to_int(row, "matches_without_assignment") for row in rows)
    matches_with_conflict = sum(_to_int(row, "matches_with_conflict") for row in rows)
    invalid_name_tenures = sum(_to_int(row, "invalid_name_tenures") for row in rows)
    future_tenures_hidden = sum(_to_int(row, "future_tenures_hidden") for row in rows)
    assistant_as_head_risk = sum(_to_int(row, "assistant_as_head_risk") for row in rows)
    impacted_rows = sum(1 for row in rows if bool(row.get("public_surface_impacted")))
    assignment_rate = (matches_with_assignment / total_matches * 100) if total_matches else 0.0

    top_missing = _top_entries(rows, key="matches_without_assignment", limit=10)
    top_conflicts = _top_entries(rows, key="matches_with_conflict", limit=10)
    top_competitions = _aggregate_by_competition(rows)
    flamengo_rows = _flamengo_slice(rows)

    lines = [
        "# Coach assignment audit",
        "",
        "## Recorte executado",
        "",
        "- Corte público: `2025-12-31`",
        "- Fonte principal de passagem: `mart.stg_team_coaches`",
        "- Fonte principal de partidas: `mart.fact_matches`",
        "- Fontes auxiliares de identidade: `mart.dim_coach`, `raw.coaches`",
        "- Fonte de lineup/súmula de técnico: inexistente nas tabelas atuais; `fixture_lineups` é player-only",
        "",
        "## Resumo executivo",
        "",
        f"- Linhas auditadas (competição/temporada/time): `{total_rows}`",
        f"- Match-team públicos auditados: `{total_matches}`",
        f"- Match-team com atribuição atual possível: `{matches_with_assignment}` ({assignment_rate:.1f}%)",
        f"- Match-team sem técnico atribuível hoje: `{matches_without_assignment}`",
        f"- Match-team com conflito de múltiplos elegíveis: `{matches_with_conflict}`",
        f"- Passagens com nome inválido: `{invalid_name_tenures}`",
        f"- Passagens futuras escondidas pelo corte: `{future_tenures_hidden}`",
        f"- Riscos de assistant competindo com principal: `{assistant_as_head_risk}`",
        f"- Linhas impactadas para superfície pública: `{impacted_rows}`",
        "",
        "## Principais áreas sem cobertura",
        "",
    ]
    lines.extend([_format_row(row) for row in top_missing] or ["- Nenhuma"])
    lines.extend(
        [
            "",
            "## Principais áreas com conflito",
            "",
        ]
    )
    lines.extend([_format_row(row) for row in top_conflicts] or ["- Nenhuma"])
    lines.extend(
        [
            "",
            "## Competições mais afetadas",
            "",
        ]
    )

    if top_competitions:
        for row in top_competitions:
            lines.append(
                f"- `{row['competition_key']}` {row['season']} | times impactados: `{row['impacted_teams']}/{row['teams']}` | "
                f"sem técnico: `{row['matches_without_assignment']}` | conflitos: `{row['matches_with_conflict']}`"
            )
    else:
        lines.append("- Nenhuma")

    lines.extend(
        [
            "",
            "## Flamengo 2020-2025",
            "",
        ]
    )
    if flamengo_rows:
        for row in flamengo_rows:
            lines.append(
                f"- {row.get('season')} | `{row.get('competition_key')}`: sem técnico `{_to_int(row, 'matches_without_assignment')}`, "
                f"conflitos `{_to_int(row, 'matches_with_conflict')}`, "
                f"assistant risk `{_to_int(row, 'assistant_as_head_risk')}`"
            )
    else:
        lines.append("- Flamengo não apareceu no recorte auditado.")

    lines.extend(
        [
            "",
            "## Leitura operacional",
            "",
            "- O dado atual de técnicos ainda é majoritariamente de passagem, não de atribuição por partida.",
            "- A inexistência de uma fonte nativa de coach por súmula/lineup impede fechar a cobertura só com heurística temporal.",
            "- A prioridade prática continua sendo backfill em áreas já públicas, começando por Flamengo 2020-2025 e Série A 2020-2025.",
        ]
    )

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    rows = db_client.fetch_all(sql)
    _write_csv(rows)
    _write_json(rows)
    _write_summary(rows)
    print(f"rows={len(rows)}")
    print(f"csv={CSV_PATH}")
    print(f"json={JSON_PATH}")
    print(f"summary={SUMMARY_PATH}")


if __name__ == "__main__":
    main()
