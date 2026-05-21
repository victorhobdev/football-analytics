-- Regra: dimensao publica de competicoes nao deve expor termos editoriais em ingles.
-- Tabela: dim_competition
-- Rationale: a camada publica deve usar taxonomia PT-BR para paises, regioes e fases.

select
    competition_sk,
    league_id,
    league_name,
    country
from {{ ref('dim_competition') }}
where league_name ~* '(quarter-finals|semi-finals|round of|south america|north america|england)'
   or country ~* '(south america|north america|england)'
