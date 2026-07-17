with linked_external as (
    select 'eloratings'::text as source, ex.elo_match_hash::text as source_entity_id,
           ex.local_fixture_id
    from control.elo_match_xref ex
    where ex.identity_status = 'linked_to_sportmonks'
      and ex.local_fixture_id is not null
    union all
    select 'transfermarkt'::text, tx.tm_game_id::text, tx.local_fixture_id
    from control.tm_game_fixture_xref tx
    where tx.identity_status = 'linked_to_sportmonks'
      and tx.local_fixture_id is not null
)
select source, source_entity_id
from linked_external e
where not exists (
    select 1
    from {{ ref('stg_elo_matches') }} s
    where e.source = 'eloratings'
      and s.elo_match_hash = e.source_entity_id
      and s.match_id = e.local_fixture_id
)
and not exists (
    select 1
    from {{ ref('stg_tm_match_identity') }} s
    where e.source = 'transfermarkt'
      and s.tm_game_id = e.source_entity_id
      and s.match_id = e.local_fixture_id
)
