from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from _repo_root import resolve_repo_root
from typing import Any

ROOT = resolve_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.src.core.config import get_settings
from api.src.db.client import db_client

SUMMARY_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_sources_summary.json"
REPORT_PATH = ROOT / "platform" / "reports" / "quality" / "external_coach_novelty_report.md"
HIGH_VALUE_CSV = ROOT / "platform" / "reports" / "quality" / "external_coach_high_novelty_candidates.csv"
DUPLICATE_CSV = ROOT / "platform" / "reports" / "quality" / "external_coach_likely_duplicates.csv"
UNRESOLVED_CSV = ROOT / "platform" / "reports" / "quality" / "external_coach_unresolved_team_candidates.csv"
SUMMARY_JSON = ROOT / "platform" / "reports" / "quality" / "external_coach_novelty_summary.json"


@dataclass(frozen=True)
class LocalTeam:
    team_id: int
    team_name: str
    norm: str
    tokens: frozenset[str]


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower().strip()
    return re.sub(r"\s+", " ", text)


def _tokens(value: str) -> frozenset[str]:
    stop = {
        "club",
        "clube",
        "de",
        "da",
        "do",
        "dos",
        "das",
        "football",
        "futebol",
        "futbol",
        "fc",
        "cf",
        "ac",
        "sc",
        "ec",
        "afc",
        "association",
        "associacao",
        "regatas",
        "sociedade",
        "esporte",
        "sport",
        "sports",
        "team",
        "national",
        "selection",
        "selecao",
    }
    return frozenset(token for token in value.split() if token not in stop and len(token) > 2)


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _load_external_facts_path() -> Path:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    base_dir = Path(summary["base_dir"])
    return base_dir / "normalized" / "external_coach_facts.jsonl"


def _load_local_teams() -> list[LocalTeam]:
    rows = db_client.fetch_all("select team_id, team_name from mart.dim_team where team_name is not null")
    return [
        LocalTeam(
            team_id=int(row["team_id"]),
            team_name=str(row["team_name"]),
            norm=_normalize(str(row["team_name"])),
            tokens=_tokens(_normalize(str(row["team_name"]))),
        )
        for row in rows
    ]


def _resolve_team(team_name: str | None, local_teams: list[LocalTeam]) -> tuple[LocalTeam | None, str, float]:
    norm = _normalize(team_name)
    if not norm:
        return None, "missing_team_name", 0.0

    exact = [team for team in local_teams if team.norm == norm]
    if len(exact) == 1:
        return exact[0], "exact_name", 1.0

    contains = [
        team
        for team in local_teams
        if len(team.norm) >= 5 and (f" {team.norm} " in f" {norm} " or f" {norm} " in f" {team.norm} ")
    ]
    if len(contains) == 1:
        return contains[0], "contains_unique", 0.9

    ext_tokens = _tokens(norm)
    scored: list[tuple[float, LocalTeam]] = []
    for team in local_teams:
        if not ext_tokens or not team.tokens:
            continue
        overlap = len(ext_tokens & team.tokens)
        if overlap == 0:
            continue
        token_score = overlap / max(len(ext_tokens), len(team.tokens))
        name_score = _similarity(norm, team.norm)
        score = max(token_score, name_score)
        if score >= 0.78:
            scored.append((score, team))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
        return scored[0][1], "token_fuzzy_unique", round(scored[0][0], 3)

    return None, "unresolved_or_ambiguous", 0.0


def _load_match_teams() -> dict[int, list[dict[str, Any]]]:
    rows = db_client.fetch_all(
        """
        select match_id, competition_key, season, date_day, home_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        union all
        select match_id, competition_key, season, date_day, away_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        """,
        [get_settings().product_data_cutoff, get_settings().product_data_cutoff],
    )
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        row["date_day"] = date.fromisoformat(str(row["date_day"]))
        grouped[int(row["team_id"])].append(row)
    return grouped


def _load_assignments() -> tuple[set[tuple[int, int]], dict[int, list[dict[str, Any]]]]:
    rows = db_client.fetch_all(
        """
        select
          fcma.match_id,
          fcma.team_id,
          fcma.is_public_eligible,
          fm.date_day,
          coalesce(ci.display_name, ci.canonical_name) as coach_name
        from mart.fact_coach_match_assignment fcma
        left join mart.fact_matches fm
          on fm.match_id = fcma.match_id
        left join mart.coach_identity ci
          on ci.coach_identity_id = fcma.coach_identity_id
        where fcma.is_public_eligible
        """
    )
    assigned_keys: set[tuple[int, int]] = set()
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("match_id") is None or row.get("team_id") is None:
            continue
        team_id = int(row["team_id"])
        assigned_keys.add((int(row["match_id"]), team_id))
        if row.get("date_day"):
            by_team[team_id].append(
                {
                    "date_day": date.fromisoformat(str(row["date_day"])),
                    "coach_name": row.get("coach_name"),
                    "coach_norm": _normalize(row.get("coach_name")),
                }
            )
    return assigned_keys, by_team


def _source_weight(source: str) -> float:
    if source.startswith("wikidata_P286"):
        return 0.95
    if source.startswith("wikidata_P6087"):
        return 0.88
    if source.startswith("mediawiki_infobox"):
        return 0.62
    if source.startswith("dbpedia"):
        return 0.38
    return 0.25


def _classify_fact(
    fact: dict[str, Any],
    local_teams: list[LocalTeam],
    match_teams: dict[int, list[dict[str, Any]]],
    assigned_keys: set[tuple[int, int]],
    assignments_by_team: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    team, team_match_method, team_match_score = _resolve_team(fact.get("team_name"), local_teams)
    start = _date(fact.get("start_date"))
    end = _date(fact.get("end_date")) or get_settings().product_data_cutoff
    source = str(fact.get("source") or "")
    source_weight = _source_weight(source)
    coach_norm = _normalize(fact.get("coach_name"))

    base = {
        "source": source,
        "source_record_id": fact.get("source_record_id"),
        "source_url": fact.get("source_url"),
        "coach_name": fact.get("coach_name"),
        "team_name": fact.get("team_name"),
        "start_date": fact.get("start_date"),
        "end_date": fact.get("end_date"),
        "external_confidence": fact.get("confidence"),
        "team_id": team.team_id if team else None,
        "local_team_name": team.team_name if team else None,
        "team_match_method": team_match_method,
        "team_match_score": team_match_score,
        "canonical_missing_matches_covered": 0,
        "canonical_assigned_matches_covered": 0,
        "same_coach_overlap_matches": 0,
        "best_existing_coach_similarity": 0.0,
        "novelty_score": 0.0,
        "classification": "unresolved_team",
        "reason": "",
    }

    if not team:
        base["reason"] = "time externo nao resolveu para dim_team de forma unica"
        base["novelty_score"] = round(0.15 * source_weight, 3)
        return base
    if not start:
        base["classification"] = "auxiliary_undated"
        base["reason"] = "sem data inicial; util como evidencia auxiliar, nao como cobertura de partidas"
        base["novelty_score"] = round(0.18 * source_weight * team_match_score, 3)
        return base
    if start > end:
        base["classification"] = "invalid_interval"
        base["reason"] = "intervalo externo invertido"
        base["novelty_score"] = 0.0
        return base

    local_matches = [
        match
        for match in match_teams.get(team.team_id, [])
        if start <= match["date_day"] <= end
    ]
    missing = [
        match for match in local_matches if (int(match["match_id"]), team.team_id) not in assigned_keys
    ]
    assigned = [
        match for match in local_matches if (int(match["match_id"]), team.team_id) in assigned_keys
    ]
    base["canonical_missing_matches_covered"] = len(missing)
    base["canonical_assigned_matches_covered"] = len(assigned)

    same_coach = 0
    best_similarity = 0.0
    for assignment in assignments_by_team.get(team.team_id, []):
        if not (start <= assignment["date_day"] <= end):
            continue
        sim = _similarity(coach_norm, assignment["coach_norm"])
        best_similarity = max(best_similarity, sim)
        if sim >= 0.86:
            same_coach += 1
    base["same_coach_overlap_matches"] = same_coach
    base["best_existing_coach_similarity"] = round(best_similarity, 3)

    coverage_signal = min(len(missing) / 20, 1.0)
    no_duplicate_signal = 1.0 if same_coach == 0 else max(0.0, 1.0 - (same_coach / max(len(local_matches), 1)))
    date_signal = 1.0 if fact.get("end_date") else 0.75
    score = source_weight * team_match_score * (0.55 * coverage_signal + 0.3 * no_duplicate_signal + 0.15 * date_signal)
    base["novelty_score"] = round(score, 3)

    if len(missing) > 0 and same_coach == 0 and score >= 0.55:
        base["classification"] = "high_novelty_candidate"
        base["reason"] = "cobre partidas sem tecnico canonico e nao parece duplicar coach ja atribuido"
    elif len(missing) > 0:
        base["classification"] = "possible_gap_evidence"
        base["reason"] = "cobre lacuna canonica, mas pode ter duplicacao parcial ou baixa confianca"
    elif same_coach > 0 or best_similarity >= 0.86:
        base["classification"] = "likely_duplicate"
        base["reason"] = "sobrepoe periodo ja coberto por coach canonico parecido"
    else:
        base["classification"] = "low_value_context"
        base["reason"] = "time resolvido, mas nao cobre lacuna atual de partidas"
    return base


def _read_facts(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "classification",
        "novelty_score",
        "source",
        "coach_name",
        "team_name",
        "team_id",
        "local_team_name",
        "start_date",
        "end_date",
        "canonical_missing_matches_covered",
        "canonical_assigned_matches_covered",
        "same_coach_overlap_matches",
        "best_existing_coach_similarity",
        "team_match_method",
        "team_match_score",
        "external_confidence",
        "reason",
        "source_url",
        "source_record_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    facts_path = _load_external_facts_path()
    facts = _read_facts(facts_path)
    local_teams = _load_local_teams()
    match_teams = _load_match_teams()
    assigned_keys, assignments_by_team = _load_assignments()

    classified = [
        _classify_fact(fact, local_teams, match_teams, assigned_keys, assignments_by_team)
        for fact in facts
    ]
    classified.sort(
        key=lambda row: (
            row["classification"] != "high_novelty_candidate",
            -float(row["novelty_score"]),
            -int(row["canonical_missing_matches_covered"]),
            str(row.get("team_name") or ""),
            str(row.get("coach_name") or ""),
        )
    )

    high = [row for row in classified if row["classification"] == "high_novelty_candidate"]
    duplicates = [row for row in classified if row["classification"] == "likely_duplicate"]
    unresolved = [row for row in classified if row["classification"] == "unresolved_team"]

    _write_csv(HIGH_VALUE_CSV, high)
    _write_csv(DUPLICATE_CSV, duplicates[:50000])
    _write_csv(UNRESOLVED_CSV, unresolved[:50000])

    summary = {
        "facts_analyzed": len(classified),
        "classification_counts": dict(Counter(row["classification"] for row in classified)),
        "high_novelty_candidates": len(high),
        "likely_duplicates": len(duplicates),
        "unresolved_team_candidates": len(unresolved),
        "high_novelty_missing_matches_sum": sum(int(row["canonical_missing_matches_covered"]) for row in high),
        "top_high_novelty": high[:50],
        "top_duplicate": duplicates[:20],
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, high, duplicates)
    print(json.dumps(summary, ensure_ascii=True))


def _write_report(summary: dict[str, Any], high: list[dict[str, Any]], duplicates: list[dict[str, Any]]) -> None:
    by_source = Counter(row["source"] for row in high)
    by_team = Counter(row["local_team_name"] for row in high)
    flamengo_high = [
        row
        for row in high
        if row.get("team_id") == 1024 or "flamengo" in _normalize(row.get("team_name"))
    ][:40]

    lines = [
        "# External coach novelty analysis",
        "",
        "## Objetivo",
        "",
        "Separar o que parece ser dado novo aproveitavel do que tende a ser duplicacao ou evidencia auxiliar.",
        "",
        "## Criterio de novidade",
        "",
        "- Time externo resolve para `mart.dim_team`.",
        "- Fato tem intervalo datado.",
        "- Intervalo cobre partidas publicas sem tecnico em `mart.fact_coach_match_assignment`.",
        "- Nao ha tecnico canonico com nome parecido no mesmo time/janela.",
        "- Fonte tem peso maior quando vem de Wikidata com statement datado.",
        "",
        "## Resumo",
        "",
        f"- Fatos analisados: `{summary['facts_analyzed']}`",
        f"- Alta chance de novidade: `{summary['high_novelty_candidates']}`",
        f"- Provaveis duplicacoes: `{summary['likely_duplicates']}`",
        f"- Time nao resolvido/ambiguo: `{summary['unresolved_team_candidates']}`",
        f"- Soma bruta de partidas potencialmente cobertas por candidatos novos: `{summary['high_novelty_missing_matches_sum']}`",
        "",
        "## Distribuicao dos candidatos novos por fonte",
        "",
    ]
    for source, count in by_source.most_common(20):
        lines.append(f"- `{source}`: `{count}`")

    lines.extend(["", "## Times com mais candidatos novos", ""])
    for team, count in by_team.most_common(25):
        lines.append(f"- `{team}`: `{count}`")

    lines.extend(["", "## Top candidatos com maior chance de novidade", ""])
    for row in high[:40]:
        lines.append(
            f"- score `{row['novelty_score']}` | `{row['source']}` | {row.get('local_team_name')} | "
            f"{row.get('coach_name')} | {row.get('start_date') or '?'} ate {row.get('end_date') or '?'} | "
            f"lacuna `{row['canonical_missing_matches_covered']}` jogos | {row.get('source_url') or ''}"
        )

    lines.extend(["", "## Flamengo: candidatos mais relevantes", ""])
    if flamengo_high:
        for row in flamengo_high:
            lines.append(
                f"- score `{row['novelty_score']}` | `{row['source']}` | {row.get('coach_name')} | "
                f"{row.get('start_date') or '?'} ate {row.get('end_date') or '?'} | "
                f"lacuna `{row['canonical_missing_matches_covered']}` jogos | sim existente `{row['best_existing_coach_similarity']}`"
            )
    else:
        lines.append("- Nenhum candidato Flamengo ficou no corte de alta novidade; ver CSV especifico de Flamengo para triagem manual.")

    lines.extend(["", "## Provaveis duplicacoes", ""])
    for row in duplicates[:20]:
        lines.append(
            f"- `{row['source']}` | {row.get('local_team_name')} | {row.get('coach_name')} | "
            f"{row.get('start_date') or '?'} ate {row.get('end_date') or '?'} | "
            f"similaridade `{row['best_existing_coach_similarity']}` | overlaps `{row['same_coach_overlap_matches']}`"
        )

    lines.extend(
        [
            "",
            "## Arquivos gerados",
            "",
            f"- Alta novidade: `{HIGH_VALUE_CSV}`",
            f"- Duplicacao provavel: `{DUPLICATE_CSV}`",
            f"- Time nao resolvido: `{UNRESOLVED_CSV}`",
            f"- Resumo JSON: `{SUMMARY_JSON}`",
            "",
            "## Leitura",
            "",
            "- O melhor material para acoplamento automatico vem de Wikidata datado.",
            "- DBpedia tem volume alto, mas grande parte e sem data: boa para ampliar nomes/passagens, fraca para atribuir partidas.",
            "- MediaWiki raw deve ser usado como evidencia textual, nao como fonte direta.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
