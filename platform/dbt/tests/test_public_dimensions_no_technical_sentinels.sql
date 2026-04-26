-- Regra: dimensoes publicas nao devem expor sentinels tecnicos como nome final.
-- Tabelas: dim_team, dim_player, dim_venue, dim_coach
-- Rationale: IDs tecnicos podem existir como identificadores, mas nao como rotulos publicos.

select 'team' as entity, team_id::text as entity_id, team_name as label
from {{ ref('dim_team') }}
where team_name ~ '^(Unknown Team|Team) #|^[0-9]+$'

union all

select 'player' as entity, player_id::text as entity_id, player_name as label
from {{ ref('dim_player') }}
where player_name ~ '^(Unknown Player) #|^[0-9]+$'

union all

select 'venue' as entity, venue_id::text as entity_id, venue_name as label
from {{ ref('dim_venue') }}
where venue_name ~ '^(Unknown Venue) #|^[0-9]+$'

union all

select 'coach' as entity, coach_id::text as entity_id, coach_name as label
from {{ ref('dim_coach') }}
where coach_name ~ '^(Unknown Coach) #|^[0-9]+$'
