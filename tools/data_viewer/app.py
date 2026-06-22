import os
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


ROUNDS_SQL = """
SELECT DISTINCT
  COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) AS round_number,
  f.round AS round_label
FROM raw.fixtures f
WHERE f.league_id = :league_id
  AND f.season = :season
  AND COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) IS NOT NULL
ORDER BY round_number;
"""

STANDINGS_SQL = """
WITH team_names AS (
  SELECT t.team_id, MAX(t.team_name) AS team_name
  FROM (
    SELECT home_team_id AS team_id, home_team_name AS team_name
    FROM raw.fixtures
    WHERE league_id = :league_id
      AND season = :season
    UNION ALL
    SELECT away_team_id AS team_id, away_team_name AS team_name
    FROM raw.fixtures
    WHERE league_id = :league_id
      AND season = :season
  ) t
  WHERE t.team_id IS NOT NULL
    AND t.team_name IS NOT NULL
  GROUP BY t.team_id
)
SELECT
  se.round,
  se.position,
  se.team_id,
  tn.team_name,
  se.points_accumulated,
  se.goals_for_accumulated,
  se.goal_diff_accumulated
FROM mart.standings_evolution se
LEFT JOIN team_names tn
  ON tn.team_id = se.team_id
WHERE se.season = :season
  AND se.round = :round_number
ORDER BY se.position, se.team_id;
"""

MATCHES_SQL = """
SELECT
  f.fixture_id AS match_id,
  f.date_utc,
  f.status_short,
  f.round,
  f.venue_name,
  f.venue_city,
  f.home_team_name,
  f.away_team_name,
  f.home_goals,
  f.away_goals,
  hs.total_shots AS home_shots,
  hs.shots_on_goal AS home_shots_on_target,
  hs.ball_possession AS home_possession,
  hs.corner_kicks AS home_corners,
  hs.fouls AS home_fouls,
  as2.total_shots AS away_shots,
  as2.shots_on_goal AS away_shots_on_target,
  as2.ball_possession AS away_possession,
  as2.corner_kicks AS away_corners,
  as2.fouls AS away_fouls
FROM raw.fixtures f
LEFT JOIN raw.match_statistics hs
  ON hs.fixture_id = f.fixture_id
 AND hs.team_id = f.home_team_id
LEFT JOIN raw.match_statistics as2
  ON as2.fixture_id = f.fixture_id
 AND as2.team_id = f.away_team_id
WHERE f.league_id = :league_id
  AND f.season = :season
  AND COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) = :round_number
ORDER BY f.date_utc, f.fixture_id;
"""

MATCH_DETAIL_STATS_SQL = """
SELECT
  f.fixture_id AS match_id,
  f.home_team_id,
  f.home_team_name,
  f.away_team_id,
  f.away_team_name,
  hs.total_shots AS home_shots,
  hs.shots_on_goal AS home_shots_on_target,
  hs.ball_possession AS home_possession,
  hs.corner_kicks AS home_corners,
  hs.fouls AS home_fouls,
  as2.total_shots AS away_shots,
  as2.shots_on_goal AS away_shots_on_target,
  as2.ball_possession AS away_possession,
  as2.corner_kicks AS away_corners,
  as2.fouls AS away_fouls
FROM raw.fixtures f
LEFT JOIN raw.match_statistics hs
  ON hs.fixture_id = f.fixture_id
 AND hs.team_id = f.home_team_id
LEFT JOIN raw.match_statistics as2
  ON as2.fixture_id = f.fixture_id
 AND as2.team_id = f.away_team_id
WHERE f.fixture_id = :fixture_id;
"""

MATCH_EVENTS_SQL = """
SELECT
  event_id,
  fixture_id,
  time_elapsed,
  time_extra,
  CASE
    WHEN time_elapsed IS NULL THEN NULL
    WHEN time_extra IS NULL THEN time_elapsed::text
    ELSE (time_elapsed::text || '+' || time_extra::text)
  END AS minute,
  type,
  detail,
  team_name,
  player_name
FROM raw.match_events
WHERE fixture_id = :fixture_id
ORDER BY
  COALESCE(time_elapsed, 9999),
  COALESCE(time_extra, 0),
  event_id;
"""

CHECK_DUP_FIXTURES_SQL = """
SELECT fixture_id, COUNT(*) AS dup_count
FROM raw.fixtures
WHERE league_id = :league_id
  AND season = :season
GROUP BY fixture_id
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, fixture_id;
"""

CHECK_COVERAGE_SQL = """
WITH fixture_base AS (
  SELECT f.fixture_id
  FROM raw.fixtures f
  WHERE f.league_id = :league_id
    AND f.season = :season
),
stats_per_fixture AS (
  SELECT ms.fixture_id, COUNT(*) AS stats_rows
  FROM raw.match_statistics ms
  GROUP BY ms.fixture_id
)
SELECT
  COUNT(*) AS fixtures_total,
  COUNT(*) FILTER (WHERE COALESCE(spf.stats_rows, 0) = 2) AS fixtures_com_2_stats,
  COUNT(*) FILTER (WHERE COALESCE(spf.stats_rows, 0) = 1) AS fixtures_com_1_stat,
  COUNT(*) FILTER (WHERE COALESCE(spf.stats_rows, 0) = 0) AS fixtures_sem_stats
FROM fixture_base fb
LEFT JOIN stats_per_fixture spf
  ON spf.fixture_id = fb.fixture_id;
"""

CHECK_COVERAGE_BY_ROUND_SQL = """
WITH fixture_round AS (
  SELECT
    f.fixture_id,
    COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) AS round_number
  FROM raw.fixtures f
  WHERE f.league_id = :league_id
    AND f.season = :season
),
stats_per_fixture AS (
  SELECT ms.fixture_id, COUNT(*) AS stats_rows
  FROM raw.match_statistics ms
  GROUP BY ms.fixture_id
),
events_per_fixture AS (
  SELECT me.fixture_id, COUNT(*) AS events_rows
  FROM raw.match_events me
  GROUP BY me.fixture_id
)
SELECT
  fr.round_number,
  COUNT(*) AS fixtures_total,
  COUNT(*) FILTER (WHERE COALESCE(spf.stats_rows, 0) >= 2) AS fixtures_com_stats,
  COUNT(*) FILTER (WHERE COALESCE(epf.events_rows, 0) > 0) AS fixtures_com_eventos,
  COUNT(*) FILTER (WHERE COALESCE(spf.stats_rows, 0) = 0) AS fixtures_sem_stats,
  COUNT(*) FILTER (WHERE COALESCE(epf.events_rows, 0) = 0) AS fixtures_sem_eventos
FROM fixture_round fr
LEFT JOIN stats_per_fixture spf
  ON spf.fixture_id = fr.fixture_id
LEFT JOIN events_per_fixture epf
  ON epf.fixture_id = fr.fixture_id
WHERE fr.round_number IS NOT NULL
GROUP BY fr.round_number
ORDER BY fr.round_number;
"""

CHECK_DUP_EVENTS_NK_SQL = """
SELECT
  fixture_id,
  COALESCE(time_elapsed, -1) AS time_elapsed,
  COALESCE(time_extra, -1) AS time_extra,
  COALESCE(team_id, -1) AS team_id,
  COALESCE(player_id, -1) AS player_id,
  COALESCE(assist_id, -1) AS assist_id,
  COALESCE(type, '') AS type,
  COALESCE(detail, '') AS detail,
  COALESCE(comments, '') AS comments,
  COUNT(*) AS dup_count
FROM raw.match_events
GROUP BY
  fixture_id,
  COALESCE(time_elapsed, -1),
  COALESCE(time_extra, -1),
  COALESCE(team_id, -1),
  COALESCE(player_id, -1),
  COALESCE(assist_id, -1),
  COALESCE(type, ''),
  COALESCE(detail, ''),
  COALESCE(comments, '')
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, fixture_id
LIMIT 200;
"""

CHECK_NULL_RATE_SQL = """
WITH base AS (
  SELECT *
  FROM raw.fixtures
  WHERE league_id = :league_id
    AND season = :season
),
total AS (
  SELECT COUNT(*)::numeric AS total_rows FROM base
),
nulls AS (
  SELECT 'home_team_id' AS field_name, COUNT(*) FILTER (WHERE home_team_id IS NULL)::numeric AS null_rows FROM base
  UNION ALL
  SELECT 'away_team_id', COUNT(*) FILTER (WHERE away_team_id IS NULL)::numeric FROM base
  UNION ALL
  SELECT 'date', COUNT(*) FILTER (WHERE date IS NULL)::numeric FROM base
  UNION ALL
  SELECT 'home_goals', COUNT(*) FILTER (WHERE home_goals IS NULL)::numeric FROM base
  UNION ALL
  SELECT 'away_goals', COUNT(*) FILTER (WHERE away_goals IS NULL)::numeric FROM base
)
SELECT
  n.field_name,
  n.null_rows::bigint AS null_rows,
  t.total_rows::bigint AS total_rows,
  CASE
    WHEN t.total_rows = 0 THEN 0
    ELSE ROUND((n.null_rows / t.total_rows) * 100.0, 2)
  END AS null_rate_pct
FROM nulls n
CROSS JOIN total t
ORDER BY null_rate_pct DESC, field_name;
"""

CHECK_OUTLIERS_SQL = """
WITH base AS (
  SELECT
    fixture_id,
    date,
    date_utc,
    season,
    home_goals,
    away_goals,
    COALESCE(home_goals, 0) + COALESCE(away_goals, 0) AS total_goals
  FROM raw.fixtures
  WHERE league_id = :league_id
    AND season = :season
)
SELECT
  fixture_id,
  date,
  date_utc,
  season,
  home_goals,
  away_goals,
  total_goals,
  CASE
    WHEN total_goals < 0 THEN 'total_goals_negativo'
    WHEN total_goals > 20 THEN 'total_goals_maior_20'
    WHEN date IS NOT NULL AND EXTRACT(YEAR FROM date)::int <> season THEN 'date_fora_da_temporada'
    WHEN date IS NULL AND date_utc IS NOT NULL AND EXTRACT(YEAR FROM date_utc)::int <> season THEN 'date_utc_fora_da_temporada'
    ELSE 'ok'
  END AS outlier_type
FROM base
WHERE total_goals < 0
   OR total_goals > 20
   OR (date IS NOT NULL AND EXTRACT(YEAR FROM date)::int <> season)
   OR (date IS NULL AND date_utc IS NOT NULL AND EXTRACT(YEAR FROM date_utc)::int <> season)
ORDER BY fixture_id
LIMIT 200;
"""

CHECK_TOP20_PROBLEMS_SQL = """
WITH fixtures_base AS (
  SELECT
    fixture_id,
    COALESCE((regexp_match(round, '([0-9]+)'))[1]::int, NULL) AS round_number,
    league_id,
    season,
    home_team_id,
    away_team_id,
    date,
    home_goals,
    away_goals
  FROM raw.fixtures
  WHERE league_id = :league_id
    AND season = :season
),
stats_per_fixture AS (
  SELECT fixture_id, COUNT(*) AS stats_rows
  FROM raw.match_statistics
  GROUP BY fixture_id
),
events_per_fixture AS (
  SELECT fixture_id, COUNT(*) AS events_rows
  FROM raw.match_events
  GROUP BY fixture_id
),
dup_fixtures AS (
  SELECT fixture_id, COUNT(*) AS dup_count
  FROM raw.fixtures
  WHERE league_id = :league_id
    AND season = :season
  GROUP BY fixture_id
  HAVING COUNT(*) > 1
),
problem_rows AS (
  SELECT
    'dup_fixture_id' AS problem_type,
    d.fixture_id::text AS problem_key,
    d.dup_count::bigint AS severity,
    ('fixture_id duplicado no raw.fixtures: ' || d.fixture_id::text) AS detail
  FROM dup_fixtures d
  UNION ALL
  SELECT
    'fixture_sem_stats' AS problem_type,
    f.fixture_id::text AS problem_key,
    50::bigint AS severity,
    ('fixture sem stats: ' || f.fixture_id::text) AS detail
  FROM fixtures_base f
  LEFT JOIN stats_per_fixture s ON s.fixture_id = f.fixture_id
  WHERE COALESCE(s.stats_rows, 0) = 0
  UNION ALL
  SELECT
    'fixture_sem_eventos' AS problem_type,
    f.fixture_id::text AS problem_key,
    40::bigint AS severity,
    ('fixture sem eventos: ' || f.fixture_id::text) AS detail
  FROM fixtures_base f
  LEFT JOIN events_per_fixture e ON e.fixture_id = f.fixture_id
  WHERE COALESCE(e.events_rows, 0) = 0
  UNION ALL
  SELECT
    'campos_criticos_nulos' AS problem_type,
    f.fixture_id::text AS problem_key,
    (
      (CASE WHEN f.home_team_id IS NULL THEN 1 ELSE 0 END) +
      (CASE WHEN f.away_team_id IS NULL THEN 1 ELSE 0 END) +
      (CASE WHEN f.date IS NULL THEN 1 ELSE 0 END) +
      (CASE WHEN f.home_goals IS NULL THEN 1 ELSE 0 END) +
      (CASE WHEN f.away_goals IS NULL THEN 1 ELSE 0 END)
    )::bigint * 10 AS severity,
    ('fixture com nulos criticos: ' || f.fixture_id::text) AS detail
  FROM fixtures_base f
  WHERE
    f.home_team_id IS NULL OR
    f.away_team_id IS NULL OR
    f.date IS NULL OR
    f.home_goals IS NULL OR
    f.away_goals IS NULL
  UNION ALL
  SELECT
    'outlier_total_goals' AS problem_type,
    f.fixture_id::text AS problem_key,
    30::bigint AS severity,
    ('total_goals fora da faixa [0,20]: ' || f.fixture_id::text) AS detail
  FROM fixtures_base f
  WHERE (COALESCE(f.home_goals, 0) + COALESCE(f.away_goals, 0)) < 0
     OR (COALESCE(f.home_goals, 0) + COALESCE(f.away_goals, 0)) > 20
)
SELECT
  problem_type,
  problem_key,
  severity,
  detail
FROM problem_rows
ORDER BY severity DESC, problem_type, problem_key
LIMIT 20;
"""

CHECK_COUNTS_SQL = """
SELECT 'raw.fixtures' AS table_name, COUNT(*)::bigint AS row_count FROM raw.fixtures
UNION ALL
SELECT 'raw.match_events', COUNT(*)::bigint FROM raw.match_events
UNION ALL
SELECT 'raw.match_statistics', COUNT(*)::bigint FROM raw.match_statistics
UNION ALL
SELECT 'mart.standings_evolution', COUNT(*)::bigint FROM mart.standings_evolution
UNION ALL
SELECT
  'mart.league_summary',
  CASE
    WHEN to_regclass('mart.league_summary') IS NULL THEN NULL::bigint
    ELSE (SELECT COUNT(*)::bigint FROM mart.league_summary)
  END AS row_count;
"""


def _resolve_dsn() -> str:
    dsn = os.getenv("FOOTBALL_PG_DSN")
    if dsn:
        return dsn

    host = os.getenv("FOOTBALL_PG_HOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = os.getenv("FOOTBALL_PG_PORT", os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("FOOTBALL_PG_USER", os.getenv("POSTGRES_USER", "football"))
    password = os.getenv("FOOTBALL_PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", "football"))
    dbname = os.getenv("FOOTBALL_PG_DBNAME", os.getenv("POSTGRES_DB", "football_dw"))
    return f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(dbname)}"


@st.cache_resource(show_spinner=False)
def _get_engine() -> Engine:
    return create_engine(_resolve_dsn(), pool_pre_ping=True)


def _read_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with _get_engine().begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def _load_filter_options() -> tuple[list[int], dict[int, list[int]]]:
    league_df = _read_df("SELECT DISTINCT league_id FROM raw.fixtures WHERE league_id IS NOT NULL ORDER BY league_id;")
    leagues = [int(v) for v in league_df["league_id"].tolist()]
    seasons_by_league: dict[int, list[int]] = {}
    for league_id in leagues:
        season_df = _read_df(
            """
            SELECT DISTINCT season
            FROM raw.fixtures
            WHERE league_id = :league_id
              AND season IS NOT NULL
            ORDER BY season;
            """,
            {"league_id": league_id},
        )
        seasons_by_league[league_id] = [int(v) for v in season_df["season"].tolist()]
    return leagues, seasons_by_league


def main() -> None:
    st.set_page_config(page_title="Football Data Viewer", layout="wide")
    st.title("Football Data Viewer")
    st.caption("Viewer provisório para validação em raw.* e mart.*")

    try:
        leagues, seasons_by_league = _load_filter_options()
    except Exception as exc:
        st.error(f"Falha ao conectar/carregar filtros: {exc}")
        st.stop()

    if not leagues:
        st.warning("Nenhum dado encontrado em raw.fixtures.")
        st.stop()

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        league_id = st.selectbox("league_id", leagues, index=0)

    seasons = seasons_by_league.get(league_id, [])
    if not seasons:
        st.warning(f"Nenhuma season encontrada para league_id={league_id}.")
        st.stop()

    with c2:
        season = st.selectbox("season", seasons, index=len(seasons) - 1)

    rounds_df = _read_df(ROUNDS_SQL, {"league_id": league_id, "season": season})
    if rounds_df.empty:
        st.warning("Nenhuma rodada disponível para os filtros selecionados.")
        st.stop()
    round_options = rounds_df["round_number"].astype(int).tolist()
    with c3:
        round_number = st.selectbox("round", round_options, index=max(len(round_options) - 1, 0))

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Tabela")
        standings_df = _read_df(
            STANDINGS_SQL,
            {"league_id": league_id, "season": season, "round_number": round_number},
        )
        st.dataframe(standings_df, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Jogos")
        matches_df = _read_df(
            MATCHES_SQL,
            {"league_id": league_id, "season": season, "round_number": round_number},
        )
        if not matches_df.empty and "date_utc" in matches_df.columns:
            matches_df["date_utc"] = pd.to_datetime(matches_df["date_utc"], utc=True, errors="coerce")
        if matches_df.empty:
            st.info("Sem jogos para os filtros selecionados.")
        else:
            for _, row in matches_df.iterrows():
                score_home = "-" if pd.isna(row.get("home_goals")) else int(row["home_goals"])
                score_away = "-" if pd.isna(row.get("away_goals")) else int(row["away_goals"])
                match_time = ""
                if pd.notna(row.get("date_utc")):
                    match_time = row["date_utc"].strftime("%Y-%m-%d %H:%M UTC")
                venue_parts = [str(v) for v in [row.get("venue_name"), row.get("venue_city")] if pd.notna(v) and str(v).strip()]
                venue_text = " - ".join(venue_parts) if venue_parts else "Sem estadio"

                st.markdown(
                    "\n".join(
                        [
                            f"**{row['home_team_name']} {score_home} x {score_away} {row['away_team_name']}**",
                            f"`fixture_id={int(row['match_id'])}` | status: `{row['status_short']}`",
                            f"{venue_text} | {match_time}",
                        ]
                    )
                )
                st.divider()

            fixture_options = [int(v) for v in matches_df["match_id"].tolist()]
            selected_fixture = st.selectbox(
                "Selecionar jogo para detalhar",
                fixture_options,
                index=0,
                format_func=lambda v: f"fixture_id={v}",
            )

            st.markdown("### Detalhe do jogo")
            detail_df = _read_df(MATCH_DETAIL_STATS_SQL, {"fixture_id": selected_fixture})
            if detail_df.empty:
                st.warning("Fixture não encontrado em raw.fixtures.")
            else:
                d = detail_df.iloc[0]
                stats_values = [
                    d.get("home_shots"),
                    d.get("home_shots_on_target"),
                    d.get("home_possession"),
                    d.get("home_corners"),
                    d.get("home_fouls"),
                    d.get("away_shots"),
                    d.get("away_shots_on_target"),
                    d.get("away_possession"),
                    d.get("away_corners"),
                    d.get("away_fouls"),
                ]
                has_stats = any(pd.notna(v) for v in stats_values)

                if not has_stats:
                    st.warning("sem stats para este fixture")
                else:
                    stats_table = pd.DataFrame(
                        [
                            {
                                "team": d["home_team_name"],
                                "shots": d["home_shots"],
                                "shots_on_target": d["home_shots_on_target"],
                                "possession": d["home_possession"],
                                "corners": d["home_corners"],
                                "fouls": d["home_fouls"],
                            },
                            {
                                "team": d["away_team_name"],
                                "shots": d["away_shots"],
                                "shots_on_target": d["away_shots_on_target"],
                                "possession": d["away_possession"],
                                "corners": d["away_corners"],
                                "fouls": d["away_fouls"],
                            },
                        ]
                    )
                    st.markdown("**Estatísticas (home/away)**")
                    st.dataframe(stats_table, use_container_width=True, hide_index=True)

                events_df = _read_df(MATCH_EVENTS_SQL, {"fixture_id": selected_fixture})
                st.markdown("**Eventos**")
                if events_df.empty:
                    st.info("Sem eventos para este fixture.")
                else:
                    default_cols = ["minute", "type", "detail", "team_name", "player_name"]
                    st.dataframe(events_df[default_cols], use_container_width=True, hide_index=True)

    st.subheader("Checks")
    tab_summary, tab_duplicates, tab_quality, tab_top = st.tabs(["Resumo", "Duplicidades", "Qualidade", "Top 20"])

    with tab_summary:
        coverage_df = _read_df(CHECK_COVERAGE_SQL, {"league_id": league_id, "season": season})
        counts_df = _read_df(CHECK_COUNTS_SQL)

        if not coverage_df.empty:
            row = coverage_df.iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("fixtures_total", int(row["fixtures_total"]))
            m2.metric("fixtures_com_2_stats", int(row["fixtures_com_2_stats"]))
            m3.metric("fixtures_com_1_stat", int(row["fixtures_com_1_stat"]))
            m4.metric("fixtures_sem_stats", int(row["fixtures_sem_stats"]))

        st.markdown("Contagens gerais")
        st.dataframe(counts_df, use_container_width=True, hide_index=True)

        st.markdown("Cobertura por rodada")
        coverage_round_df = _read_df(CHECK_COVERAGE_BY_ROUND_SQL, {"league_id": league_id, "season": season})
        st.dataframe(coverage_round_df, use_container_width=True, hide_index=True)

    with tab_duplicates:
        dup_fixtures_df = _read_df(CHECK_DUP_FIXTURES_SQL, {"league_id": league_id, "season": season})
        dup_events_df = _read_df(CHECK_DUP_EVENTS_NK_SQL)

        st.markdown("Duplicidade de fixture_id em raw.fixtures")
        st.dataframe(dup_fixtures_df, use_container_width=True, hide_index=True)

        st.markdown("Duplicidade em raw.match_events (chave natural)")
        st.dataframe(dup_events_df, use_container_width=True, hide_index=True)

    with tab_quality:
        st.markdown("Null-rate de campos críticos em raw.fixtures")
        null_rate_df = _read_df(CHECK_NULL_RATE_SQL, {"league_id": league_id, "season": season})
        st.dataframe(null_rate_df, use_container_width=True, hide_index=True)

        st.markdown("Outliers básicos (total_goals e datas fora da temporada)")
        outliers_df = _read_df(CHECK_OUTLIERS_SQL, {"league_id": league_id, "season": season})
        st.dataframe(outliers_df, use_container_width=True, hide_index=True)

    with tab_top:
        st.markdown("Top 20 problemas mais graves")
        top_problems_df = _read_df(CHECK_TOP20_PROBLEMS_SQL, {"league_id": league_id, "season": season})
        st.dataframe(top_problems_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
