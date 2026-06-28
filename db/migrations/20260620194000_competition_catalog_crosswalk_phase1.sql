-- migrate:up
ALTER TABLE control.competition_provider_map
  ADD COLUMN IF NOT EXISTS provider_league_code TEXT;

ALTER TABLE control.competition_provider_map
  ALTER COLUMN provider_league_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_control_competition_provider_map_provider_league_code
  ON control.competition_provider_map (provider, provider_league_code)
  WHERE provider_league_code IS NOT NULL;

WITH competition_seed AS (
  SELECT *
  FROM (
    VALUES
      ('african_cup_of_nations', 'Copa Africana de Nações', 'continental_cup', 'África', 'CAF', 1::smallint, TRUE, 118),
      ('brasileirao_a', 'Campeonato Brasileiro Série A', 'league', 'Brasil', 'CONMEBOL', 1::smallint, TRUE, 80),
      ('brasileirao_b', 'Campeonato Brasileiro Série B', 'league', 'Brasil', 'CONMEBOL', 2::smallint, TRUE, 90),
      ('bundesliga', 'Bundesliga', 'league', 'Alemanha', 'UEFA', 1::smallint, TRUE, 40),
      ('champions_league', 'UEFA Champions League', 'continental_cup', NULL, 'UEFA', NULL::smallint, TRUE, 60),
      ('copa_america', 'Copa América', 'continental_cup', 'América do Sul', 'CONMEBOL', 1::smallint, TRUE, 117),
      ('copa_del_rey', 'Copa del Rey', 'cup', 'Espanha', 'UEFA', NULL::smallint, TRUE, 140),
      ('copa_do_brasil', 'Copa do Brasil', 'cup', 'Brasil', 'CONMEBOL', NULL::smallint, TRUE, 100),
      ('fa_womens_super_league', 'FA Women''s Super League', 'league', 'Inglaterra', 'UEFA', 1::smallint, TRUE, 145),
      ('fifa_intercontinental_cup', 'FIFA Intercontinental Cup', 'cup', 'Mundo', 'FIFA', NULL::smallint, TRUE, 65),
      ('fifa_u20_world_cup', 'Copa do Mundo FIFA Sub-20', 'cup', 'Mundo', 'FIFA', NULL::smallint, TRUE, 162),
      ('fifa_womens_world_cup', 'Copa do Mundo Feminina FIFA', 'cup', 'Mundo', 'FIFA', NULL::smallint, TRUE, 161),
      ('fifa_world_cup_mens', 'Copa do Mundo FIFA', 'cup', 'Mundo', 'FIFA', 1::smallint, TRUE, 10),
      ('frauen_bundesliga', 'Frauen Bundesliga', 'league', 'Alemanha', 'UEFA', 1::smallint, TRUE, 146),
      ('indian_super_league', 'Indian Super League', 'league', 'Índia', 'AFC', 1::smallint, TRUE, 158),
      ('la_liga', 'La Liga', 'league', 'Espanha', 'UEFA', 1::smallint, TRUE, 20),
      ('libertadores', 'Copa Libertadores da América', 'continental_cup', NULL, 'CONMEBOL', NULL::smallint, TRUE, 70),
      ('liga_f', 'Liga F', 'league', 'Espanha', 'UEFA', 1::smallint, TRUE, 147),
      ('liga_profesional_argentina', 'Liga Profesional Argentina', 'league', 'Argentina', 'CONMEBOL', 1::smallint, TRUE, 157),
      ('ligue_1', 'Ligue 1', 'league', 'França', 'UEFA', 1::smallint, TRUE, 50),
      ('major_league_soccer', 'Major League Soccer', 'league', 'Estados Unidos', 'CONCACAF', 1::smallint, TRUE, 156),
      ('north_american_league', 'Liga Norte-Americana', 'league', 'Estados Unidos', 'CONCACAF', 1::smallint, TRUE, 159),
      ('nwsl', 'National Women''s Soccer League', 'league', 'Estados Unidos', 'CONCACAF', 1::smallint, TRUE, 148),
      ('premier_league', 'Premier League', 'league', 'Inglaterra', 'UEFA', 1::smallint, TRUE, 10),
      ('primeira_liga', 'Liga Portugal', 'league', 'Portugal', 'UEFA', 1::smallint, TRUE, 55),
      ('serie_a_it', 'Serie A', 'league', 'Itália', 'UEFA', 1::smallint, TRUE, 30),
      ('serie_a_women', 'Serie A Women', 'league', 'Itália', 'UEFA', 1::smallint, TRUE, 149),
      ('sudamericana', 'Copa Sudamericana', 'continental_cup', NULL, 'CONMEBOL', NULL::smallint, TRUE, 75),
      ('supercopa_do_brasil', 'Supercopa do Brasil', 'cup', 'Brasil', 'CONMEBOL', NULL::smallint, TRUE, 95),
      ('uefa_euro', 'UEFA Euro', 'continental_cup', 'Europa', 'UEFA', 1::smallint, TRUE, 150),
      ('uefa_europa_league', 'UEFA Europa League', 'continental_cup', NULL, 'UEFA', NULL::smallint, TRUE, 151),
      ('uefa_womens_euro', 'UEFA Women''s Euro', 'continental_cup', 'Europa', 'UEFA', 1::smallint, TRUE, 152)
  ) AS seeded (
    competition_key,
    competition_name,
    competition_type,
    country_name,
    confederation_name,
    tier,
    is_active,
    display_priority
  )
)
INSERT INTO control.competitions (
  competition_key,
  competition_name,
  competition_type,
  country_name,
  confederation_name,
  tier,
  is_active,
  display_priority
)
SELECT
  competition_key,
  competition_name,
  competition_type,
  country_name,
  confederation_name,
  tier,
  is_active,
  display_priority
FROM competition_seed
ON CONFLICT (competition_key) DO UPDATE
SET
  competition_name = EXCLUDED.competition_name,
  competition_type = EXCLUDED.competition_type,
  country_name = EXCLUDED.country_name,
  confederation_name = EXCLUDED.confederation_name,
  tier = EXCLUDED.tier,
  is_active = EXCLUDED.is_active,
  display_priority = EXCLUDED.display_priority,
  updated_at = now();

WITH provider_seed AS (
  SELECT *
  FROM (
    VALUES
      ('brasileirao_a', 'sportmonks', 648::bigint, NULL::text, 'Campeonato Brasileiro Série A', TRUE),
      ('brasileirao_b', 'sportmonks', 651::bigint, NULL::text, 'Campeonato Brasileiro Série B', TRUE),
      ('bundesliga', 'sportmonks', 82::bigint, NULL::text, 'Bundesliga', TRUE),
      ('champions_league', 'sportmonks', 2::bigint, NULL::text, 'UEFA Champions League', TRUE),
      ('copa_do_brasil', 'sportmonks', 654::bigint, NULL::text, 'Copa do Brasil', TRUE),
      ('fifa_intercontinental_cup', 'sportmonks', 1452::bigint, NULL::text, 'FIFA Intercontinental Cup', TRUE),
      ('la_liga', 'sportmonks', 564::bigint, NULL::text, 'La Liga', TRUE),
      ('libertadores', 'sportmonks', 1122::bigint, NULL::text, 'Copa Libertadores', TRUE),
      ('ligue_1', 'sportmonks', 301::bigint, NULL::text, 'Ligue 1', TRUE),
      ('premier_league', 'sportmonks', 8::bigint, NULL::text, 'Premier League', TRUE),
      ('primeira_liga', 'sportmonks', 462::bigint, NULL::text, 'Liga Portugal', TRUE),
      ('serie_a_it', 'sportmonks', 384::bigint, NULL::text, 'Serie A', TRUE),
      ('sudamericana', 'sportmonks', 1116::bigint, NULL::text, 'Copa Sudamericana', TRUE),
      ('supercopa_do_brasil', 'sportmonks', 1798::bigint, NULL::text, 'Supercopa do Brasil', TRUE),
      ('fifa_world_cup_mens', 'fjelstul_worldcup', 7000547241627854950::bigint, NULL::text, 'Fjelstul World Cup Database', TRUE),
      ('african_cup_of_nations', 'transfermarkt', NULL::bigint, 'AFCN', 'Africa Cup of Nations', TRUE),
      ('brasileirao_a', 'transfermarkt', NULL::bigint, 'BRA1', 'Campeonato Brasileiro Série A', TRUE),
      ('champions_league', 'transfermarkt', NULL::bigint, 'CL', 'UEFA Champions League', TRUE),
      ('copa_america', 'transfermarkt', NULL::bigint, 'COPA', 'Copa América', TRUE),
      ('la_liga', 'transfermarkt', NULL::bigint, 'ES1', 'La Liga', TRUE),
      ('ligue_1', 'transfermarkt', NULL::bigint, 'FR1', 'Ligue 1', TRUE),
      ('major_league_soccer', 'transfermarkt', NULL::bigint, 'MLS1', 'Major League Soccer', TRUE),
      ('premier_league', 'transfermarkt', NULL::bigint, 'GB1', 'Premier League', TRUE),
      ('serie_a_it', 'transfermarkt', NULL::bigint, 'IT1', 'Serie A', TRUE),
      ('bundesliga', 'transfermarkt', NULL::bigint, 'L1', 'Bundesliga', TRUE),
      ('primeira_liga', 'transfermarkt', NULL::bigint, 'PO1', 'Liga Portugal', TRUE),
      ('brasileirao_a', 'eloratings', NULL::bigint, 'BRA', 'Brasileirão Série A', TRUE),
      ('bundesliga', 'eloratings', NULL::bigint, 'D1', 'Bundesliga', TRUE),
      ('premier_league', 'eloratings', NULL::bigint, 'E0', 'Premier League', TRUE),
      ('ligue_1', 'eloratings', NULL::bigint, 'F1', 'Ligue 1', TRUE),
      ('serie_a_it', 'eloratings', NULL::bigint, 'I1', 'Serie A', TRUE),
      ('primeira_liga', 'eloratings', NULL::bigint, 'P1', 'Primeira Liga', TRUE),
      ('la_liga', 'eloratings', NULL::bigint, 'SP1', 'La Liga', TRUE),
      ('major_league_soccer', 'eloratings', NULL::bigint, 'USA', 'Major League Soccer', TRUE)
  ) AS seeded (
    competition_key,
    provider,
    provider_league_id,
    provider_league_code,
    provider_name,
    is_active
  )
)
INSERT INTO control.competition_provider_map (
  competition_key,
  provider,
  provider_league_id,
  provider_league_code,
  provider_name,
  is_active
)
SELECT
  competition_key,
  provider,
  provider_league_id,
  provider_league_code,
  provider_name,
  is_active
FROM provider_seed
ON CONFLICT (competition_key, provider) DO UPDATE
SET
  provider_league_id = EXCLUDED.provider_league_id,
  provider_league_code = EXCLUDED.provider_league_code,
  provider_name = EXCLUDED.provider_name,
  is_active = EXCLUDED.is_active,
  updated_at = now();

-- migrate:down
DELETE FROM control.competition_provider_map
WHERE provider IN ('transfermarkt', 'eloratings')
   OR (provider = 'sportmonks' AND competition_key IN (
        'brasileirao_a',
        'brasileirao_b',
        'bundesliga',
        'champions_league',
        'copa_do_brasil',
        'fifa_intercontinental_cup',
        'la_liga',
        'libertadores',
        'ligue_1',
        'premier_league',
        'primeira_liga',
        'serie_a_it',
        'sudamericana',
        'supercopa_do_brasil'
      ));

DROP INDEX IF EXISTS uq_control_competition_provider_map_provider_league_code;

ALTER TABLE control.competition_provider_map
  DROP COLUMN IF EXISTS provider_league_code;
