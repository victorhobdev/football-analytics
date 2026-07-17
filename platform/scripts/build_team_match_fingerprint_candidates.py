"""Build team-identity candidates from repeated match fingerprints.

This is evidence generation only: it never updates a fact table or approves a
team merge. A pair is scored when different source rows contain the same date,
competition, relative score, and a normalized opponent name.
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"
MIN_OPPONENT_SIMILARITY = 0.70
MIN_SHARED_MATCHES = int(os.getenv("TEAM_MATCH_MIN_SHARED", "5"))


def dsn() -> str:
    return os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or DEFAULT_DSN


def normalize_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    replacements = {
        "mg": "mineiro",
        "ath": "atletico",
        "sp": "sporting",
        "fc": "",
        "cf": "",
        "club": "",
        "football": "",
        "futebol": "",
        "s a d": "",
    }
    tokens = [replacements.get(token, token) for token in text.split()]
    return " ".join(token for token in tokens if token)


def opponent_match(left: str, right: str) -> bool:
    a, b = normalize_name(left), normalize_name(right)
    if not a or not b:
        return False
    if a == b or a in b.split() or b in a.split():
        return True
    return SequenceMatcher(None, a, b).ratio() >= MIN_OPPONENT_SIMILARITY


def load_rows(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select fixture_id, home_team_id as team_id, home_team_name as team_name,
               away_team_name as opponent_name, home_goals as goals_for,
               away_goals as goals_against, date_utc::date as match_date,
               competition_key, coalesce(source_provider, provider) as source
        from mart.stg_matches
        where home_team_id is not null
        union all
        select fixture_id, away_team_id, away_team_name, home_team_name,
               away_goals, home_goals, date_utc::date, competition_key,
               coalesce(source_provider, provider)
        from mart.stg_matches
        where away_team_id is not null
        """
    ).fetchall()
    return [dict(row) for row in rows]


def build_edges(rows: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[
            (
                row["match_date"],
                row["competition_key"],
                row["goals_for"],
                row["goals_against"],
            )
        ].append(row)

    edges: dict[tuple[int, int], dict[str, Any]] = {}
    for bucket in buckets.values():
        for index, left in enumerate(bucket):
            for right in bucket[index + 1 :]:
                if left["team_id"] == right["team_id"] or left["source"] == right["source"]:
                    continue
                if not opponent_match(left["opponent_name"], right["opponent_name"]):
                    continue
                pair = tuple(sorted((int(left["team_id"]), int(right["team_id"]))))
                edge = edges.setdefault(pair, {"shared_matches": set(), "examples": []})
                fingerprint = (
                    str(left["match_date"]),
                    left["competition_key"],
                    int(left["goals_for"]),
                    int(left["goals_against"]),
                    normalize_name(left["opponent_name"]),
                )
                edge["shared_matches"].add(fingerprint)
                if len(edge["examples"]) < 3:
                    edge["examples"].append(
                        {
                            "date": str(left["match_date"]),
                            "competition": left["competition_key"],
                            "opponent_a": left["opponent_name"],
                            "opponent_b": right["opponent_name"],
                            "score": f"{left['goals_for']}-{left['goals_against']}",
                            "source_a": left["source"],
                            "source_b": right["source"],
                        }
                    )
    return {pair: edge for pair, edge in edges.items() if len(edge["shared_matches"]) >= MIN_SHARED_MATCHES}


def components(edges: dict[tuple[int, int], dict[str, Any]]) -> list[set[int]]:
    graph: dict[int, set[int]] = defaultdict(set)
    for left, right in edges:
        graph[left].add(right)
        graph[right].add(left)
    result: list[set[int]] = []
    unseen = set(graph)
    while unseen:
        root = unseen.pop()
        component = {root}
        stack = [root]
        while stack:
            node = stack.pop()
            for neighbor in graph[node] & unseen:
                unseen.remove(neighbor)
                component.add(neighbor)
                stack.append(neighbor)
        result.append(component)
    return result


def main() -> None:
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        rows = load_rows(conn)
        names = {
            int(row["team_id"]): row["team_name"]
            for row in conn.execute("select team_id, team_name from mart.dim_team")
        }
    edges = build_edges(rows)
    groups = sorted(components(edges), key=lambda group: (-len(group), min(group)))
    print(
        {
            "team_rows": len(names),
            "match_side_rows": len(rows),
            "candidate_edges": len(edges),
            "candidate_nodes": len({node for group in groups for node in group}),
            "components": len(groups),
            "merged_ids_by_match_evidence": sum(len(group) - 1 for group in groups),
            "unique_if_only_match_evidence": len(names) - sum(len(group) - 1 for group in groups),
            "threshold_shared_matches": MIN_SHARED_MATCHES,
            "threshold_opponent_similarity": MIN_OPPONENT_SIMILARITY,
        }
    )
    for group in groups[:50]:
        print(
            {
                "size": len(group),
                "members": [
                    {"team_id": team_id, "team_name": names.get(team_id)}
                    for team_id in sorted(group)
                ],
            }
        )


if __name__ == "__main__":
    main()
