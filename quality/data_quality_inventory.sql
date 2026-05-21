-- Baseline editorial de qualidade dos dados.
-- Execute contra o warehouse local antes de promover mudancas de publicacao.
-- As queries sao inventarios: elas devem produzir listas finitas e revisaveis.

-- 1) Sentinels tecnicos em dimensoes centrais.
select 'team' as entity, team_id::text as entity_id, team_name as label
from mart.dim_team
where team_name ~ '^(Unknown Team|Team) #|^[0-9]+$'
union all
select 'player' as entity, player_id::text as entity_id, player_name as label
from mart.dim_player
where player_name ~ '^(Unknown Player) #|^[0-9]+$'
union all
select 'venue' as entity, venue_id::text as entity_id, venue_name as label
from mart.dim_venue
where venue_name ~ '^(Unknown Venue) #|^[0-9]+$'
order by 1, 2;

-- 2) Termos em ingles proibidos em catalogo/labels publicos quando houver PT-BR esperado.
-- Ajuste a origem para a camada publica disponivel no ambiente.
select 'competition' as entity, league_id::text as entity_id, league_name as label
from mart.dim_competition
where league_name ~* '(quarter-finals|semi-finals|round of|south america|north america|england)'
   or country ~* '(south america|north america|england)'
order by 1, 2;

-- 3) World Cup: pendencias de confianca e bloqueio em jogadores.
select match_confidence, blocked_reason, count(*) as rows_count
from raw.wc_player_identity_map
group by 1, 2
order by rows_count desc;

-- 4) World Cup: pendencias de confianca/status em selecoes.
select confidence, status, count(*) as rows_count
from raw.wc_team_identity_map
group by 1, 2
order by rows_count desc;

-- 5) Transferencias: peso real dos tipos do provider.
select type_id, count(*) as rows_count
from mart.stg_player_transfers
group by 1
order by rows_count desc;

-- 6) Transferencias: amostra auditavel de retorno de emprestimo.
select transfer_id, player_id, from_team_id, to_team_id, transfer_date, type_id
from mart.stg_player_transfers
where type_id = 9688
order by transfer_date desc nulls last, transfer_id desc
limit 200;

-- 7) Imagens de tecnicos ainda vindas de placeholder do provider.
select count(*) as placeholder_count
from mart.coach_identity
where image_url ilike '%placeholder%';
