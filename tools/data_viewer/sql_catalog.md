# SQL Catalog - Data Viewer

Todos os SQLs abaixo usam apenas `raw.*` e `mart.*`.

## Parametros
- `:league_id` (bigint)
- `:season` (int)
- `:round_number` (int)

## 0) Rodadas disponiveis (para filtro)
```sql
SELECT DISTINCT
  COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) AS round_number,
  f.round AS round_label
FROM raw.fixtures f
WHERE f.league_id = :league_id
  AND f.season = :season
  AND COALESCE((regexp_match(f.round, '([0-9]+)'))[1]::int, NULL) IS NOT NULL
ORDER BY round_number;
```

## 1) Coluna esquerda - Tabela (standings da rodada)
```sql
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
```

## 2) Coluna direita - Jogos da rodada (com stats home/away)
```sql
SELECT
  f.fixture_id AS match_id,
  f.date_utc,
  f.status_short,
  f.round,
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
```

## 3) Checks - Duplicidade

### 3.1 `raw.fixtures` duplicado por `fixture_id`
```sql
SELECT fixture_id, COUNT(*) AS dup_count
FROM raw.fixtures
WHERE league_id = :league_id
  AND season = :season
GROUP BY fixture_id
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, fixture_id;
```

### 3.2 `raw.match_events` duplicado por chave natural
```sql
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
```

### 3.3 `raw.match_statistics` duplicado por `(fixture_id, team_id)`
```sql
SELECT fixture_id, team_id, COUNT(*) AS dup_count
FROM raw.match_statistics
GROUP BY fixture_id, team_id
HAVING COUNT(*) > 1
ORDER BY dup_count DESC, fixture_id, team_id;
```

## 4) Checks - Cobertura de statistics (temporada)
```sql
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
```

## 5) Checks - Cobertura de statistics por rodada
```sql
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
```

## 6) Checks - Null-rate (campos críticos em raw.fixtures)
```sql
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
```

## 7) Checks - Outliers básicos
```sql
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
```

## 8) Checks - Top 20 problemas mais graves
```sql
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
```

## 9) Checks - Contagens gerais
```sql
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
```

## 10) (Opcional) Resumo da liga (se usar no rodape)
```sql
SELECT
  competition_sk,
  league_id,
  league_name,
  season,
  total_matches,
  total_goals,
  avg_goals_per_match,
  first_match_date,
  last_match_date
FROM mart.league_summary
WHERE league_id = :league_id
  AND season = :season;
```
