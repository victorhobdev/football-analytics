{{ config(
    materialized='incremental',
    unique_key='elo_match_team_stat_id',
    on_schema_change='sync_all_columns',
    indexes=[
        {'columns': ['match_id'], 'type': 'btree'},
        {'columns': ['team_id', 'match_date'], 'type': 'btree'}
    ]
) }}

with elo as (
    select * from {{ ref('stg_elo_matches') }}
),
published_matches as (
    select
        match_id,
        competition_sk,
        competition_key,
        date_day as match_date,
        home_team_id,
        away_team_id,
        home_team_sk,
        away_team_sk
    from {{ ref('fact_matches') }}
),
team_rows as (
    select
        pm.match_id,
        pm.competition_sk,
        pm.competition_key,
        pm.match_date,
        'home' as side,
        pm.home_team_id as team_id,
        pm.home_team_sk as team_sk,
        elo.home_team_name as team_name,
        elo.home_elo as elo_rating,
        elo.form3_home as form3,
        elo.form5_home as form5,
        elo.home_shots as shots,
        elo.home_shots_on_target as shots_on_target,
        elo.home_fouls as fouls,
        elo.home_corners as corners,
        elo.home_yellow_cards as yellow_cards,
        elo.home_red_cards as red_cards,
        elo.ht_home_goals as half_time_goals,
        elo.ft_home_goals as full_time_goals,
        elo.ft_result,
        elo.ht_result,
        elo.elo_match_hash,
        elo.ingested_at
    from elo
    inner join published_matches pm
      on pm.match_id = elo.match_id

    union all

    select
        pm.match_id,
        pm.competition_sk,
        pm.competition_key,
        pm.match_date,
        'away' as side,
        pm.away_team_id as team_id,
        pm.away_team_sk as team_sk,
        elo.away_team_name as team_name,
        elo.away_elo as elo_rating,
        elo.form3_away as form3,
        elo.form5_away as form5,
        elo.away_shots as shots,
        elo.away_shots_on_target as shots_on_target,
        elo.away_fouls as fouls,
        elo.away_corners as corners,
        elo.away_yellow_cards as yellow_cards,
        elo.away_red_cards as red_cards,
        elo.ht_away_goals as half_time_goals,
        elo.ft_away_goals as full_time_goals,
        elo.ft_result,
        elo.ht_result,
        elo.elo_match_hash,
        elo.ingested_at
    from elo
    inner join published_matches pm
      on pm.match_id = elo.match_id
),
base as (
    select
        md5(concat('eloratings:', match_id::text, ':', side)) as elo_match_team_stat_id,
        match_id,
        competition_sk,
        competition_key,
        match_date,
        side,
        team_id,
        team_sk,
        team_name,
        elo_rating,
        form3,
        form5,
        shots,
        shots_on_target,
        fouls,
        corners,
        yellow_cards,
        red_cards,
        half_time_goals,
        full_time_goals,
        ft_result,
        ht_result,
        'eloratings' as source_provider,
        elo_match_hash as source_match_id,
        coalesce(ingested_at, now()) as updated_at
    from team_rows
    where elo_rating is not null
       or form3 is not null
       or form5 is not null
       or shots is not null
       or shots_on_target is not null
       or fouls is not null
       or corners is not null
       or yellow_cards is not null
       or red_cards is not null
),
filtered as (
    select *
    from base
    {% if is_incremental() %}
    where updated_at >= (
        select coalesce(max(updated_at) - interval '24 hour', timestamp '1900-01-01')
        from {{ this }}
    )
    {% endif %}
)
select * from filtered
