with source_lineups as (
    select * from {{ source('postgres_raw', 'fixture_lineups') }}
),
statsbomb_lineups as (
    select
        l.*,
        m.match_date
    from {{ source('postgres_raw', 'statsbomb_lineups') }} l
    left join {{ source('postgres_raw', 'statsbomb_matches') }} m
      on m.source_name = l.source_name
     and m.match_id = l.match_id
    where l.match_identity_status = 'new_external_match'
      and m.match_date is not null
),
enriched as (
    select
        l.provider,
        l.fixture_id,
        l.team_id,
        l.player_id,
        nullif(
            trim(
                coalesce(
                    l.payload -> 'player' ->> 'name',
                    l.payload ->> 'player_name',
                    l.payload -> 'player' ->> 'display_name'
                )
            ),
            ''
        ) as player_name,
        l.lineup_id,
        l.position_id,
        nullif(trim(l.position_name), '') as position_name,
        l.lineup_type_id,
        nullif(trim(l.formation_field), '') as formation_field,
        l.formation_position,
        l.jersey_number,
        l.details,
        l.payload,
        l.ingested_run,
        l.updated_at,
        stats.minutes_played
    from source_lineups l
    left join lateral (
        select
            max(
                nullif(
                    regexp_replace(
                        coalesce(
                            detail ->> 'value',
                            detail -> 'raw_value' ->> 'value',
                            detail ->> 'raw_value',
                            ''
                        ),
                        '[^0-9\\.-]',
                        '',
                        'g'
                    ),
                    ''
                )::numeric
            )::int as minutes_played
        from jsonb_array_elements(
            case jsonb_typeof(l.details)
                when 'array' then l.details
                when 'object' then jsonb_build_array(l.details)
                else '[]'::jsonb
            end
        ) as detail
        where lower(coalesce(detail ->> 'type', detail ->> 'developer_name', detail ->> 'raw_type_name', '')) in (
            'minutes_played',
            'minutes',
            'time_played'
        )
    ) stats on true
),
statsbomb_enriched as (
    select
        source_name as provider,
        900000000000 + match_id as fixture_id,
        910000000000 + source_team_id as team_id,
        920000000000 + source_player_id as player_id,
        nullif(trim(source_player_name), '') as player_name,
        source_player_id as lineup_id,
        nullif(payload -> 'player' -> 'positions' -> 0 ->> 'position_id', '')::bigint as position_id,
        nullif(trim(payload -> 'player' -> 'positions' -> 0 ->> 'position'), '') as position_name,
        case
            when payload -> 'player' -> 'positions' -> 0 ->> 'start_reason' = 'Starting XI' then 1
            else null
        end as lineup_type_id,
        cast(null as text) as formation_field,
        cast(null as int) as formation_position,
        jersey_number,
        cast(null as int) as minutes_played,
        payload -> 'player' -> 'positions' as details,
        payload,
        coalesce(
            to_char(updated_at::timestamp at time zone 'UTC', 'YYYY-MM-DD"T"HH24MISS"Z"'),
            '2026-06-19T000000Z'
        ) as ingested_run,
        updated_at
    from statsbomb_lineups
    where source_team_id is not null
      and source_player_id is not null
)
select
    provider,
    fixture_id,
    team_id,
    player_id,
    player_name,
    lineup_id,
    position_id,
    position_name,
    lineup_type_id,
    case
        when lineup_type_id in (1, 11) then true
        when lineup_type_id is null then null
        else false
    end as is_starter,
    formation_field,
    formation_position,
    jersey_number,
    minutes_played,
    details,
    payload,
    ingested_run,
    updated_at
from enriched

union all

select
    provider,
    fixture_id,
    team_id,
    player_id,
    player_name,
    lineup_id,
    position_id,
    position_name,
    lineup_type_id,
    case
        when lineup_type_id in (1, 11) then true
        when lineup_type_id is null then null
        else false
    end as is_starter,
    formation_field,
    formation_position,
    jersey_number,
    minutes_played,
    details,
    payload,
    ingested_run,
    updated_at
from statsbomb_enriched
