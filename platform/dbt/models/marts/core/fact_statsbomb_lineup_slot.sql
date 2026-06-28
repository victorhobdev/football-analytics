with lineups as (
    select * from {{ ref('stg_statsbomb_lineups') }}
),
slots as (
    select
        l.source_name as provider,
        l.source_match_id,
        l.local_match_id,
        l.source_team_id,
        l.source_team_name,
        l.local_team_id,
        l.source_player_id,
        l.source_player_name,
        l.local_player_id,
        l.jersey_number,
        l.country_name,
        l.match_identity_status,
        l.player_identity_status,
        l.player_identity_reason,
        l.player_identity_confidence,
        position.position_index,
        position.position_item,
        l.updated_at
    from lineups l
    left join lateral (
        select
            ordinality - 1 as position_index,
            value as position_item
        from jsonb_array_elements(coalesce(l.payload -> 'player' -> 'positions', '[]'::jsonb)) with ordinality
    ) position on true
)
select
    md5(
        concat(
            provider, ':', source_match_id::text, ':', source_team_id::text, ':', source_player_id::text, ':',
            coalesce(position_index::text, 'no_position')
        )
    ) as statsbomb_lineup_slot_id,
    provider,
    source_match_id,
    local_match_id,
    source_team_id,
    source_team_name,
    local_team_id,
    source_player_id,
    source_player_name,
    local_player_id,
    jersey_number,
    country_name,
    position_index,
    position_item ->> 'position_id' as position_id,
    position_item ->> 'position' as position_name,
    position_item ->> 'from' as minute_from_label,
    position_item ->> 'to' as minute_to_label,
    position_item ->> 'from_period' as from_period,
    position_item ->> 'to_period' as to_period,
    position_item ->> 'start_reason' as start_reason,
    position_item ->> 'end_reason' as end_reason,
    match_identity_status,
    player_identity_status,
    player_identity_reason,
    player_identity_confidence,
    updated_at
from slots
