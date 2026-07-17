with linked_sides as (
    select
        m.source_name,
        m.match_id,
        m.home_team_id as source_team_id,
        t.local_team_id,
        'home'::text as side
    from {{ source('postgres_raw', 'statsbomb_matches') }} m
    join {{ source('postgres_mart', 'stg_statsbomb_team_identity') }} t
      on t.source_name = m.source_name
     and t.source_team_id = m.home_team_id
     and t.identity_status = 'linked_to_sportmonks'
    where m.identity_status = 'new_external_match'

    union all

    select
        m.source_name,
        m.match_id,
        m.away_team_id,
        t.local_team_id,
        'away'::text
    from {{ source('postgres_raw', 'statsbomb_matches') }} m
    join {{ source('postgres_mart', 'stg_statsbomb_team_identity') }} t
      on t.source_name = m.source_name
     and t.source_team_id = m.away_team_id
     and t.identity_status = 'linked_to_sportmonks'
    where m.identity_status = 'new_external_match'
)
select l.source_name, l.match_id, l.side
from linked_sides l
join {{ ref('stg_matches') }} s
  on s.fixture_id = 900000000000 + l.match_id
where (l.side = 'home' and s.home_team_id <> l.local_team_id)
   or (l.side = 'away' and s.away_team_id <> l.local_team_id)
