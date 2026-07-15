"""Export public mart data to local Parquet snapshots consumed by the PBIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT_DIR = Path(r"C:\Users\Public\football-analytics-bi-data")
SNAPSHOT_DIR_ENV = "BI_SNAPSHOT_DIR"

PREFERRED_SCOPES_CTE = """
        preferred_scopes as (
            select distinct on (competition_key, season_label)
                   provider, competition_key, season_label
            from mart.fact_matches
            order by competition_key, season_label,
                     case provider
                         when 'sportmonks' then 1
                         when 'dataset_brasileirao' then 2
                         when 'transfermarkt' then 3
                         when 'eloratings' then 4
                         else 5
                     end,
                     provider
        )
"""

QUERIES = {
    "FactMatch": f"""
        with {PREFERRED_SCOPES_CTE}
        select match_id, concat_ws('|', provider, competition_key, season_label) scope_key,
               provider, competition_key, season_label, date_day match_date, round_number,
               home_team_id, away_team_id, home_goals, away_goals, total_goals, result,
               (home_goals is not null and away_goals is not null) score_valid,
               updated_at::timestamp without time zone updated_at
        from mart.fact_matches fm
        where exists (
            select 1 from preferred_scopes ps
            where ps.provider = fm.provider
              and ps.competition_key = fm.competition_key
              and ps.season_label = fm.season_label
        )
    """,
    "FactTeamMatch": f"""
        with {PREFERRED_SCOPES_CTE}, valid as (
            select fm.* from mart.fact_matches fm
            where home_goals is not null and away_goals is not null
              and home_team_id is not null and away_team_id is not null
              and exists (
                  select 1 from preferred_scopes ps
                  where ps.provider = fm.provider
                    and ps.competition_key = fm.competition_key
                    and ps.season_label = fm.season_label
              )
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
    "FactPlayerMatch": f"""
        with {PREFERRED_SCOPES_CTE}
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
          and exists (
              select 1 from preferred_scopes ps
              where ps.provider = fm.provider
                and ps.competition_key = fm.competition_key
                and ps.season_label = fm.season_label
          )
    """,
    "DimScope": f"""
        with {PREFERRED_SCOPES_CTE}, player_matches as (
            select distinct provider,match_id from mart.fact_fixture_player_stats
        ), scopes as (
            select fm.provider,fm.competition_key,fm.season_label,count(*) total_matches,
                   count(*) filter(where fm.home_goals is not null and fm.away_goals is not null) scored_matches,
                   count(pm.match_id) player_matches
            from mart.fact_matches fm
            left join player_matches pm on pm.provider=fm.provider and pm.match_id=fm.match_id
            group by 1,2,3
        )
        select concat_ws('|',s.provider,s.competition_key,s.season_label) scope_key, s.provider,
               coalesce(c.competition_name, initcap(replace(s.competition_key,'_',' '))) competition,
               s.competition_key, s.season_label,
               total_matches::bigint,
               round(100.0*scored_matches/nullif(total_matches,0),2)::double precision score_pct,
               round(100.0*player_matches/nullif(total_matches,0),2)::double precision player_stats_pct,
               scored_matches*100.0/nullif(total_matches,0)>=95 team_ranking_eligible,
               player_matches*100.0/nullif(total_matches,0)>=95 player_ranking_eligible,
               ps.provider is not null is_preferred_public_scope
        from scopes s
        left join preferred_scopes ps using (provider, competition_key, season_label)
        left join control.competitions c on c.competition_key = s.competition_key
    """,
    "DimDate": "select date_day, year::bigint, month::bigint, to_char(date_day,'YYYY-MM') month_name from mart.dim_date",
    "DimTeam": "select team_sk, team_id, team_name from mart.dim_team",
    "DimPlayer": "select player_sk, player_id, player_name from mart.dim_player",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta os sete snapshots Parquet do mart.")
    parser.add_argument("--output-dir", dest="output_dir", help="Diretório dos snapshots; relativo à raiz do repositório.")
    return parser.parse_args(argv)


def resolve_snapshot_dir(
    cli_value: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    dotenv_value: str | None = None,
    root: Path = ROOT,
) -> Path:
    values = environ if environ is not None else os.environ
    raw_value = cli_value if cli_value is not None else values.get(SNAPSHOT_DIR_ENV, dotenv_value)
    if raw_value is None:
        raw_value = DEFAULT_SNAPSHOT_DIR
    if not str(raw_value).strip():
        raise ValueError(f"{SNAPSHOT_DIR_ENV} não pode ser vazio")
    path = Path(raw_value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def build_manifest(table_stats: dict[str, dict[str, int | str]]) -> dict[str, object]:
    return {"source": "PostgreSQL mart", "tables": table_stats}


def main(argv: Sequence[str] | None = None) -> None:
    import pandas as pd
    import psycopg
    import pyarrow as pa
    import pyarrow.parquet as pq
    from dotenv import dotenv_values

    args = parse_args(argv)
    env = dotenv_values(ROOT / ".env")
    data_root = resolve_snapshot_dir(args.output_dir, dotenv_value=env.get(SNAPSHOT_DIR_ENV))
    data_root.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest({})
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    ) as connection:
        for name, query in QUERIES.items():
            frame = pd.read_sql_query(query, connection).convert_dtypes(dtype_backend="pyarrow")
            path = data_root / f"{name}.parquet"
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
    print(f"Snapshots: {data_root}")


if __name__ == "__main__":
    main()
