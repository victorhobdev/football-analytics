{{ config(materialized='view') }}

select
    x.tm_game_id,
    coalesce(
        case
            when x.identity_status = 'linked_to_sportmonks' then x.local_fixture_id
            else null
        end,
        case
            when px.publication_status = 'publishable' then px.canonical_external_match_id
            else null
        end
    ) as match_id,
    x.identity_status,
    px.publication_status,
    px.competition_key,
    x.match_date
from control.tm_game_fixture_xref x
left join control.external_match_publication_xref px
  on px.source = 'transfermarkt'
 and px.source_entity_id = x.tm_game_id
where (
        x.identity_status = 'linked_to_sportmonks'
    and x.local_fixture_id is not null
)
or px.publication_status = 'publishable'
