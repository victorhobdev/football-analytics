-- Regra: imagens placeholder de tecnico devem ser classificadas explicitamente.
-- Tabela: dim_coach
-- Rationale: placeholder do provider pode existir como dado operacional, mas nao deve parecer foto real.

select
    coach_sk,
    provider,
    coach_id,
    coach_name,
    image_path,
    is_placeholder_image
from {{ ref('dim_coach') }}
where image_path ilike '%placeholder%'
  and is_placeholder_image is not true
