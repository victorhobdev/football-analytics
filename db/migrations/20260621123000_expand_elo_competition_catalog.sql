-- migrate:up
CREATE SCHEMA IF NOT EXISTS control;

WITH competition_seed AS (
  SELECT *
  FROM (
    VALUES
      ('argentina_primera_division', 'Primera División Argentina', 'league', 'Argentina', 'CONMEBOL', 1::smallint, TRUE, 210),
      ('austrian_bundesliga', 'Bundesliga Austríaca', 'league', 'Áustria', 'UEFA', 1::smallint, TRUE, 220),
      ('belgian_pro_league', 'Belgian Pro League', 'league', 'Bélgica', 'UEFA', 1::smallint, TRUE, 230),
      ('chinese_super_league', 'Chinese Super League', 'league', 'China', 'AFC', 1::smallint, TRUE, 240),
      ('danish_superliga', 'Superliga Dinamarquesa', 'league', 'Dinamarca', 'UEFA', 1::smallint, TRUE, 250),
      ('efl_championship', 'EFL Championship', 'league', 'Inglaterra', 'UEFA', 2::smallint, TRUE, 260),
      ('efl_league_one', 'EFL League One', 'league', 'Inglaterra', 'UEFA', 3::smallint, TRUE, 270),
      ('efl_league_two', 'EFL League Two', 'league', 'Inglaterra', 'UEFA', 4::smallint, TRUE, 280),
      ('eredivisie', 'Eredivisie', 'league', 'Holanda', 'UEFA', 1::smallint, TRUE, 290),
      ('finnish_veikkausliiga', 'Veikkausliiga', 'league', 'Finlândia', 'UEFA', 1::smallint, TRUE, 300),
      ('greek_super_league', 'Super League Grega', 'league', 'Grécia', 'UEFA', 1::smallint, TRUE, 310),
      ('j1_league', 'J1 League', 'league', 'Japão', 'AFC', 1::smallint, TRUE, 320),
      ('liga_mx', 'Liga MX', 'league', 'México', 'CONCACAF', 1::smallint, TRUE, 330),
      ('norwegian_eliteserien', 'Eliteserien', 'league', 'Noruega', 'UEFA', 1::smallint, TRUE, 340),
      ('polish_ekstraklasa', 'Ekstraklasa', 'league', 'Polônia', 'UEFA', 1::smallint, TRUE, 350),
      ('romanian_superliga', 'SuperLiga Romena', 'league', 'Romênia', 'UEFA', 1::smallint, TRUE, 360),
      ('russian_premier_league', 'Premier Liga Russa', 'league', 'Rússia', 'UEFA', 1::smallint, TRUE, 370),
      ('scottish_championship', 'Scottish Championship', 'league', 'Escócia', 'UEFA', 2::smallint, TRUE, 380),
      ('scottish_league_one', 'Scottish League One', 'league', 'Escócia', 'UEFA', 3::smallint, TRUE, 390),
      ('scottish_league_two', 'Scottish League Two', 'league', 'Escócia', 'UEFA', 4::smallint, TRUE, 400),
      ('scottish_premiership', 'Scottish Premiership', 'league', 'Escócia', 'UEFA', 1::smallint, TRUE, 410),
      ('segunda_division', 'Segunda División', 'league', 'Espanha', 'UEFA', 2::smallint, TRUE, 420),
      ('serie_b_it', 'Serie B', 'league', 'Itália', 'UEFA', 2::smallint, TRUE, 430),
      ('super_lig_turkey', 'Süper Lig', 'league', 'Turquia', 'UEFA', 1::smallint, TRUE, 440),
      ('swedish_allsvenskan', 'Allsvenskan', 'league', 'Suécia', 'UEFA', 1::smallint, TRUE, 450),
      ('swiss_super_league', 'Swiss Super League', 'league', 'Suíça', 'UEFA', 1::smallint, TRUE, 460),
      ('league_of_ireland', 'League of Ireland', 'league', 'Irlanda', 'UEFA', 1::smallint, TRUE, 470),
      ('ligue_2', 'Ligue 2', 'league', 'França', 'UEFA', 2::smallint, TRUE, 480),
      ('bundesliga_2', '2. Bundesliga', 'league', 'Alemanha', 'UEFA', 2::smallint, TRUE, 490),
      ('copa_america_ec', 'Copa América / CONMEBOL EC', 'continental_cup', 'América do Sul', 'CONMEBOL', NULL::smallint, TRUE, 500)
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
      ('argentina_primera_division', 'eloratings', NULL::bigint, 'ARG', 'Primera División Argentina', TRUE),
      ('austrian_bundesliga', 'eloratings', NULL::bigint, 'AUT', 'Bundesliga Austríaca', TRUE),
      ('belgian_pro_league', 'eloratings', NULL::bigint, 'B1', 'Belgian Pro League', TRUE),
      ('chinese_super_league', 'eloratings', NULL::bigint, 'CHN', 'Chinese Super League', TRUE),
      ('danish_superliga', 'eloratings', NULL::bigint, 'DEN', 'Superliga Dinamarquesa', TRUE),
      ('efl_championship', 'eloratings', NULL::bigint, 'E1', 'EFL Championship', TRUE),
      ('efl_league_one', 'eloratings', NULL::bigint, 'E2', 'EFL League One', TRUE),
      ('efl_league_two', 'eloratings', NULL::bigint, 'E3', 'EFL League Two', TRUE),
      ('eredivisie', 'eloratings', NULL::bigint, 'N1', 'Eredivisie', TRUE),
      ('finnish_veikkausliiga', 'eloratings', NULL::bigint, 'FIN', 'Veikkausliiga', TRUE),
      ('greek_super_league', 'eloratings', NULL::bigint, 'G1', 'Super League Grega', TRUE),
      ('j1_league', 'eloratings', NULL::bigint, 'JAP', 'J1 League', TRUE),
      ('liga_mx', 'eloratings', NULL::bigint, 'MEX', 'Liga MX', TRUE),
      ('norwegian_eliteserien', 'eloratings', NULL::bigint, 'NOR', 'Eliteserien', TRUE),
      ('polish_ekstraklasa', 'eloratings', NULL::bigint, 'POL', 'Ekstraklasa', TRUE),
      ('romanian_superliga', 'eloratings', NULL::bigint, 'ROM', 'SuperLiga Romena', TRUE),
      ('russian_premier_league', 'eloratings', NULL::bigint, 'RUS', 'Premier Liga Russa', TRUE),
      ('scottish_championship', 'eloratings', NULL::bigint, 'SC1', 'Scottish Championship', TRUE),
      ('scottish_league_one', 'eloratings', NULL::bigint, 'SC2', 'Scottish League One', TRUE),
      ('scottish_league_two', 'eloratings', NULL::bigint, 'SC3', 'Scottish League Two', TRUE),
      ('scottish_premiership', 'eloratings', NULL::bigint, 'SC0', 'Scottish Premiership', TRUE),
      ('segunda_division', 'eloratings', NULL::bigint, 'SP2', 'Segunda División', TRUE),
      ('serie_b_it', 'eloratings', NULL::bigint, 'I2', 'Serie B', TRUE),
      ('super_lig_turkey', 'eloratings', NULL::bigint, 'T1', 'Süper Lig', TRUE),
      ('swedish_allsvenskan', 'eloratings', NULL::bigint, 'SWE', 'Allsvenskan', TRUE),
      ('swiss_super_league', 'eloratings', NULL::bigint, 'SUI', 'Swiss Super League', TRUE),
      ('league_of_ireland', 'eloratings', NULL::bigint, 'IRL', 'League of Ireland', TRUE),
      ('ligue_2', 'eloratings', NULL::bigint, 'F2', 'Ligue 2', TRUE),
      ('bundesliga_2', 'eloratings', NULL::bigint, 'D2', '2. Bundesliga', TRUE),
      ('copa_america_ec', 'eloratings', NULL::bigint, 'EC', 'Copa América / CONMEBOL EC', TRUE)
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
WHERE provider = 'eloratings'
  AND provider_league_code IN (
    'ARG', 'AUT', 'B1', 'CHN', 'DEN', 'E1', 'E2', 'E3', 'N1', 'FIN',
    'G1', 'JAP', 'MEX', 'NOR', 'POL', 'ROM', 'RUS', 'SC1', 'SC2',
    'SC3', 'SC0', 'SP2', 'I2', 'T1', 'SWE', 'SUI', 'IRL', 'F2',
    'D2', 'EC'
  );

DELETE FROM control.competitions
WHERE competition_key IN (
  'argentina_primera_division',
  'austrian_bundesliga',
  'belgian_pro_league',
  'chinese_super_league',
  'danish_superliga',
  'efl_championship',
  'efl_league_one',
  'efl_league_two',
  'eredivisie',
  'finnish_veikkausliiga',
  'greek_super_league',
  'j1_league',
  'liga_mx',
  'norwegian_eliteserien',
  'polish_ekstraklasa',
  'romanian_superliga',
  'russian_premier_league',
  'scottish_championship',
  'scottish_league_one',
  'scottish_league_two',
  'scottish_premiership',
  'segunda_division',
  'serie_b_it',
  'super_lig_turkey',
  'swedish_allsvenskan',
  'swiss_super_league',
  'league_of_ireland',
  'ligue_2',
  'bundesliga_2',
  'copa_america_ec'
);
