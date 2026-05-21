-- Regra: atribuicoes publicas de tecnico devem ter grao unico e identidade resolvida.
-- Tabela: fact_coach_match_assignment
-- Rationale: desempenho publico de tecnico depende de no maximo um tecnico publicavel por match_id + team_id.

select
    'duplicate_public_match_team' as issue,
    match_id::text as match_id,
    team_id::text as team_id
from (
    select match_id, team_id
    from {{ target.schema }}.fact_coach_match_assignment
    where is_public_eligible
    group by match_id, team_id
    having count(*) > 1
) duplicates

union all

select
    'public_missing_coach_identity' as issue,
    match_id::text as match_id,
    team_id::text as team_id
from {{ target.schema }}.fact_coach_match_assignment
where is_public_eligible
  and coach_identity_id is null

union all

select
    'public_invalid_confidence' as issue,
    match_id::text as match_id,
    team_id::text as team_id
from {{ target.schema }}.fact_coach_match_assignment
where is_public_eligible
  and coalesce(assignment_confidence, 0) <= 0
