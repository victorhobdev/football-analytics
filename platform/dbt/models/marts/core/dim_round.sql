{{ config(
    indexes=[
        {'columns': ['league_id', 'season_id', 'stage_id', 'round_id'], 'type': 'btree'}
    ]
) }}

with rounds as (
    select * from {{ ref('int_competition_round_calendar') }}
)
select
    md5(concat(provider, ':round:', round_id::text)) as round_sk,
    provider,
    round_id,
    stage_id,
    md5(concat(provider, ':stage:', stage_id::text)) as stage_sk,
    league_id,
    season_id,
    round_key,
    round_name,
    starting_at,
    ending_at,
    finished,
    is_current,
    now() as updated_at
from rounds
