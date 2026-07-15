with pending_publications as (
    select bx.brasileirao_match_id::text as source_entity_id, 'dataset_brasileirao'::text as source
    from control.brasileirao_fixture_xref bx
    join control.external_match_publication_xref px
      on px.source = 'dataset_brasileirao'
     and px.source_entity_id = bx.brasileirao_match_id::text
    where bx.identity_status = 'new_coverage'
      and bx.review_status <> 'auto_approved'
      and px.publication_status = 'publishable'

    union all

    select tx.tm_game_id::text, 'transfermarkt'::text
    from control.tm_game_fixture_xref tx
    join control.external_match_publication_xref px
      on px.source = 'transfermarkt'
     and px.source_entity_id = tx.tm_game_id::text
    where tx.identity_status = 'new_coverage'
      and tx.review_status <> 'auto_approved'
      and px.publication_status = 'publishable'

    union all

    select ex.elo_match_hash::text, 'eloratings'::text
    from control.elo_match_xref ex
    join control.external_match_publication_xref px
      on px.source = 'eloratings'
     and px.source_entity_id = ex.elo_match_hash::text
    where ex.identity_status = 'new_coverage'
      and ex.review_status <> 'auto_approved'
      and px.publication_status = 'publishable'
)
select source, source_entity_id
from pending_publications
