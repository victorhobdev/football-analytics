from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2


ROOT_DIR = Path(__file__).resolve().parents[1]
QUALITY_DIR = ROOT_DIR / "quality"
CSV_PATH = QUALITY_DIR / "sportmonks_wikidata_coach_resolution_candidates.csv"
JSON_PATH = QUALITY_DIR / "sportmonks_wikidata_coach_resolution_summary.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_db_dsn() -> str:
    env_dsn = (os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or "").strip()
    if env_dsn:
        return env_dsn.replace("postgresql+psycopg2://", "postgresql://")
    return "postgresql://football:football@127.0.0.1:5432/football_dw"


def normalize(text: str | None) -> str:
    raw = (text or "").strip().lower()
    if not raw:
        return ""
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


@dataclass
class SportCoach:
    coach_identity_id: int
    provider_coach_id: int
    coach_name: str
    norm_name: str
    aliases: list[str]
    teams: set[int]


@dataclass
class WikiCoach:
    coach_identity_id: int
    provider_coach_id: int
    coach_name: str
    norm_name: str
    aliases: list[str]
    teams: set[int]


def fetch_sport_coaches(conn: Any) -> list[SportCoach]:
    query = """
        with base as (
            select
                ci.coach_identity_id,
                ci.provider_coach_id,
                coalesce(nullif(trim(ci.display_name), ''), nullif(trim(ci.canonical_name), ''), concat('Coach ', ci.coach_identity_id::text)) as coach_name,
                ci.aliases,
                array_remove(array_agg(distinct f.team_id), null) as team_ids
            from mart.coach_identity ci
            left join mart.fact_coach_match_assignment f
              on f.coach_identity_id = ci.coach_identity_id
            where ci.provider = 'sportmonks'
              and ci.image_url ilike '%placeholder%'
            group by ci.coach_identity_id, ci.provider_coach_id, coach_name, ci.aliases
        )
        select coach_identity_id, provider_coach_id, coach_name, aliases, team_ids
        from base
        order by coach_identity_id
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    coaches: list[SportCoach] = []
    for coach_identity_id, provider_coach_id, coach_name, aliases, team_ids in rows:
        alias_names = []
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    alias_names.append(alias)
                elif isinstance(alias, dict):
                    name = alias.get("name")
                    if isinstance(name, str) and name.strip():
                        alias_names.append(name)
        teams = {int(team_id) for team_id in (team_ids or []) if team_id is not None}
        coaches.append(
            SportCoach(
                coach_identity_id=int(coach_identity_id),
                provider_coach_id=int(provider_coach_id),
                coach_name=str(coach_name),
                norm_name=normalize(str(coach_name)),
                aliases=alias_names,
                teams=teams,
            )
        )
    return coaches


def fetch_wiki_coaches(conn: Any) -> list[WikiCoach]:
    query = """
        with base as (
            select
                ci.coach_identity_id,
                ci.provider_coach_id,
                coalesce(nullif(trim(ci.display_name), ''), nullif(trim(ci.canonical_name), ''), concat('Coach ', ci.coach_identity_id::text)) as coach_name,
                ci.aliases,
                array_remove(array_agg(distinct f.team_id), null) as team_ids
            from mart.coach_identity ci
            left join mart.fact_coach_match_assignment f
              on f.coach_identity_id = ci.coach_identity_id
            where ci.provider = 'wikidata'
            group by ci.coach_identity_id, ci.provider_coach_id, coach_name, ci.aliases
        )
        select coach_identity_id, provider_coach_id, coach_name, aliases, team_ids
        from base
        order by coach_identity_id
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    coaches: list[WikiCoach] = []
    for coach_identity_id, provider_coach_id, coach_name, aliases, team_ids in rows:
        alias_names = []
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    alias_names.append(alias)
                elif isinstance(alias, dict):
                    name = alias.get("name")
                    if isinstance(name, str) and name.strip():
                        alias_names.append(name)
        teams = {int(team_id) for team_id in (team_ids or []) if team_id is not None}
        coaches.append(
            WikiCoach(
                coach_identity_id=int(coach_identity_id),
                provider_coach_id=int(provider_coach_id),
                coach_name=str(coach_name),
                norm_name=normalize(str(coach_name)),
                aliases=alias_names,
                teams=teams,
            )
        )
    return coaches


def build_name_index(wiki_coaches: list[WikiCoach]) -> dict[str, list[WikiCoach]]:
    index: dict[str, list[WikiCoach]] = defaultdict(list)
    for coach in wiki_coaches:
        names = {coach.norm_name}
        names.update(normalize(alias) for alias in coach.aliases if normalize(alias))
        for name in names:
            index[name].append(coach)
    return index


def score_candidate(sport: SportCoach, wiki: WikiCoach) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    if sport.norm_name and sport.norm_name == wiki.norm_name:
        score += 0.62
        reasons.append("exact_primary_name")

    sport_aliases = {normalize(alias) for alias in sport.aliases if normalize(alias)}
    wiki_aliases = {normalize(alias) for alias in wiki.aliases if normalize(alias)}
    if sport.norm_name in wiki_aliases or wiki.norm_name in sport_aliases:
        score += 0.24
        reasons.append("primary_alias_cross_match")

    alias_overlap = sorted((sport_aliases | {sport.norm_name}) & (wiki_aliases | {wiki.norm_name}))
    if alias_overlap:
        score += 0.08
        reasons.append("alias_overlap")

    shared_teams = sport.teams & wiki.teams
    if shared_teams:
        shared_cap = min(len(shared_teams), 3)
        score += 0.08 + 0.04 * (shared_cap - 1)
        reasons.append(f"shared_team_count_{len(shared_teams)}")

    if sport.norm_name and wiki.norm_name and sport.norm_name == wiki.norm_name and len(shared_teams) >= 1:
        score += 0.06
        reasons.append("exact_name_plus_team")

    return min(score, 1.0), reasons


def classify_candidates(sport_coaches: list[SportCoach], wiki_coaches: list[WikiCoach]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    name_index = build_name_index(wiki_coaches)
    rows: list[dict[str, Any]] = []
    resolution_counter: Counter[str] = Counter()

    for sport in sport_coaches:
        candidate_pool: dict[int, WikiCoach] = {}
        lookup_names = {sport.norm_name}
        lookup_names.update(normalize(alias) for alias in sport.aliases if normalize(alias))
        for lookup_name in lookup_names:
            for wiki in name_index.get(lookup_name, []):
                candidate_pool[wiki.coach_identity_id] = wiki

        scored: list[tuple[float, WikiCoach, list[str]]] = []
        for wiki in candidate_pool.values():
            score, reasons = score_candidate(sport, wiki)
            if score <= 0:
                continue
            scored.append((score, wiki, reasons))

        scored.sort(key=lambda item: (-item[0], item[1].coach_identity_id))
        if not scored:
            resolution_counter["no_candidate"] += 1
            continue

        top_score, top_wiki, top_reasons = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        score_gap = round(top_score - second_score, 4)
        shared_teams = sorted(sport.teams & top_wiki.teams)

        if top_score >= 0.92 and score_gap >= 0.12:
            classification = "promotable_strong"
        elif top_score >= 0.86 and score_gap >= 0.18 and shared_teams:
            classification = "promotable_with_team_overlap"
        elif top_score >= 0.78:
            classification = "review_needed"
        else:
            classification = "weak_candidate"

        resolution_counter[classification] += 1
        rows.append(
            {
                "sport_coach_identity_id": sport.coach_identity_id,
                "sportmonks_coach_id": sport.provider_coach_id,
                "sport_coach_name": sport.coach_name,
                "sport_aliases": json.dumps(sport.aliases, ensure_ascii=False),
                "sport_team_count": len(sport.teams),
                "wikidata_coach_identity_id": top_wiki.coach_identity_id,
                "wikidata_id": f"Q{top_wiki.provider_coach_id}",
                "wikidata_coach_name": top_wiki.coach_name,
                "wikidata_aliases": json.dumps(top_wiki.aliases, ensure_ascii=False),
                "wikidata_team_count": len(top_wiki.teams),
                "shared_team_count": len(shared_teams),
                "shared_team_ids": ",".join(str(team_id) for team_id in shared_teams[:10]),
                "score": round(top_score, 4),
                "second_score": round(second_score, 4),
                "score_gap": score_gap,
                "classification": classification,
                "reasons": "|".join(top_reasons),
            }
        )

    summary = {
        "generated_at": utc_now_iso(),
        "sport_placeholder_total": len(sport_coaches),
        "wikidata_total": len(wiki_coaches),
        "candidate_rows": len(rows),
        "classification_counts": dict(resolution_counter),
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sport_coach_identity_id",
                "sportmonks_coach_id",
                "sport_coach_name",
                "sport_aliases",
                "sport_team_count",
                "wikidata_coach_identity_id",
                "wikidata_id",
                "wikidata_coach_name",
                "wikidata_aliases",
                "wikidata_team_count",
                "shared_team_count",
                "shared_team_ids",
                "score",
                "second_score",
                "score_gap",
                "classification",
                "reasons",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    conn = psycopg2.connect(resolve_db_dsn())
    try:
        sport_coaches = fetch_sport_coaches(conn)
        wiki_coaches = fetch_wiki_coaches(conn)
        rows, summary = classify_candidates(sport_coaches, wiki_coaches)
        write_outputs(rows, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
