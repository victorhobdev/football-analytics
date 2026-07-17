"""Materialize the researched team resolution in an isolated shadow schema.

The script never updates raw source tables or active marts.  It persists the
deterministic allocation and manifests so a second run reuses the same IDs.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import analyze_team_identity_uniqueness as analysis  # noqa: E402


DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"
SCHEMA = "shadow_team_identity_20260715"
SHADOW_ID_START = 3_000_000_000_000
BELENENSES_MIXED = 1002633571734
BELENENSES_CLUB = 1025187804228
BELENENSES_SAD = 1030245672235
SPLIT_DATE = "2018-07-01"


def dsn() -> str:
    return os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or DEFAULT_DSN


def canonical_key(legacy_id: int, union: analysis.UnionFind) -> str:
    if legacy_id == BELENENSES_CLUB:
        return "belenenses:club"
    if legacy_id == BELENENSES_SAD:
        return "belenenses:sad"
    if legacy_id == BELENENSES_MIXED:
        raise ValueError("the mixed Belenenses identity requires a contextual key")
    return f"component:{union.find(legacy_id)}"


def metadata(member_ids: list[int], names: dict[int, str], features: dict[int, dict[str, set[str]]]) -> tuple[str, str | None, str, str]:
    observed_names = sorted({names[value] for value in member_ids})
    countries = sorted(set().union(*(features[value]["countries"] for value in member_ids)))
    genders = set().union(*(features[value]["genders"] for value in member_ids))
    types = set().union(*(features[value]["types"] for value in member_ids))
    gender = next(iter(genders)) if len(genders) == 1 else "unknown"
    team_type = "national_team" if types == {"national"} else "club"
    return observed_names[0], countries[0] if countries else None, team_type, gender


def source_rows(conn: psycopg.Connection, names: dict[int, str], union: analysis.UnionFind) -> list[dict[str, object]]:
    """Return provider-native/contextual source keys that resolve to legacy IDs."""
    rows: list[dict[str, object]] = []

    def add(provider: str, source_id: object, legacy_id: int, source_team_key: str, edition_key: str | None = None, valid_from: str | None = None, valid_to: str | None = None) -> None:
        if legacy_id not in names:
            return
        if legacy_id == BELENENSES_MIXED:
            return
        rows.append({
            "provider": provider,
            "source_id": str(source_id),
            "source_team_key": source_team_key,
            "edition_key": edition_key,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "key": canonical_key(legacy_id, union),
            "method": "researched_union_resolution",
            "confidence": "high",
        })

    for legacy_id in sorted(names):
        if legacy_id == BELENENSES_MIXED:
            rows.extend([
                {"provider": "legacy_dim_team", "source_id": str(legacy_id), "source_team_key": f"legacy_dim_team:{legacy_id}:pre_2018", "edition_key": "pre_2018", "valid_from": None, "valid_to": SPLIT_DATE, "key": "belenenses:club", "method": "split_context", "confidence": "high"},
                {"provider": "legacy_dim_team", "source_id": str(legacy_id), "source_team_key": f"legacy_dim_team:{legacy_id}:post_2018", "edition_key": "post_2018", "valid_from": SPLIT_DATE, "valid_to": None, "key": "belenenses:sad", "method": "split_context", "confidence": "high"},
            ])
        else:
            add("legacy_dim_team", legacy_id, legacy_id, f"legacy_dim_team:{legacy_id}")

    fixture_rows = conn.execute(
        """
        select distinct source_provider, team_id
        from (
          select coalesce(source_provider, provider) as source_provider, home_team_id as team_id from raw.fixtures
          union
          select coalesce(source_provider, provider), away_team_id from raw.fixtures
        ) s
        where source_provider is not null and team_id is not null
        """
    ).fetchall()
    for row in fixture_rows:
        provider = str(row["source_provider"])
        team_id = int(row["team_id"])
        add(provider, team_id, team_id, f"{provider}:{team_id}")

    statsbomb_rows = conn.execute(
        """
        select distinct source_team_id
        from (
          select home_team_id as source_team_id from raw.statsbomb_matches
          union
          select away_team_id from raw.statsbomb_matches
        ) s
        where source_team_id is not null
        """
    ).fetchall()
    for row in statsbomb_rows:
        source_team_id = int(row["source_team_id"])
        legacy_id = 910000000000 + source_team_id
        add("statsbomb_open_data", source_team_id, legacy_id, f"statsbomb_open_data:{source_team_id}")

    # Transfermarkt's native club key is retained when its name maps uniquely
    # to a researched legacy identity.  This avoids a wide staging-view join.
    name_to_legacy: dict[str, list[int]] = defaultdict(list)
    for legacy_id, name in names.items():
        name_to_legacy[analysis.normalize_name(name)].append(legacy_id)
    for row in conn.execute("select distinct club_id, name from raw.tm_clubs where club_id is not null and name is not null").fetchall():
        matches = name_to_legacy.get(analysis.normalize_name(str(row["name"])), [])
        if len(matches) == 1:
            add("transfermarkt", row["club_id"], matches[0], f"transfermarkt:club:{row['club_id']}")

    # Elo has no native team ID.  Its stable source key is the competition and
    # observed name; reproduce the existing staging key only to locate the
    # researched legacy identity, never to allocate a canonical ID.
    elo_rows = conn.execute(
        """
        with teams as (
          select ex.competition_key, ex.home_team_name_raw as team_name
          from control.elo_match_xref ex
          union
          select ex.competition_key, ex.away_team_name_raw
          from control.elo_match_xref ex
        )
        select distinct competition_key, team_name,
          960200000000 + (('x' || substr(md5(concat('eloratings:', competition_key, ':', lower(trim(team_name)))), 1, 15))::bit(60)::bigint % 99999999999) as team_id
        from teams
        where competition_key is not null and team_name is not null
        """
    ).fetchall()
    for row in elo_rows:
        legacy_id = int(row["team_id"])
        if legacy_id not in names:
            continue
        period_rows = (("pre_2018", "belenenses:club", None, SPLIT_DATE), ("post_2018", "belenenses:sad", SPLIT_DATE, None)) if legacy_id == BELENENSES_MIXED else (("", canonical_key(legacy_id, union), None, None),)
        for period, key, valid_from, valid_to in period_rows:
            suffix = f":{period}" if period else ""
            rows.append({"provider": "eloratings", "source_id": str(legacy_id), "source_team_key": f"eloratings:{row['competition_key']}:{row['team_name']}{suffix}", "edition_key": str(row["competition_key"]), "valid_from": valid_from, "valid_to": valid_to, "key": key, "method": "split_context" if period else "contextual_source_key", "confidence": "high"})

    for row in conn.execute("select distinct home_team_name as team_name from raw.brasileirao_matches where home_team_name is not null union select distinct away_team_name from raw.brasileirao_matches where away_team_name is not null").fetchall():
        matches = name_to_legacy.get(analysis.normalize_name(str(row["team_name"])), [])
        if len(matches) == 1:
            legacy_id = matches[0]
            if legacy_id != BELENENSES_MIXED:
                rows.append({"provider": "dataset_brasileirao", "source_id": str(legacy_id), "source_team_key": f"dataset_brasileirao:name:{analysis.normalize_name(str(row['team_name']))}", "edition_key": None, "valid_from": None, "valid_to": None, "key": canonical_key(legacy_id, union), "method": "contextual_source_key", "confidence": "high"})

    unique: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        unique[(str(row["provider"]), "team", str(row["source_team_key"]))] = row
    return list(unique.values())


def materialize() -> dict[str, int]:
    # main() is the single resolution implementation; suppress its diagnostic stdout.
    with contextlib.redirect_stdout(io.StringIO()):
        analysis.main()
    result = analysis.RESOLUTION_RESULT
    names = result["names"]
    features = result["features"]
    union = result["union"]
    roots = result["roots"]
    belenenses_roots = result["belenenses_roots"]
    component_members: dict[int, list[int]] = defaultdict(list)
    for legacy_id in names:
        component_members[union.find(legacy_id)].append(legacy_id)
    canonical_members: dict[str, list[int]] = {}
    for root in sorted(roots - belenenses_roots):
        canonical_members[f"component:{root}"] = sorted(component_members[root])
    canonical_members["belenenses:club"] = [BELENENSES_CLUB]
    canonical_members["belenenses:sad"] = [BELENENSES_SAD]
    if len(canonical_members) != 1930:
        raise RuntimeError(f"expected corrected 1930 canonical identities, got {len(canonical_members)}")

    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        conn.execute(f"create schema if not exists {SCHEMA}")
        conn.execute(f"create sequence if not exists {SCHEMA}.canonical_team_id_seq start with {SHADOW_ID_START}")
        conn.execute(f"""
          create table if not exists {SCHEMA}.canonical_team (
            canonical_team_id bigint primary key,
            canonical_key text not null unique,
            team_name text not null,
            country_or_territory text,
            team_type text not null,
            gender text not null,
            category text not null default 'senior',
            identity_state text not null default 'active',
            merged_into_team_id bigint,
            decision_method text not null,
            decision_confidence numeric(5,4),
            decision_evidence jsonb not null default '{{}}'::jsonb,
            check (identity_state = 'active' and merged_into_team_id is null)
          )
        """)
        conn.execute(f"""
          create table if not exists {SCHEMA}.provider_entity_map (
            provider text not null,
            entity_type text not null,
            source_id text not null,
            source_team_key text not null,
            canonical_team_id bigint not null references {SCHEMA}.canonical_team(canonical_team_id),
            edition_key text,
            valid_from date,
            valid_to date,
            mapping_state text not null,
            mapping_confidence text not null,
            resolution_method text not null,
            evidence jsonb not null default '{{}}'::jsonb,
            primary key (provider, entity_type, source_team_key)
          )
        """)
        conn.execute(f"""
          create table if not exists {SCHEMA}.team_manifest (
            source_team_key text primary key,
            retired_team_id bigint,
            survivor_team_id bigint not null,
            classification text not null,
            method text not null,
            confidence text not null,
            evidence jsonb not null,
            affected_relations jsonb not null,
            expected_delta integer not null,
            rollback text not null
          )
        """)
        conn.execute(f"""
          create table if not exists {SCHEMA}.negative_decision (
            source_team_key text primary key,
            left_root bigint not null,
            right_root bigint not null,
            decision text not null,
            method text not null,
            confidence text not null,
            evidence jsonb not null
          )
        """)
        conn.execute(f"""
          create table if not exists {SCHEMA}.dim_team as
          select c.canonical_team_id as team_id,
                 md5(c.canonical_team_id::text) as team_sk,
                 c.team_name, c.country_or_territory, c.team_type, c.gender,
                 c.category, c.identity_state, c.merged_into_team_id
          from {SCHEMA}.canonical_team c
          where false
        """)
        conn.execute(f"""
          create table if not exists {SCHEMA}.fact_matches_rekeyed as
          select f.*, null::bigint as canonical_home_team_id, null::bigint as canonical_away_team_id
          from mart.fact_matches f where false
        """)

        # Rebuild from the current decision set. A component can disappear after
        # a newly approved merge, so retaining old registry rows would leave a
        # publishable canonical identity with no source mapping.
        conn.execute(f"delete from {SCHEMA}.provider_entity_map")
        conn.execute(
            f"delete from {SCHEMA}.canonical_team where not (canonical_key = any(%s))",
            (list(canonical_members),),
        )

        key_to_id: dict[str, int] = {}
        for key, member_ids in sorted(canonical_members.items()):
            team_name, country, team_type, gender = metadata(member_ids, names, features)
            if key == "belenenses:club":
                team_name = "Belenenses"
                country = "Portugal"
                gender = "male"
            elif key == "belenenses:sad":
                team_name = "B SAD"
                country = "Portugal"
                gender = "male"
            existing = conn.execute(f"select canonical_team_id from {SCHEMA}.canonical_team where canonical_key=%s", (key,)).fetchone()
            if existing:
                canonical_id = int(existing["canonical_team_id"])
                conn.execute(
                    f"""update {SCHEMA}.canonical_team
                        set team_name=%s, country_or_territory=%s, team_type=%s,
                            gender=%s, decision_method=%s, decision_confidence=%s,
                            decision_evidence=%s
                        where canonical_team_id=%s""",
                    (team_name, country, team_type, gender, "researched_union_resolution", 0.95,
                     json.dumps({"legacy_members": member_ids, "canonical_key": key}), canonical_id),
                )
            else:
                canonical_id = int(conn.execute(f"select nextval('{SCHEMA}.canonical_team_id_seq') as id").fetchone()["id"])
                conn.execute(f"insert into {SCHEMA}.canonical_team (canonical_team_id,canonical_key,team_name,country_or_territory,team_type,gender,decision_method,decision_confidence,decision_evidence) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (canonical_id, key, team_name, country, team_type, gender, "researched_union_resolution", 0.95, json.dumps({"legacy_members": member_ids, "canonical_key": key})))
            key_to_id[key] = canonical_id

        maps = source_rows(conn, names, union)
        for row in maps:
            conn.execute(f"""
              insert into {SCHEMA}.provider_entity_map
                (provider,entity_type,source_id,source_team_key,canonical_team_id,edition_key,valid_from,valid_to,mapping_state,mapping_confidence,resolution_method,evidence)
              values (%s,'team',%s,%s,%s,%s,%s,%s,'approved',%s,%s,%s)
              on conflict (provider,entity_type,source_team_key) do update set
                source_id=excluded.source_id, canonical_team_id=excluded.canonical_team_id,
                edition_key=excluded.edition_key, valid_from=excluded.valid_from, valid_to=excluded.valid_to,
                mapping_state=excluded.mapping_state, mapping_confidence=excluded.mapping_confidence,
                resolution_method=excluded.resolution_method, evidence=excluded.evidence
            """, (row["provider"], row["source_id"], row["source_team_key"], key_to_id[str(row["key"])], row["edition_key"], row["valid_from"], row["valid_to"], row["confidence"], row["method"], json.dumps({"source_id": row["source_id"], "contextual": row["method"] == "split_context"})))

        conn.execute(f"delete from {SCHEMA}.team_manifest")
        for key, member_ids in sorted(canonical_members.items()):
            classification = "merge" if key.startswith("belenenses:") or len(member_ids) > 1 else "separate"
            for legacy_id in member_ids:
                source_key = f"legacy_dim_team:{legacy_id}"
                conn.execute(f"insert into {SCHEMA}.team_manifest values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (source_team_key) do update set survivor_team_id=excluded.survivor_team_id, classification=excluded.classification, evidence=excluded.evidence", (source_key, legacy_id if classification == "merge" else None, key_to_id[key], classification, "match_and_context_research", "high", json.dumps({"canonical_key": key, "legacy_members": member_ids}), json.dumps({"dim_team": 1, "fact_matches": 0}), -1 if classification == "merge" else 0, "restore shadow schema from backup"))
        for period, key in (("pre_2018", "belenenses:club"), ("post_2018", "belenenses:sad")):
            source_key = f"legacy_dim_team:{BELENENSES_MIXED}:{period}"
            conn.execute(f"insert into {SCHEMA}.team_manifest values (%s,%s,%s,'split_context','legal_history_research','high',%s,%s,0,%s) on conflict (source_team_key) do update set survivor_team_id=excluded.survivor_team_id, evidence=excluded.evidence", (source_key, BELENENSES_MIXED, key_to_id[key], json.dumps({"valid_from": SPLIT_DATE if period == "post_2018" else None, "valid_to": SPLIT_DATE if period == "pre_2018" else None, "canonical_key": key}), json.dumps({"dim_team": 0, "fact_matches": "date-aware"}), "restore shadow schema from backup"))

        conn.execute(f"delete from {SCHEMA}.negative_decision")
        for index, candidate in enumerate(result.get("fuzzy_candidates", []), start=1):
            conn.execute(f"insert into {SCHEMA}.negative_decision values (%s,%s,%s,'separate','reviewed_fuzzy_candidate','high',%s)", (f"fuzzy:{index:03d}", int(candidate["left_root"]), int(candidate["right_root"]), json.dumps(candidate)))

        conn.execute(f"delete from {SCHEMA}.dim_team")
        conn.execute(f"insert into {SCHEMA}.dim_team select canonical_team_id,md5(concat('team:', canonical_team_id::text)),team_name,country_or_territory,team_type,gender,category,identity_state,merged_into_team_id from {SCHEMA}.canonical_team order by canonical_team_id")
        conn.execute(f"truncate {SCHEMA}.fact_matches_rekeyed")
        conn.execute(f"""
          insert into {SCHEMA}.fact_matches_rekeyed
          select f.*, hm.canonical_team_id, am.canonical_team_id
          from mart.fact_matches f
          left join {SCHEMA}.provider_entity_map hm
            on hm.provider='legacy_dim_team' and hm.entity_type='team'
           and hm.source_id=f.home_team_id::text
           and (hm.source_team_key='legacy_dim_team:'||f.home_team_id::text
                or (f.home_team_id={BELENENSES_MIXED} and (hm.valid_from is null or hm.valid_from <= f.date_day) and (hm.valid_to is null or f.date_day < hm.valid_to)))
          left join {SCHEMA}.provider_entity_map am
            on am.provider='legacy_dim_team' and am.entity_type='team'
           and am.source_id=f.away_team_id::text
           and (am.source_team_key='legacy_dim_team:'||f.away_team_id::text
                or (f.away_team_id={BELENENSES_MIXED} and (am.valid_from is null or am.valid_from <= f.date_day) and (am.valid_to is null or f.date_day < am.valid_to)))
        """)
        conn.commit()

        counts = {
            "canonical_count": int(conn.execute(f"select count(*) as n from {SCHEMA}.canonical_team").fetchone()["n"]),
            "crosswalk_count": int(conn.execute(f"select count(*) as n from {SCHEMA}.provider_entity_map").fetchone()["n"]),
            "manifest_count": int(conn.execute(f"select count(*) as n from {SCHEMA}.team_manifest").fetchone()["n"]),
            "negative_count": int(conn.execute(f"select count(*) as n from {SCHEMA}.negative_decision").fetchone()["n"]),
            "fact_count": int(conn.execute(f"select count(*) as n from {SCHEMA}.fact_matches_rekeyed").fetchone()["n"]),
            "unresolved_home": int(conn.execute(f"select count(*) as n from {SCHEMA}.fact_matches_rekeyed where canonical_home_team_id is null").fetchone()["n"]),
            "unresolved_away": int(conn.execute(f"select count(*) as n from {SCHEMA}.fact_matches_rekeyed where canonical_away_team_id is null").fetchone()["n"]),
            "same_side": int(conn.execute(f"select count(*) as n from {SCHEMA}.fact_matches_rekeyed where canonical_home_team_id is not null and canonical_home_team_id=canonical_away_team_id").fetchone()["n"]),
        }

    out = Path("platform/reports/quality")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "team_identity_manifest_20260715.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["source_team_key", "canonical_key", "canonical_team_id", "classification", "legacy_members"])
        for key, member_ids in sorted(canonical_members.items()):
            classification = "merge" if key.startswith("belenenses:") or len(member_ids) > 1 else "separate"
            for legacy_id in member_ids:
                writer.writerow([f"legacy_dim_team:{legacy_id}", key, key_to_id[key], classification, ",".join(map(str, member_ids))])
        writer.writerow([f"legacy_dim_team:{BELENENSES_MIXED}:pre_2018", "belenenses:club", key_to_id["belenenses:club"], "split_context", str(BELENENSES_MIXED)])
        writer.writerow([f"legacy_dim_team:{BELENENSES_MIXED}:post_2018", "belenenses:sad", key_to_id["belenenses:sad"], "split_context", str(BELENENSES_MIXED)])
    with (out / "team_identity_negative_decisions_20260715.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["decision_key", "left_root", "right_root", "decision", "score", "left_name", "right_name", "countries"])
        for index, candidate in enumerate(result.get("fuzzy_candidates", []), start=1):
            writer.writerow([f"fuzzy:{index:03d}", candidate["left_root"], candidate["right_root"], "separate", candidate["score"], candidate["left_name"], candidate["right_name"], ",".join(candidate["countries"])])
    print(json.dumps(counts, sort_keys=True))
    return counts


if __name__ == "__main__":
    materialize()
