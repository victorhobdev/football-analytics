-- migrate:up
INSERT INTO control.competitions (
  competition_key,
  competition_name,
  competition_type,
  country_name,
  confederation_name,
  tier,
  is_active,
  display_priority
) VALUES (
  'fifa_world_cup_mens',
  'Copa do Mundo FIFA (Masculino)',
  'cup',
  NULL,
  'FIFA',
  1,
  TRUE,
  10
)
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

INSERT INTO control.competition_provider_map (
  competition_key,
  provider,
  provider_league_id,
  provider_name,
  is_active
) VALUES (
  'fifa_world_cup_mens',
  'fjelstul_worldcup',
  7000547241627854950,
  'Fjelstul World Cup Database',
  TRUE
)
ON CONFLICT (competition_key, provider) DO UPDATE
SET
  provider_league_id = EXCLUDED.provider_league_id,
  provider_name = EXCLUDED.provider_name,
  is_active = EXCLUDED.is_active,
  updated_at = now();

INSERT INTO control.season_catalog (
  competition_key,
  season_label,
  season_start_date,
  season_end_date,
  is_closed,
  provider,
  provider_season_id
)
VALUES
  ('fifa_world_cup_mens', '1930', DATE '1930-07-13', DATE '1930-07-30', TRUE, 'fjelstul_worldcup', 7010363961417254171),
  ('fifa_world_cup_mens', '1934', DATE '1934-05-27', DATE '1934-06-10', TRUE, 'fjelstul_worldcup', 7010268944684493231),
  ('fifa_world_cup_mens', '1938', DATE '1938-06-04', DATE '1938-06-19', TRUE, 'fjelstul_worldcup', 7010361588066468969),
  ('fifa_world_cup_mens', '1950', DATE '1950-06-24', DATE '1950-07-16', TRUE, 'fjelstul_worldcup', 7010481487397766736),
  ('fifa_world_cup_mens', '1954', DATE '1954-06-16', DATE '1954-07-04', TRUE, 'fjelstul_worldcup', 7010012328535950159),
  ('fifa_world_cup_mens', '1958', DATE '1958-06-08', DATE '1958-06-29', TRUE, 'fjelstul_worldcup', 7010643098752757725),
  ('fifa_world_cup_mens', '1962', DATE '1962-05-30', DATE '1962-07-17', TRUE, 'fjelstul_worldcup', 7010705927365143123),
  ('fifa_world_cup_mens', '1966', DATE '1966-07-11', DATE '1966-07-30', TRUE, 'fjelstul_worldcup', 7010945525844326395),
  ('fifa_world_cup_mens', '1970', DATE '1970-05-31', DATE '1970-06-21', TRUE, 'fjelstul_worldcup', 7010875673558868434),
  ('fifa_world_cup_mens', '1974', DATE '1974-06-13', DATE '1974-07-07', TRUE, 'fjelstul_worldcup', 7010895881645964889),
  ('fifa_world_cup_mens', '1978', DATE '1978-06-01', DATE '1978-06-25', TRUE, 'fjelstul_worldcup', 7010098132803142088),
  ('fifa_world_cup_mens', '1982', DATE '1982-06-13', DATE '1982-07-11', TRUE, 'fjelstul_worldcup', 7010164493588097772),
  ('fifa_world_cup_mens', '1986', DATE '1986-05-31', DATE '1986-06-29', TRUE, 'fjelstul_worldcup', 7010026637973488437),
  ('fifa_world_cup_mens', '1990', DATE '1990-06-08', DATE '1990-07-08', TRUE, 'fjelstul_worldcup', 7010980284647633089),
  ('fifa_world_cup_mens', '1994', DATE '1994-06-17', DATE '1994-07-17', TRUE, 'fjelstul_worldcup', 7010907156475866125),
  ('fifa_world_cup_mens', '1998', DATE '1998-06-10', DATE '1998-07-12', TRUE, 'fjelstul_worldcup', 7010704626742941378),
  ('fifa_world_cup_mens', '2002', DATE '2002-05-31', DATE '2002-06-30', TRUE, 'fjelstul_worldcup', 7010986552379119332),
  ('fifa_world_cup_mens', '2006', DATE '2006-06-09', DATE '2006-07-09', TRUE, 'fjelstul_worldcup', 7010166250031297487),
  ('fifa_world_cup_mens', '2010', DATE '2010-06-11', DATE '2010-07-11', TRUE, 'fjelstul_worldcup', 7010781933006015485),
  ('fifa_world_cup_mens', '2014', DATE '2014-06-12', DATE '2014-07-13', TRUE, 'fjelstul_worldcup', 7010763311456970254),
  ('fifa_world_cup_mens', '2018', DATE '2018-06-14', DATE '2018-07-15', TRUE, 'fjelstul_worldcup', 7010020205385683794),
  ('fifa_world_cup_mens', '2022', DATE '2022-11-20', DATE '2022-12-18', TRUE, 'fjelstul_worldcup', 7010420829110427099)
ON CONFLICT (competition_key, season_label, provider) DO UPDATE
SET
  season_start_date = EXCLUDED.season_start_date,
  season_end_date = EXCLUDED.season_end_date,
  is_closed = EXCLUDED.is_closed,
  provider_season_id = EXCLUDED.provider_season_id,
  updated_at = now();

-- migrate:down
DELETE FROM control.season_catalog
WHERE competition_key = 'fifa_world_cup_mens'
  AND provider = 'fjelstul_worldcup';

DELETE FROM control.competition_provider_map
WHERE competition_key = 'fifa_world_cup_mens'
  AND provider = 'fjelstul_worldcup';

DELETE FROM control.competitions
WHERE competition_key = 'fifa_world_cup_mens';
