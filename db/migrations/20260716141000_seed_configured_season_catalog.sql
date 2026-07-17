-- migrate:up

INSERT INTO control.season_catalog (
  competition_key, season_label, provider, is_closed
)
VALUES
  ('champions_league', '2020_21', 'manual_config', true),
  ('champions_league', '2021_22', 'manual_config', true),
  ('champions_league', '2022_23', 'manual_config', true),
  ('champions_league', '2023_24', 'manual_config', true),
  ('champions_league', '2024_25', 'manual_config', true),
  ('copa_do_brasil', '2021', 'manual_config', true),
  ('copa_do_brasil', '2022', 'manual_config', true),
  ('copa_do_brasil', '2023', 'manual_config', true),
  ('copa_do_brasil', '2024', 'manual_config', true),
  ('copa_do_brasil', '2025', 'manual_config', true),
  ('libertadores', '2021', 'manual_config', true),
  ('libertadores', '2022', 'manual_config', true),
  ('libertadores', '2023', 'manual_config', true),
  ('libertadores', '2024', 'manual_config', true),
  ('libertadores', '2025', 'manual_config', true)
ON CONFLICT (competition_key, season_label, provider) DO NOTHING;

-- migrate:down

DELETE FROM control.season_catalog
WHERE provider = 'manual_config'
  AND (competition_key, season_label) IN (
    ('champions_league', '2020_21'),
    ('champions_league', '2021_22'),
    ('champions_league', '2022_23'),
    ('champions_league', '2023_24'),
    ('champions_league', '2024_25'),
    ('copa_do_brasil', '2021'),
    ('copa_do_brasil', '2022'),
    ('copa_do_brasil', '2023'),
    ('copa_do_brasil', '2024'),
    ('copa_do_brasil', '2025'),
    ('libertadores', '2021'),
    ('libertadores', '2022'),
    ('libertadores', '2023'),
    ('libertadores', '2024'),
    ('libertadores', '2025')
  );
