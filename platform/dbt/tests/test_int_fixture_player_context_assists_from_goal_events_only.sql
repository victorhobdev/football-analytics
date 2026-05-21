-- Regra: fallback de assistencias por evento deve usar apenas gols nao-own-goal.
-- Tabela: int_fixture_player_context
-- Rationale: em eventos de substituicao, assist_player_id representa o outro jogador da troca, nao uma assistencia.

with expected_event_assists as (
    select
        fixture_id,
        assist_player_id as player_id,
        count(*)::int as assists_from_goal_events
    from {{ ref('stg_match_events') }}
    where fixture_id is not null
      and assist_player_id is not null
      and event_type = 'Goal'
      and coalesce(event_detail, '') <> 'Own Goal'
    group by fixture_id, assist_player_id
),
fallback_rows as (
    select
        c.provider,
        c.fixture_id,
        c.team_id,
        c.player_id,
        c.assists,
        coalesce(e.assists_from_goal_events, 0) as expected_assists
    from {{ ref('int_fixture_player_context') }} c
    left join {{ ref('stg_fixture_player_statistics') }} f
      on f.provider = c.provider
     and f.fixture_id = c.fixture_id
     and f.team_id = c.team_id
     and f.player_id = c.player_id
    left join expected_event_assists e
      on e.fixture_id = c.fixture_id
     and e.player_id = c.player_id
    where f.assists is null
)
select *
from fallback_rows
where coalesce(assists, 0) <> expected_assists
