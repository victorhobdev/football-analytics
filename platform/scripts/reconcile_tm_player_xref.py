from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from _repo_root import resolve_repo_root


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_DSN = "postgresql://football:football@127.0.0.1:5432/football_dw"

STOPWORDS = {
    "a",
    "club",
    "clube",
    "da",
    "de",
    "do",
    "dos",
    "fc",
    "football",
    "futebol",
    "junior",
    "jr",
}


@dataclass(frozen=True)
class LocalLineupRow:
    match_id: int
    team_id: int
    player_id: int
    player_name: str
    normalized_name: str
    jersey_number: int | None
    is_starter: bool | None


@dataclass(frozen=True)
class TmLineupRow:
    tm_player_id: str
    tm_game_id: str
    local_match_id: int
    local_team_id: int
    player_name: str
    normalized_name: str
    jersey_number: int | None
    lineup_type: str | None
    date_of_birth_raw: str | None


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_dsn(env_values: dict[str, str]) -> str:
    dsn = os.getenv("FOOTBALL_PG_DSN") or os.getenv("DATABASE_URL") or env_values.get("DATABASE_URL") or DEFAULT_DSN
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg2://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    if "@postgres:" in dsn:
        dsn = dsn.replace("@postgres:", "@127.0.0.1:")
    if "@postgres/" in dsn:
        dsn = dsn.replace("@postgres/", "@127.0.0.1/")
    return dsn


def repair_text(value: str | None) -> str:
    text = (value or "").strip()
    if text == "":
        return ""
    if "Ã" in text or "Â" in text or "�" in text:
        try:
            return text.encode("latin1", "ignore").decode("utf-8", "ignore").strip()
        except UnicodeError:
            return text
    return text


def normalize_name(value: str | None) -> str:
    text = repair_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = text.replace("-", " ").replace(".", " ").replace("'", " ").replace("’", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [token for token in re.sub(r"\s+", " ", text).strip().split(" ") if token and token not in STOPWORDS]
    return " ".join(tokens)


def name_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    token_score = overlap / min(len(left_tokens), len(right_tokens))
    ordered_bonus = 0.04 if left.split()[:1] == right.split()[:1] else 0.0
    return min(1.0, token_score + ordered_bonus)


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def load_local_lineups(conn: psycopg.Connection[Any]) -> dict[tuple[int, int], list[LocalLineupRow]]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              fl.match_id,
              fl.team_id,
              fl.player_id,
              coalesce(fl.player_name, dp.player_name) as player_name,
              fl.jersey_number,
              fl.is_starter
            from mart.fact_fixture_lineups fl
            left join mart.dim_player dp
              on dp.player_id = fl.player_id
            where fl.player_id is not null
              and fl.team_id is not null;
            """
        )
        rows = cursor.fetchall()

    payload: dict[tuple[int, int], list[LocalLineupRow]] = defaultdict(list)
    for row in rows:
        player_name = repair_text(row["player_name"])
        payload[(int(row["match_id"]), int(row["team_id"]))].append(
            LocalLineupRow(
                match_id=int(row["match_id"]),
                team_id=int(row["team_id"]),
                player_id=int(row["player_id"]),
                player_name=player_name,
                normalized_name=normalize_name(player_name),
                jersey_number=parse_int(row["jersey_number"]),
                is_starter=row["is_starter"],
            )
        )
    return payload


def load_tm_club_name_map(conn: psycopg.Connection[Any]) -> dict[tuple[str, str], str]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select club_id, domestic_competition_id, name
            from raw.tm_clubs
            where club_id is not null
              and domestic_competition_id is not null
              and name is not null;
            """
        )
        rows = cursor.fetchall()

    payload: dict[tuple[str, str], str] = {}
    for row in rows:
        competition_code = str(row["domestic_competition_id"]).strip()
        normalized_name = normalize_name(row["name"])
        if competition_code and normalized_name:
            payload[(competition_code, normalized_name)] = str(row["club_id"]).strip()
    return payload


def load_linked_tm_match_map(conn: psycopg.Connection[Any], tm_club_name_map: dict[tuple[str, str], str]) -> dict[str, dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              x.tm_game_id,
              x.local_fixture_id,
              rf.competition_key,
              competition_map.provider_league_code as tm_competition_code,
              rf.home_team_id,
              rf.home_team_name,
              rf.away_team_id,
              rf.away_team_name
            from control.tm_game_fixture_xref x
            inner join raw.fixtures rf
              on rf.fixture_id = x.local_fixture_id
            left join control.competition_provider_map competition_map
              on competition_map.provider = 'transfermarkt'
             and competition_map.competition_key = rf.competition_key
            where x.identity_status = 'linked_to_sportmonks'
              and x.local_fixture_id is not null
              and competition_map.provider_league_code is not null;
            """
        )
        rows = cursor.fetchall()

    payload: dict[str, dict[str, Any]] = {}
    for row in rows:
        competition_code = str(row["tm_competition_code"]).strip()
        home_club_id = tm_club_name_map.get((competition_code, normalize_name(row["home_team_name"])))
        away_club_id = tm_club_name_map.get((competition_code, normalize_name(row["away_team_name"])))
        if home_club_id is None or away_club_id is None:
            continue
        payload[str(row["tm_game_id"])] = {
            "local_match_id": int(row["local_fixture_id"]),
            "home_team_id": int(row["home_team_id"]),
            "away_team_id": int(row["away_team_id"]),
            "home_tm_club_id": home_club_id,
            "away_tm_club_id": away_club_id,
        }
    return payload


def load_tm_lineups(conn: psycopg.Connection[Any], linked_tm_match_map: dict[str, dict[str, Any]]) -> list[TmLineupRow]:
    if not linked_tm_match_map:
        return []

    with conn.cursor() as cursor:
        cursor.execute(
            """
            select
              l.player_id as tm_player_id,
              l.game_id::text as tm_game_id,
              l.club_id,
              l.player_name,
              l.shirt_number,
              l.lineup_type,
              p.date_of_birth_raw
            from raw.tm_game_lineups l
            left join raw.tm_players p
              on p.player_id = l.player_id
            where l.game_id::text = any(%s);
            """,
            [sorted(linked_tm_match_map.keys())],
        )
        rows = cursor.fetchall()

    payload: list[TmLineupRow] = []
    for row in rows:
        tm_game_id = str(row["tm_game_id"])
        match_map = linked_tm_match_map.get(tm_game_id)
        if match_map is None:
            continue
        club_id = str(row["club_id"]).strip() if row["club_id"] is not None else None
        if club_id == match_map["home_tm_club_id"]:
            local_team_id = int(match_map["home_team_id"])
        elif club_id == match_map["away_tm_club_id"]:
            local_team_id = int(match_map["away_team_id"])
        else:
            continue

        player_name = repair_text(row["player_name"])
        payload.append(
            TmLineupRow(
                tm_player_id=str(row["tm_player_id"]),
                tm_game_id=tm_game_id,
                local_match_id=int(match_map["local_match_id"]),
                local_team_id=local_team_id,
                player_name=player_name,
                normalized_name=normalize_name(player_name),
                jersey_number=parse_int(row["shirt_number"]),
                lineup_type=str(row["lineup_type"]).strip() if row["lineup_type"] is not None else None,
                date_of_birth_raw=str(row["date_of_birth_raw"]).strip() if row["date_of_birth_raw"] is not None else None,
            )
        )
    return payload


def candidate_score(tm_row: TmLineupRow, local_row: LocalLineupRow) -> tuple[float, dict[str, Any]]:
    similarity = name_similarity(tm_row.normalized_name, local_row.normalized_name)
    jersey_exact = (
        tm_row.jersey_number is not None
        and local_row.jersey_number is not None
        and tm_row.jersey_number == local_row.jersey_number
    )
    starter_alignment = None
    if tm_row.lineup_type is not None and local_row.is_starter is not None:
        starter_alignment = (
            (tm_row.lineup_type == "starting_lineup" and bool(local_row.is_starter))
            or (tm_row.lineup_type != "starting_lineup" and not bool(local_row.is_starter))
        )

    score = similarity * 80.0
    if jersey_exact:
        score += 20.0
    if starter_alignment is True:
        score += 4.0
    elif starter_alignment is False:
        score -= 4.0

    evidence = {
        "tmGameId": tm_row.tm_game_id,
        "localMatchId": tm_row.local_match_id,
        "localTeamId": tm_row.local_team_id,
        "tmPlayerName": tm_row.player_name,
        "localPlayerId": local_row.player_id,
        "localPlayerName": local_row.player_name,
        "nameSimilarity": round(similarity, 4),
        "jerseyExact": jersey_exact,
        "tmJerseyNumber": tm_row.jersey_number,
        "localJerseyNumber": local_row.jersey_number,
        "starterAlignment": starter_alignment,
        "score": round(score, 4),
    }
    return score, evidence


def reconcile_rows(
    tm_rows: list[TmLineupRow],
    local_lineups: dict[tuple[int, int], list[LocalLineupRow]],
) -> dict[str, dict[str, Any]]:
    votes_by_tm_player: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    sample_row_by_tm_player: dict[str, TmLineupRow] = {}
    ambiguous_events_by_tm_player: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for tm_row in tm_rows:
        sample_row_by_tm_player.setdefault(tm_row.tm_player_id, tm_row)
        candidates = local_lineups.get((tm_row.local_match_id, tm_row.local_team_id), [])
        scored: list[tuple[float, LocalLineupRow, dict[str, Any]]] = []
        for local_row in candidates:
            score, evidence = candidate_score(tm_row, local_row)
            if score >= 70.0:
                scored.append((score, local_row, evidence))
        if not scored:
            ambiguous_events_by_tm_player[tm_row.tm_player_id].append(
                {
                    "tmGameId": tm_row.tm_game_id,
                    "reason": "no_local_candidate_above_threshold",
                    "tmPlayerName": tm_row.player_name,
                    "localMatchId": tm_row.local_match_id,
                    "localTeamId": tm_row.local_team_id,
                }
            )
            continue

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_local, best_evidence = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else None
        if second_score is not None and (best_score - second_score) < 8.0:
            best_evidence["secondBestScore"] = round(second_score, 4)
            ambiguous_events_by_tm_player[tm_row.tm_player_id].append(
                {"reason": "multiple_candidates_close_score", **best_evidence}
            )
            continue

        votes_by_tm_player[tm_row.tm_player_id][best_local.player_id].append(best_evidence)

    results: dict[str, dict[str, Any]] = {}
    for tm_player_id, tm_row in sample_row_by_tm_player.items():
        player_votes = votes_by_tm_player.get(tm_player_id, {})
        if not player_votes:
            results[tm_player_id] = {
                "local_player_id": None,
                "identity_status": "unmatched",
                "confidence": None,
                "match_method": "no_strong_match_in_linked_games",
                "review_status": "pending",
                "player_name_raw": tm_row.player_name,
                "date_of_birth_raw": tm_row.date_of_birth_raw,
                "source_evidence": {"ambiguousEvents": ambiguous_events_by_tm_player.get(tm_player_id, [])[:10]},
            }
            continue

        ranked_votes = sorted(
            (
                (
                    player_id,
                    len(evidences),
                    max(float(evidence["score"]) for evidence in evidences),
                    evidences,
                )
                for player_id, evidences in player_votes.items()
            ),
            key=lambda item: (item[1], item[2]),
            reverse=True,
        )
        best_player_id, vote_count, best_score, best_evidences = ranked_votes[0]
        second_vote_count = ranked_votes[1][1] if len(ranked_votes) > 1 else 0
        second_best_score = ranked_votes[1][2] if len(ranked_votes) > 1 else 0.0

        unique_vote = vote_count >= 2 and vote_count > second_vote_count
        elite_single_vote = vote_count == 1 and best_score >= 99.0 and second_vote_count == 0

        if unique_vote or elite_single_vote:
            confidence = min(0.9999, round((best_score / 100.0) + min(vote_count, 3) * 0.02, 4))
            results[tm_player_id] = {
                "local_player_id": best_player_id,
                "identity_status": "linked_to_local_player",
                "confidence": confidence,
                "match_method": "linked_match_team_lineup_name_jersey_consensus",
                "review_status": "auto_approved",
                "player_name_raw": tm_row.player_name,
                "date_of_birth_raw": tm_row.date_of_birth_raw,
                "source_evidence": {
                    "voteCount": vote_count,
                    "secondVoteCount": second_vote_count,
                    "bestScore": round(best_score, 4),
                    "secondBestScore": round(second_best_score, 4) if second_best_score else None,
                    "sampleMatches": best_evidences[:10],
                },
            }
            continue

        results[tm_player_id] = {
            "local_player_id": None,
            "identity_status": "ambiguous",
            "confidence": round(best_score / 100.0, 4),
            "match_method": "linked_match_team_lineup_multiple_candidates",
            "review_status": "manual_review",
            "player_name_raw": tm_row.player_name,
            "date_of_birth_raw": tm_row.date_of_birth_raw,
            "source_evidence": {
                "voteCount": vote_count,
                "secondVoteCount": second_vote_count,
                "bestScore": round(best_score, 4),
                "candidatePlayerIds": [player_id for player_id, *_ in ranked_votes[:5]],
                "sampleMatches": best_evidences[:10],
                "ambiguousEvents": ambiguous_events_by_tm_player.get(tm_player_id, [])[:10],
            },
        }

    return results


def upsert_tm_player_xref(conn: psycopg.Connection[Any], results: dict[str, dict[str, Any]]) -> None:
    rows = [
        (
            tm_player_id,
            payload["local_player_id"],
            payload["player_name_raw"],
            payload["date_of_birth_raw"],
            payload["identity_status"],
            payload["confidence"],
            payload["match_method"],
            payload["review_status"],
            json.dumps(payload["source_evidence"], ensure_ascii=True),
        )
        for tm_player_id, payload in results.items()
    ]
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into control.tm_player_xref (
              tm_player_id,
              local_player_id,
              player_name_raw,
              date_of_birth_raw,
              identity_status,
              confidence,
              resolved_at,
              updated_at,
              match_method,
              review_status,
              source_evidence
            )
            values (%s, %s, %s, %s, %s, %s, now(), now(), %s, %s, %s::jsonb)
            on conflict (tm_player_id) do update set
              local_player_id = excluded.local_player_id,
              player_name_raw = excluded.player_name_raw,
              date_of_birth_raw = excluded.date_of_birth_raw,
              identity_status = excluded.identity_status,
              confidence = excluded.confidence,
              resolved_at = now(),
              updated_at = now(),
              match_method = excluded.match_method,
              review_status = excluded.review_status,
              source_evidence = excluded.source_evidence;
            """,
            rows,
        )


def summarize(results: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for payload in results.values():
        status = str(payload["identity_status"])
        summary[status] = summary.get(status, 0) + 1
    return summary


def main() -> None:
    env_values = load_env_file(DEFAULT_ENV_PATH)
    dsn = resolve_dsn(env_values)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        local_lineups = load_local_lineups(conn)
        tm_club_name_map = load_tm_club_name_map(conn)
        linked_tm_match_map = load_linked_tm_match_map(conn, tm_club_name_map)
        tm_rows = load_tm_lineups(conn, linked_tm_match_map)
        results = reconcile_rows(tm_rows, local_lineups)
        upsert_tm_player_xref(conn, results)
        conn.commit()

    print(json.dumps({"processedTmPlayers": len(results), "statusSummary": summarize(results)}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
