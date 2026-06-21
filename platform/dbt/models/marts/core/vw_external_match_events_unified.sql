{{ config(materialized='view') }}

with wc_statsbomb as (
    select
        source_name as provider,
        source_match_id::bigint as source_match_id,
        fixture_id as local_match_id,
        source_event_id,
        event_index as source_event_index,
        event_type,
        period,
        minute,
        second,
        team_internal_id as source_team_id,
        player_internal_id as source_player_id,
        location_x,
        location_y,
        play_pattern_label as play_pattern,
        is_three_sixty_backed,
        'raw.wc_match_events' as source_table,
        event_payload as payload,
        updated_at
    from raw.wc_match_events
    where source_name = 'statsbomb_open_data'
),
external_statsbomb as (
    select
        provider,
        source_match_id,
        local_match_id,
        source_event_id,
        source_event_index,
        event_type,
        period,
        minute,
        second,
        source_team_id::text as source_team_id,
        source_player_id::text as source_player_id,
        location_x,
        location_y,
        play_pattern,
        is_three_sixty_backed,
        'mart.fact_statsbomb_match_event' as source_table,
        payload,
        updated_at
    from {{ ref('fact_statsbomb_match_event') }}
)
select * from wc_statsbomb
union all
select * from external_statsbomb
