{{ config(materialized='incremental', unique_key='player_sk', on_schema_change='sync_all_columns') }}

with events as (
    select * from {{ ref('stg_match_events') }}
),
player_ids_union as (
    select player_id
    from events
    where player_id is not null

    union

    select assist_player_id as player_id
    from events
    where assist_player_id is not null
),
player_attribute_candidates as (
    select
        player_id,
        nullif(trim(player_name), '') as player_name,
        updated_at,
        ingested_run,
        event_id,
        1 as source_priority
    from events
    where player_id is not null

    union all

    select
        assist_player_id as player_id,
        nullif(trim(assist_player_name), '') as player_name,
        updated_at,
        ingested_run,
        event_id,
        2 as source_priority
    from events
    where assist_player_id is not null
),
ranked_players as (
    select
        ids.player_id,
        attrs.player_name,
        row_number() over (
            partition by ids.player_id
            order by
                case when attrs.player_name is null then 1 else 0 end,
                attrs.source_priority,
                attrs.updated_at desc nulls last,
                attrs.ingested_run desc nulls last,
                attrs.event_id desc nulls last
        ) as row_num
    from player_ids_union ids
    left join player_attribute_candidates attrs
      on attrs.player_id = ids.player_id
)
select
    md5(concat('player:', player_id::text)) as player_sk,
    player_id,
    coalesce(player_name, concat('Unknown Player #', player_id::text)) as player_name,
    now() as updated_at
from ranked_players
where row_num = 1
  and player_id is not null
