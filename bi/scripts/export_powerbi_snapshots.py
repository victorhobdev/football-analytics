"""Export public mart data to local Parquet snapshots consumed by the PBIP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(r"C:\Users\Public\football-analytics-bi-data")

QUERIES = {
    "FactMatch": """
        select match_id, concat_ws('|', provider, competition_key, season_label) scope_key,
               provider, competition_key, season_label, date_day match_date, round_number,
               home_team_id, away_team_id, home_goals, away_goals, total_goals, result,
               (home_goals is not null and away_goals is not null) score_valid,
               updated_at::timestamp without time zone updated_at
        from mart.fact_matches
    """,
    "FactTeamMatch": """
        with valid as (
            select * from mart.fact_matches
            where home_goals is not null and away_goals is not null
              and home_team_id is not null and away_team_id is not null
        ), rows as (
            select provider, match_id, concat_ws('|',provider,competition_key,season_label) scope_key,
                   date_day match_date, round_number, home_team_sk team_sk, home_team_id team_id,
                   away_team_sk opponent_team_sk, away_team_id opponent_team_id, 'Casa' venue,
                   home_goals goals_for, away_goals goals_against
            from valid
            union all
            select provider, match_id, concat_ws('|',provider,competition_key,season_label),
                   date_day, round_number, away_team_sk, away_team_id, home_team_sk, home_team_id,
                   'Fora', away_goals, home_goals
            from valid
        )
        select r.match_id, r.scope_key, r.match_date, r.round_number, r.team_sk, r.team_id,
               r.opponent_team_sk, r.opponent_team_id, r.venue, r.goals_for, r.goals_against,
               case when r.goals_for > r.goals_against then 'Vitória'
                    when r.goals_for = r.goals_against then 'Empate' else 'Derrota' end result,
               case when r.goals_for > r.goals_against then 3
                    when r.goals_for = r.goals_against then 1 else 0 end::bigint points,
               s.ball_possession::double precision ball_possession,
               s.passes_pct::double precision passes_pct,
               s.total_shots::bigint total_shots,
               s.shots_on_goal::bigint shots_on_goal,
               s.passes_accurate::bigint passes_accurate
        from rows r
        left join mart.stg_match_statistics s
          on r.provider = 'sportmonks' and s.fixture_id = r.match_id and s.team_id = r.team_id
    """,
    "FactPlayerMatch": """
        select fps.fixture_player_stat_id player_match_id, fps.match_id,
               concat_ws('|',fm.provider,fm.competition_key,fm.season_label) scope_key,
               fm.date_day match_date, fps.team_sk, fps.team_id, fps.player_sk, fps.player_id,
               fps.minutes_played::double precision minutes_played,
               fps.goals::double precision goals, fps.assists::double precision assists,
               fps.shots_total::double precision shots_total,
               fps.shots_on_goal::double precision shots_on_goal,
               fps.yellow_cards::double precision yellow_cards,
               fps.red_cards::double precision red_cards,
               fps.rating::double precision rating
        from mart.fact_fixture_player_stats fps
        join mart.fact_matches fm on fm.match_id=fps.match_id and fm.provider=fps.provider
        where fm.home_goals is not null and fm.away_goals is not null
    """,
    "DimScope": """
        with player_matches as (
            select distinct provider,match_id from mart.fact_fixture_player_stats
        ), scopes as (
            select fm.provider,fm.competition_key,fm.season_label,count(*) total_matches,
                   count(*) filter(where fm.home_goals is not null and fm.away_goals is not null) scored_matches,
                   count(pm.match_id) player_matches
            from mart.fact_matches fm
            left join player_matches pm on pm.provider=fm.provider and pm.match_id=fm.match_id
            group by 1,2,3
        )
        select concat_ws('|',provider,competition_key,season_label) scope_key, provider,
               initcap(replace(competition_key,'_',' ')) competition, competition_key, season_label,
               total_matches::bigint,
               round(100.0*scored_matches/nullif(total_matches,0),2)::double precision score_pct,
               round(100.0*player_matches/nullif(total_matches,0),2)::double precision player_stats_pct,
               scored_matches*100.0/nullif(total_matches,0)>=95 team_ranking_eligible,
               player_matches*100.0/nullif(total_matches,0)>=95 player_ranking_eligible
        from scopes
    """,
    "DimDate": "select date_day, year::bigint, month::bigint, to_char(date_day,'YYYY-MM') month_name from mart.dim_date",
    "DimTeam": "select team_sk, team_id, team_name from mart.dim_team",
    "DimPlayer": "select player_sk, player_id, player_name from mart.dim_player",
}


def main() -> None:
    env = dotenv_values(ROOT / ".env")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"source": "PostgreSQL mart", "tables": {}}
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    ) as connection:
        for name, query in QUERIES.items():
            frame = pd.read_sql_query(query, connection).convert_dtypes(dtype_backend="pyarrow")
            path = DATA_ROOT / f"{name}.parquet"
            pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path, compression="zstd")
            manifest["tables"][name] = {
                "rows": len(frame),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            print(f"{name}: {len(frame):,} linhas")

    manifest_path = ROOT / "bi" / "data" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Snapshots: {DATA_ROOT}")


if __name__ == "__main__":
    main()
