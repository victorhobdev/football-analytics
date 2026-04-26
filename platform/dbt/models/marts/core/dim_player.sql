{{ config(
    materialized='incremental',
    unique_key='player_sk',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['player_id'], 'type': 'btree'}
    ]
) }}

with events as (
    select * from {{ ref('stg_match_events') }}
),
lineups as (
    select * from {{ ref('stg_fixture_lineups') }}
),
player_stats as (
    select * from {{ ref('stg_fixture_player_statistics') }}
),
season_stats as (
    select * from {{ ref('stg_player_season_statistics') }}
),
player_ids_union as (
    select player_id
    from events
    where player_id is not null

    union

    select assist_player_id as player_id
    from events
    where assist_player_id is not null

    union

    select player_id
    from lineups
    where player_id is not null

    union

    select player_id
    from player_stats
    where player_id is not null

    union

    select player_id
    from season_stats
    where player_id is not null
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

    union all

    select
        player_id,
        nullif(trim(player_name), '') as player_name,
        updated_at,
        ingested_run,
        cast(lineup_id as text) as event_id,
        3 as source_priority
    from lineups
    where player_id is not null

    union all

    select
        player_id,
        nullif(trim(player_name), '') as player_name,
        updated_at,
        ingested_run,
        cast(fixture_id as text) as event_id,
        4 as source_priority
    from player_stats
    where player_id is not null
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
),
player_nationality_candidates as (
    select
        player_id,
        nullif(trim(player_nationality), '') as player_nationality,
        updated_at,
        ingested_run,
        season_id,
        row_number() over (
            partition by player_id
            order by
                case when nullif(trim(player_nationality), '') is null then 1 else 0 end,
                updated_at desc nulls last,
                ingested_run desc nulls last,
                season_id desc nulls last
        ) as row_num
    from season_stats
    where player_id is not null
)
select
    md5(concat('player:', ranked_players.player_id::text)) as player_sk,
    ranked_players.player_id as player_id,
    coalesce(
        ranked_players.player_name,
        concat('Unknown Player #', ranked_players.player_id::text)
    ) as player_name,
    nationality.player_nationality as nationality,
    now() as updated_at
from ranked_players
left join player_nationality_candidates nationality
  on nationality.player_id = ranked_players.player_id
 and nationality.row_num = 1
where ranked_players.row_num = 1
  and ranked_players.player_id is not null
