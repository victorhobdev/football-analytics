-- migrate:up
WITH competition_seed AS (
  SELECT
    'fifa_world_cup_mens'::text AS competition_key,
    'FIFA Men''s World Cup'::text AS competition_name,
    'cup'::text AS competition_type,
    NULL::text AS country_name,
    'FIFA'::text AS confederation_name,
    NULL::smallint AS tier,
    TRUE AS is_active,
    60::integer AS display_priority
),
competition_upsert AS (
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
    updated_at = now()
  WHERE
    control.competitions.competition_name IS DISTINCT FROM EXCLUDED.competition_name
    OR control.competitions.competition_type IS DISTINCT FROM EXCLUDED.competition_type
    OR control.competitions.country_name IS DISTINCT FROM EXCLUDED.country_name
    OR control.competitions.confederation_name IS DISTINCT FROM EXCLUDED.confederation_name
    OR control.competitions.tier IS DISTINCT FROM EXCLUDED.tier
    OR control.competitions.is_active IS DISTINCT FROM EXCLUDED.is_active
    OR control.competitions.display_priority IS DISTINCT FROM EXCLUDED.display_priority
  RETURNING 1
),
provider_seed AS (
  SELECT
    'fifa_world_cup_mens'::text AS competition_key,
    'fjelstul_worldcup'::text AS provider,
    7000547241627854950::bigint AS provider_league_id,
    'Fjelstul World Cup Database'::text AS provider_name,
    TRUE AS is_active
),
provider_upsert AS (
  INSERT INTO control.competition_provider_map (
    competition_key,
    provider,
    provider_league_id,
    provider_name,
    is_active
  )
  SELECT
    competition_key,
    provider,
    provider_league_id,
    provider_name,
    is_active
  FROM provider_seed
  ON CONFLICT ON CONSTRAINT uq_control_competition_provider_map_provider_league DO UPDATE
  SET
    competition_key = EXCLUDED.competition_key,
    provider_name = EXCLUDED.provider_name,
    is_active = EXCLUDED.is_active,
    updated_at = now()
  WHERE
    control.competition_provider_map.competition_key IS DISTINCT FROM EXCLUDED.competition_key
    OR control.competition_provider_map.provider_name IS DISTINCT FROM EXCLUDED.provider_name
    OR control.competition_provider_map.is_active IS DISTINCT FROM EXCLUDED.is_active
  RETURNING 1
),
season_seed AS (
  SELECT *
  FROM (
    VALUES
      ('fifa_world_cup_mens', '1930', DATE '1930-07-13', DATE '1930-07-30', TRUE, 'fjelstul_worldcup', 7010363961417254171::bigint),
      ('fifa_world_cup_mens', '1934', DATE '1934-05-27', DATE '1934-06-10', TRUE, 'fjelstul_worldcup', 7010268944684493231::bigint),
      ('fifa_world_cup_mens', '1938', DATE '1938-06-04', DATE '1938-06-19', TRUE, 'fjelstul_worldcup', 7010361588066468969::bigint),
      ('fifa_world_cup_mens', '1950', DATE '1950-06-24', DATE '1950-07-16', TRUE, 'fjelstul_worldcup', 7010481487397766736::bigint),
      ('fifa_world_cup_mens', '1954', DATE '1954-06-16', DATE '1954-07-04', TRUE, 'fjelstul_worldcup', 7010012328535950159::bigint),
      ('fifa_world_cup_mens', '1958', DATE '1958-06-08', DATE '1958-06-29', TRUE, 'fjelstul_worldcup', 7010643098752757725::bigint),
      ('fifa_world_cup_mens', '1962', DATE '1962-05-30', DATE '1962-07-17', TRUE, 'fjelstul_worldcup', 7010705927365143123::bigint),
      ('fifa_world_cup_mens', '1966', DATE '1966-07-11', DATE '1966-07-30', TRUE, 'fjelstul_worldcup', 7010945525844326395::bigint),
      ('fifa_world_cup_mens', '1970', DATE '1970-05-31', DATE '1970-06-21', TRUE, 'fjelstul_worldcup', 7010875673558868434::bigint),
      ('fifa_world_cup_mens', '1974', DATE '1974-06-13', DATE '1974-07-07', TRUE, 'fjelstul_worldcup', 7010895881645964889::bigint),
      ('fifa_world_cup_mens', '1978', DATE '1978-06-01', DATE '1978-06-25', TRUE, 'fjelstul_worldcup', 7010098132803142088::bigint),
      ('fifa_world_cup_mens', '1982', DATE '1982-06-13', DATE '1982-07-11', TRUE, 'fjelstul_worldcup', 7010164493588097772::bigint),
      ('fifa_world_cup_mens', '1986', DATE '1986-05-31', DATE '1986-06-29', TRUE, 'fjelstul_worldcup', 7010026637973488437::bigint),
      ('fifa_world_cup_mens', '1990', DATE '1990-06-08', DATE '1990-07-08', TRUE, 'fjelstul_worldcup', 7010980284647633089::bigint),
      ('fifa_world_cup_mens', '1994', DATE '1994-06-17', DATE '1994-07-17', TRUE, 'fjelstul_worldcup', 7010907156475866125::bigint),
      ('fifa_world_cup_mens', '1998', DATE '1998-06-10', DATE '1998-07-12', TRUE, 'fjelstul_worldcup', 7010704626742941378::bigint),
      ('fifa_world_cup_mens', '2002', DATE '2002-05-31', DATE '2002-06-30', TRUE, 'fjelstul_worldcup', 7010986552379119332::bigint),
      ('fifa_world_cup_mens', '2006', DATE '2006-06-09', DATE '2006-07-09', TRUE, 'fjelstul_worldcup', 7010166250031297487::bigint),
      ('fifa_world_cup_mens', '2010', DATE '2010-06-11', DATE '2010-07-11', TRUE, 'fjelstul_worldcup', 7010781933006015485::bigint),
      ('fifa_world_cup_mens', '2014', DATE '2014-06-12', DATE '2014-07-13', TRUE, 'fjelstul_worldcup', 7010763311456970254::bigint),
      ('fifa_world_cup_mens', '2018', DATE '2018-06-14', DATE '2018-07-15', TRUE, 'fjelstul_worldcup', 7010020205385683794::bigint),
      ('fifa_world_cup_mens', '2022', DATE '2022-11-20', DATE '2022-12-18', TRUE, 'fjelstul_worldcup', 7010420829110427099::bigint)
  ) AS seeded (
    competition_key,
    season_label,
    season_start_date,
    season_end_date,
    is_closed,
    provider,
    provider_season_id
  )
),
season_catalog_upsert AS (
  INSERT INTO control.season_catalog (
    competition_key,
    season_label,
    season_start_date,
    season_end_date,
    is_closed,
    provider,
    provider_season_id
  )
  SELECT
    competition_key,
    season_label,
    season_start_date,
    season_end_date,
    is_closed,
    provider,
    provider_season_id
  FROM season_seed
  ON CONFLICT (competition_key, season_label, provider) DO UPDATE
  SET
    season_start_date = EXCLUDED.season_start_date,
    season_end_date = EXCLUDED.season_end_date,
    is_closed = EXCLUDED.is_closed,
    provider_season_id = EXCLUDED.provider_season_id,
    updated_at = now()
  WHERE
    control.season_catalog.season_start_date IS DISTINCT FROM EXCLUDED.season_start_date
    OR control.season_catalog.season_end_date IS DISTINCT FROM EXCLUDED.season_end_date
    OR control.season_catalog.is_closed IS DISTINCT FROM EXCLUDED.is_closed
    OR control.season_catalog.provider_season_id IS DISTINCT FROM EXCLUDED.provider_season_id
  RETURNING 1
),
raw_league_seed AS (
  SELECT
    'fjelstul_worldcup'::text AS provider,
    7000547241627854950::bigint AS league_id,
    'FIFA Men''s World Cup'::text AS league_name,
    NULL::bigint AS country_id,
    jsonb_build_object(
      'seed_type', 'world_cup_catalog_seed',
      'source_name', 'fjelstul_worldcup',
      'source_dataset', 'tournaments.csv',
      'competition_name', 'FIFA Men''s World Cup',
      'competition_scope', '1930-2022'
    ) AS payload,
    'world_cup_catalog_seed'::text AS ingested_run,
    7000547241627854950::bigint AS provider_league_id,
    'fifa_world_cup_mens'::text AS competition_key,
    'cup'::text AS competition_type,
    now() AS ingested_at,
    'world_cup_catalog_seed'::text AS source_run_id
),
raw_league_upsert AS (
  INSERT INTO raw.competition_leagues (
    provider,
    league_id,
    league_name,
    country_id,
    payload,
    ingested_run,
    provider_league_id,
    competition_key,
    competition_type,
    ingested_at,
    source_run_id
  )
  SELECT
    provider,
    league_id,
    league_name,
    country_id,
    payload,
    ingested_run,
    provider_league_id,
    competition_key,
    competition_type,
    ingested_at,
    source_run_id
  FROM raw_league_seed
  ON CONFLICT (provider, league_id) DO UPDATE
  SET
    league_name = EXCLUDED.league_name,
    country_id = EXCLUDED.country_id,
    payload = EXCLUDED.payload,
    ingested_run = EXCLUDED.ingested_run,
    provider_league_id = EXCLUDED.provider_league_id,
    competition_key = EXCLUDED.competition_key,
    competition_type = EXCLUDED.competition_type,
    ingested_at = EXCLUDED.ingested_at,
    source_run_id = EXCLUDED.source_run_id,
    updated_at = now()
  WHERE
    raw.competition_leagues.league_name IS DISTINCT FROM EXCLUDED.league_name
    OR raw.competition_leagues.country_id IS DISTINCT FROM EXCLUDED.country_id
    OR raw.competition_leagues.payload IS DISTINCT FROM EXCLUDED.payload
    OR raw.competition_leagues.ingested_run IS DISTINCT FROM EXCLUDED.ingested_run
    OR raw.competition_leagues.provider_league_id IS DISTINCT FROM EXCLUDED.provider_league_id
    OR raw.competition_leagues.competition_key IS DISTINCT FROM EXCLUDED.competition_key
    OR raw.competition_leagues.competition_type IS DISTINCT FROM EXCLUDED.competition_type
    OR raw.competition_leagues.ingested_at IS DISTINCT FROM EXCLUDED.ingested_at
    OR raw.competition_leagues.source_run_id IS DISTINCT FROM EXCLUDED.source_run_id
  RETURNING 1
),
raw_season_seed AS (
  SELECT *
  FROM (
    VALUES
      ('fjelstul_worldcup', 7010363961417254171::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1930', 7010363961417254171::bigint, 1930::integer, '1930 FIFA Men''s World Cup', DATE '1930-07-13', DATE '1930-07-30', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1930", "tournament_id": "WC-1930", "tournament_name": "1930 FIFA Men''s World Cup", "host_country": "Uruguay", "count_teams": 13, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": false, "semi_finals": true, "third_place_match": false, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010268944684493231::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1934', 7010268944684493231::bigint, 1934::integer, '1934 FIFA Men''s World Cup', DATE '1934-05-27', DATE '1934-06-10', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1934", "tournament_id": "WC-1934", "tournament_name": "1934 FIFA Men''s World Cup", "host_country": "Italy", "count_teams": 16, "format_flags": {"group_stage": false, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010361588066468969::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1938', 7010361588066468969::bigint, 1938::integer, '1938 FIFA Men''s World Cup', DATE '1938-06-04', DATE '1938-06-19', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1938", "tournament_id": "WC-1938", "tournament_name": "1938 FIFA Men''s World Cup", "host_country": "France", "count_teams": 15, "format_flags": {"group_stage": false, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010481487397766736::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1950', 7010481487397766736::bigint, 1950::integer, '1950 FIFA Men''s World Cup', DATE '1950-06-24', DATE '1950-07-16', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1950", "tournament_id": "WC-1950", "tournament_name": "1950 FIFA Men''s World Cup", "host_country": "Brazil", "count_teams": 13, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": true, "round_of_16": false, "quarter_finals": false, "semi_finals": false, "third_place_match": false, "final": false}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010012328535950159::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1954', 7010012328535950159::bigint, 1954::integer, '1954 FIFA Men''s World Cup', DATE '1954-06-16', DATE '1954-07-04', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1954", "tournament_id": "WC-1954", "tournament_name": "1954 FIFA Men''s World Cup", "host_country": "Switzerland", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010643098752757725::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1958', 7010643098752757725::bigint, 1958::integer, '1958 FIFA Men''s World Cup', DATE '1958-06-08', DATE '1958-06-29', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1958", "tournament_id": "WC-1958", "tournament_name": "1958 FIFA Men''s World Cup", "host_country": "Sweden", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010705927365143123::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1962', 7010705927365143123::bigint, 1962::integer, '1962 FIFA Men''s World Cup', DATE '1962-05-30', DATE '1962-07-17', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1962", "tournament_id": "WC-1962", "tournament_name": "1962 FIFA Men''s World Cup", "host_country": "Chile", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010945525844326395::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1966', 7010945525844326395::bigint, 1966::integer, '1966 FIFA Men''s World Cup', DATE '1966-07-11', DATE '1966-07-30', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1966", "tournament_id": "WC-1966", "tournament_name": "1966 FIFA Men''s World Cup", "host_country": "England", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010875673558868434::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1970', 7010875673558868434::bigint, 1970::integer, '1970 FIFA Men''s World Cup', DATE '1970-05-31', DATE '1970-06-21', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1970", "tournament_id": "WC-1970", "tournament_name": "1970 FIFA Men''s World Cup", "host_country": "Mexico", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": false, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010895881645964889::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1974', 7010895881645964889::bigint, 1974::integer, '1974 FIFA Men''s World Cup', DATE '1974-06-13', DATE '1974-07-07', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1974", "tournament_id": "WC-1974", "tournament_name": "1974 FIFA Men''s World Cup", "host_country": "West Germany", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": true, "final_round": false, "round_of_16": false, "quarter_finals": false, "semi_finals": false, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010098132803142088::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1978', 7010098132803142088::bigint, 1978::integer, '1978 FIFA Men''s World Cup', DATE '1978-06-01', DATE '1978-06-25', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1978", "tournament_id": "WC-1978", "tournament_name": "1978 FIFA Men''s World Cup", "host_country": "Argentina", "count_teams": 16, "format_flags": {"group_stage": true, "second_group_stage": true, "final_round": false, "round_of_16": false, "quarter_finals": false, "semi_finals": false, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010164493588097772::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1982', 7010164493588097772::bigint, 1982::integer, '1982 FIFA Men''s World Cup', DATE '1982-06-13', DATE '1982-07-11', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1982", "tournament_id": "WC-1982", "tournament_name": "1982 FIFA Men''s World Cup", "host_country": "Spain", "count_teams": 24, "format_flags": {"group_stage": true, "second_group_stage": true, "final_round": false, "round_of_16": false, "quarter_finals": false, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010026637973488437::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1986', 7010026637973488437::bigint, 1986::integer, '1986 FIFA Men''s World Cup', DATE '1986-05-31', DATE '1986-06-29', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1986", "tournament_id": "WC-1986", "tournament_name": "1986 FIFA Men''s World Cup", "host_country": "Mexico", "count_teams": 24, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010980284647633089::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1990', 7010980284647633089::bigint, 1990::integer, '1990 FIFA Men''s World Cup', DATE '1990-06-08', DATE '1990-07-08', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1990", "tournament_id": "WC-1990", "tournament_name": "1990 FIFA Men''s World Cup", "host_country": "Italy", "count_teams": 24, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010907156475866125::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1994', 7010907156475866125::bigint, 1994::integer, '1994 FIFA Men''s World Cup', DATE '1994-06-17', DATE '1994-07-17', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1994", "tournament_id": "WC-1994", "tournament_name": "1994 FIFA Men''s World Cup", "host_country": "United States", "count_teams": 24, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010704626742941378::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '1998', 7010704626742941378::bigint, 1998::integer, '1998 FIFA Men''s World Cup', DATE '1998-06-10', DATE '1998-07-12', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__1998", "tournament_id": "WC-1998", "tournament_name": "1998 FIFA Men''s World Cup", "host_country": "France", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010986552379119332::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2002', 7010986552379119332::bigint, 2002::integer, '2002 FIFA Men''s World Cup', DATE '2002-05-31', DATE '2002-06-30', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2002", "tournament_id": "WC-2002", "tournament_name": "2002 FIFA Men''s World Cup", "host_country": "Korea, Japan", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010166250031297487::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2006', 7010166250031297487::bigint, 2006::integer, '2006 FIFA Men''s World Cup', DATE '2006-06-09', DATE '2006-07-09', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2006", "tournament_id": "WC-2006", "tournament_name": "2006 FIFA Men''s World Cup", "host_country": "Germany", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010781933006015485::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2010', 7010781933006015485::bigint, 2010::integer, '2010 FIFA Men''s World Cup', DATE '2010-06-11', DATE '2010-07-11', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2010", "tournament_id": "WC-2010", "tournament_name": "2010 FIFA Men''s World Cup", "host_country": "South Africa", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010763311456970254::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2014', 7010763311456970254::bigint, 2014::integer, '2014 FIFA Men''s World Cup', DATE '2014-06-12', DATE '2014-07-13', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2014", "tournament_id": "WC-2014", "tournament_name": "2014 FIFA Men''s World Cup", "host_country": "Brazil", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010020205385683794::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2018', 7010020205385683794::bigint, 2018::integer, '2018 FIFA Men''s World Cup', DATE '2018-06-14', DATE '2018-07-15', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2018", "tournament_id": "WC-2018", "tournament_name": "2018 FIFA Men''s World Cup", "host_country": "Russia", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed'),
      ('fjelstul_worldcup', 7010420829110427099::bigint, 7000547241627854950::bigint, 7000547241627854950::bigint, 'fifa_world_cup_mens', '2022', 7010420829110427099::bigint, 2022::integer, '2022 FIFA Men''s World Cup', DATE '2022-11-20', DATE '2022-12-18', '{"seed_type": "world_cup_catalog_seed", "source_name": "fjelstul_worldcup", "source_dataset": "tournaments.csv", "edition_key": "fifa_world_cup_mens__2022", "tournament_id": "WC-2022", "tournament_name": "2022 FIFA Men''s World Cup", "host_country": "Qatar", "count_teams": 32, "format_flags": {"group_stage": true, "second_group_stage": false, "final_round": false, "round_of_16": true, "quarter_finals": true, "semi_finals": true, "third_place_match": true, "final": true}}'::jsonb, 'world_cup_catalog_seed', 'world_cup_catalog_seed')
  ) AS seeded (
    provider,
    season_id,
    league_id,
    provider_league_id,
    competition_key,
    season_label,
    provider_season_id,
    season_year,
    season_name,
    starting_at,
    ending_at,
    payload,
    ingested_run,
    source_run_id
  )
)
INSERT INTO raw.competition_seasons (
  provider,
  season_id,
  league_id,
  provider_league_id,
  competition_key,
  season_label,
  provider_season_id,
  season_year,
  season_name,
  starting_at,
  ending_at,
  payload,
  ingested_run,
  ingested_at,
  source_run_id
)
SELECT
  provider,
  season_id,
  league_id,
  provider_league_id,
  competition_key,
  season_label,
  provider_season_id,
  season_year,
  season_name,
  starting_at,
  ending_at,
  payload,
  ingested_run,
  now(),
  source_run_id
FROM raw_season_seed
ON CONFLICT (provider, season_id) DO UPDATE
SET
  league_id = EXCLUDED.league_id,
  provider_league_id = EXCLUDED.provider_league_id,
  competition_key = EXCLUDED.competition_key,
  season_label = EXCLUDED.season_label,
  provider_season_id = EXCLUDED.provider_season_id,
  season_year = EXCLUDED.season_year,
  season_name = EXCLUDED.season_name,
  starting_at = EXCLUDED.starting_at,
  ending_at = EXCLUDED.ending_at,
  payload = EXCLUDED.payload,
  ingested_run = EXCLUDED.ingested_run,
  ingested_at = EXCLUDED.ingested_at,
  source_run_id = EXCLUDED.source_run_id,
  updated_at = now()
WHERE
  raw.competition_seasons.league_id IS DISTINCT FROM EXCLUDED.league_id
  OR raw.competition_seasons.provider_league_id IS DISTINCT FROM EXCLUDED.provider_league_id
  OR raw.competition_seasons.competition_key IS DISTINCT FROM EXCLUDED.competition_key
  OR raw.competition_seasons.season_label IS DISTINCT FROM EXCLUDED.season_label
  OR raw.competition_seasons.provider_season_id IS DISTINCT FROM EXCLUDED.provider_season_id
  OR raw.competition_seasons.season_year IS DISTINCT FROM EXCLUDED.season_year
  OR raw.competition_seasons.season_name IS DISTINCT FROM EXCLUDED.season_name
  OR raw.competition_seasons.starting_at IS DISTINCT FROM EXCLUDED.starting_at
  OR raw.competition_seasons.ending_at IS DISTINCT FROM EXCLUDED.ending_at
  OR raw.competition_seasons.payload IS DISTINCT FROM EXCLUDED.payload
  OR raw.competition_seasons.ingested_run IS DISTINCT FROM EXCLUDED.ingested_run
  OR raw.competition_seasons.source_run_id IS DISTINCT FROM EXCLUDED.source_run_id;

-- migrate:down
DELETE FROM raw.competition_seasons
WHERE provider = 'fjelstul_worldcup'
  AND competition_key = 'fifa_world_cup_mens';

DELETE FROM raw.competition_leagues
WHERE provider = 'fjelstul_worldcup'
  AND competition_key = 'fifa_world_cup_mens';

DELETE FROM control.season_catalog
WHERE competition_key = 'fifa_world_cup_mens'
  AND provider = 'fjelstul_worldcup';

DELETE FROM control.competition_provider_map
WHERE competition_key = 'fifa_world_cup_mens'
  AND provider = 'fjelstul_worldcup';

DELETE FROM control.competitions
WHERE competition_key = 'fifa_world_cup_mens';
