-- migrate:up
CREATE TABLE IF NOT EXISTS mart.team_identity_alias (
  team_identity_alias_id BIGSERIAL PRIMARY KEY,
  team_id                BIGINT NOT NULL,
  alias_source           TEXT NOT NULL,
  external_team_id       TEXT,
  alias_name             TEXT,
  alias_name_normalized  TEXT,
  match_method           TEXT NOT NULL,
  confidence             NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
  status                 TEXT NOT NULL DEFAULT 'active',
  is_active              BOOLEAN NOT NULL DEFAULT true,
  notes                  TEXT,
  payload                JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_team_identity_alias_status CHECK (status IN ('active', 'inactive', 'review_needed')),
  CONSTRAINT ck_team_identity_alias_identifier CHECK (external_team_id IS NOT NULL OR alias_name IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_team_identity_alias_source_external_active
  ON mart.team_identity_alias (alias_source, external_team_id)
  WHERE is_active AND external_team_id IS NOT NULL;

WITH ranked_team_aliases AS (
  SELECT
    team_identity_alias_id,
    row_number() OVER (
      PARTITION BY team_id, alias_source, alias_name_normalized
      ORDER BY team_identity_alias_id
    ) AS rn
  FROM mart.team_identity_alias
  WHERE alias_name_normalized IS NOT NULL
)
DELETE FROM mart.team_identity_alias a
USING ranked_team_aliases ranked
WHERE a.team_identity_alias_id = ranked.team_identity_alias_id
  AND ranked.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_team_identity_alias_source_name_team_active
  ON mart.team_identity_alias (team_id, alias_source, alias_name_normalized)
  WHERE is_active AND alias_name_normalized IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_team_identity_alias_name_active
  ON mart.team_identity_alias (alias_name_normalized)
  WHERE is_active AND alias_name_normalized IS NOT NULL;

CREATE TABLE IF NOT EXISTS mart.coach_identity_alias (
  coach_identity_alias_id     BIGSERIAL PRIMARY KEY,
  canonical_coach_identity_id BIGINT NOT NULL REFERENCES mart.coach_identity(coach_identity_id),
  alias_coach_identity_id     BIGINT REFERENCES mart.coach_identity(coach_identity_id),
  alias_source                TEXT NOT NULL,
  external_person_id          TEXT,
  alias_name                  TEXT,
  alias_name_normalized       TEXT,
  match_method                TEXT NOT NULL,
  confidence                  NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
  status                      TEXT NOT NULL DEFAULT 'active',
  is_active                   BOOLEAN NOT NULL DEFAULT true,
  notes                       TEXT,
  payload                     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_coach_identity_alias_status CHECK (status IN ('active', 'inactive', 'review_needed')),
  CONSTRAINT ck_coach_identity_alias_identifier CHECK (
    alias_coach_identity_id IS NOT NULL
    OR external_person_id IS NOT NULL
    OR alias_name IS NOT NULL
  ),
  CONSTRAINT ck_coach_identity_alias_not_self CHECK (
    alias_coach_identity_id IS NULL
    OR alias_coach_identity_id <> canonical_coach_identity_id
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_coach_identity_alias_identity_active
  ON mart.coach_identity_alias (alias_coach_identity_id)
  WHERE is_active AND alias_coach_identity_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_coach_identity_alias_source_person_active
  ON mart.coach_identity_alias (alias_source, external_person_id)
  WHERE is_active AND external_person_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_coach_identity_alias_name_active
  ON mart.coach_identity_alias (alias_name_normalized)
  WHERE is_active AND alias_name_normalized IS NOT NULL;

CREATE OR REPLACE VIEW mart.v_coach_identity_resolution AS
SELECT
  ci.coach_identity_id AS source_coach_identity_id,
  COALESCE(alias.canonical_coach_identity_id, ci.coach_identity_id) AS canonical_coach_identity_id,
  alias.coach_identity_alias_id,
  alias.match_method,
  alias.confidence,
  alias.alias_source,
  alias.external_person_id,
  alias.alias_name,
  alias.alias_name_normalized,
  (alias.coach_identity_alias_id IS NOT NULL) AS is_alias
FROM mart.coach_identity ci
LEFT JOIN LATERAL (
  SELECT a.*
  FROM mart.coach_identity_alias a
  WHERE a.is_active
    AND a.status = 'active'
    AND a.alias_coach_identity_id = ci.coach_identity_id
  ORDER BY a.confidence DESC, a.coach_identity_alias_id DESC
  LIMIT 1
) alias ON true;

INSERT INTO mart.team_identity_alias (
  team_id,
  alias_source,
  external_team_id,
  alias_name,
  alias_name_normalized,
  match_method,
  confidence,
  status,
  notes,
  payload,
  updated_at
)
VALUES
  (3422, 'wikidata', 'Q80964', 'Sociedade Esportiva Palmeiras', 'sociedade esportiva palmeiras', 'manual_verified_external_id', 1.0000, 'active', 'Verified crosswalk for Palmeiras external sources.', '{"seed":"coach_alias_layer"}'::jsonb, now()),
  (3422, 'wikidata_P286_team_to_person', 'Q80964', 'Sociedade Esportiva Palmeiras', 'sociedade esportiva palmeiras', 'manual_verified_external_id', 1.0000, 'active', 'Verified crosswalk for Palmeiras external P286 facts.', '{"seed":"coach_alias_layer"}'::jsonb, now()),
  (3422, 'manual_verified_name', null, 'Sociedade Esportiva Palmeiras', 'sociedade esportiva palmeiras', 'manual_verified_name', 1.0000, 'active', 'Verified display-name alias for Palmeiras.', '{"seed":"coach_alias_layer"}'::jsonb, now()),
  (3422, 'manual_verified_name', null, 'SE Palmeiras', 'se palmeiras', 'manual_verified_name', 1.0000, 'active', 'Verified short-name alias for Palmeiras.', '{"seed":"coach_alias_layer"}'::jsonb, now())
ON CONFLICT DO NOTHING;

WITH canonical AS (
  SELECT coach_identity_id
  FROM mart.coach_identity
  WHERE provider = 'wikidata'
    AND provider_coach_id = 40652
),
alias_identity AS (
  SELECT coach_identity_id
  FROM mart.coach_identity
  WHERE provider = 'sportmonks'
    AND provider_coach_id = 474720
)
INSERT INTO mart.coach_identity_alias (
  canonical_coach_identity_id,
  alias_coach_identity_id,
  alias_source,
  external_person_id,
  alias_name,
  alias_name_normalized,
  match_method,
  confidence,
  status,
  notes,
  payload,
  updated_at
)
SELECT
  canonical.coach_identity_id,
  alias_identity.coach_identity_id,
  'sportmonks',
  '474720',
  'Adenor Bacchi',
  'adenor bacchi',
  'manual_verified_same_person',
  1.0000,
  'active',
  'Adenor Bacchi is the civil name used by SportMonks for Tite.',
  '{"seed":"coach_alias_layer","canonical_label":"Tite"}'::jsonb,
  now()
FROM canonical
CROSS JOIN alias_identity
ON CONFLICT DO NOTHING;

WITH canonical AS (
  SELECT coach_identity_id
  FROM mart.coach_identity
  WHERE provider = 'wikidata'
    AND provider_coach_id = 127256474
),
alias_identity AS (
  SELECT coach_identity_id
  FROM mart.coach_identity
  WHERE provider = 'sportmonks'
    AND provider_coach_id = 37690429
)
INSERT INTO mart.coach_identity_alias (
  canonical_coach_identity_id,
  alias_coach_identity_id,
  alias_source,
  external_person_id,
  alias_name,
  alias_name_normalized,
  match_method,
  confidence,
  status,
  notes,
  payload,
  updated_at
)
SELECT
  canonical.coach_identity_id,
  alias_identity.coach_identity_id,
  'sportmonks',
  '37690429',
  'Cledson Rafael de Paiva',
  'cledson rafael de paiva',
  'manual_verified_same_person',
  1.0000,
  'active',
  'Cledson Rafael de Paiva is the full name used by SportMonks for Rafael Paiva.',
  '{"seed":"coach_alias_layer","canonical_label":"Rafael Paiva"}'::jsonb,
  now()
FROM canonical
CROSS JOIN alias_identity
ON CONFLICT DO NOTHING;

WITH canonical AS (
  SELECT coach_identity_id
  FROM mart.coach_identity
  WHERE provider = 'sportmonks'
    AND provider_coach_id = 2511092
)
INSERT INTO mart.coach_identity_alias (
  canonical_coach_identity_id,
  alias_coach_identity_id,
  alias_source,
  external_person_id,
  alias_name,
  alias_name_normalized,
  match_method,
  confidence,
  status,
  notes,
  payload,
  updated_at
)
SELECT
  canonical.coach_identity_id,
  null,
  source_alias.alias_source,
  'Q318415',
  'Abel Ferreira',
  'abel ferreira',
  'manual_verified_external_id',
  1.0000,
  'active',
  'Wikidata Abel Ferreira mapped to existing SportMonks Abel Moreira Ferreira identity.',
  '{"seed":"coach_alias_layer","canonical_label":"Abel Moreira Ferreira"}'::jsonb,
  now()
FROM canonical
CROSS JOIN (
  VALUES
    ('wikidata'),
    ('wikidata_P286_team_to_person')
) AS source_alias(alias_source)
ON CONFLICT DO NOTHING;

UPDATE mart.coach_identity ci
SET
  aliases = (
    SELECT jsonb_agg(DISTINCT alias_item)
    FROM (
      SELECT jsonb_array_elements(ci.aliases) AS alias_item
      UNION ALL
      SELECT jsonb_build_object(
        'name', a.alias_name,
        'source', a.alias_source,
        'external_person_id', a.external_person_id,
        'alias_coach_identity_id', a.alias_coach_identity_id,
        'match_method', a.match_method
      ) AS alias_item
      FROM mart.coach_identity_alias a
      WHERE a.canonical_coach_identity_id = ci.coach_identity_id
        AND a.is_active
        AND a.status = 'active'
        AND a.alias_name IS NOT NULL
    ) aliases
  ),
  updated_at = now()
WHERE EXISTS (
  SELECT 1
  FROM mart.coach_identity_alias a
  WHERE a.canonical_coach_identity_id = ci.coach_identity_id
    AND a.is_active
    AND a.status = 'active'
);

-- migrate:down
DROP VIEW IF EXISTS mart.v_coach_identity_resolution;
DROP TABLE IF EXISTS mart.coach_identity_alias;
DROP TABLE IF EXISTS mart.team_identity_alias;
