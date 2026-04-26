-- Regra: superficie analitica de tecnicos nao deve expor sentinels tecnicos.
-- Tabela: coach_performance_summary
-- Rationale: rankings e perfis podem preservar IDs, mas nomes publicos devem ser editoriais.

select
    coach_tenure_id::text as entity_id,
    coach_name as label,
    'coach_name' as field_name
from {{ ref('coach_performance_summary') }}
where coach_name ~ '^(Unknown Coach|Coach) #|^[0-9]+$'

union all

select
    coach_tenure_id::text as entity_id,
    team_name as label,
    'team_name' as field_name
from {{ ref('coach_performance_summary') }}
where team_name ~ '^(Unknown Team|Team) #|^[0-9]+$'
