with source_matches as (
    select * from {{ source('postgres_raw', 'fixtures') }}
),
statsbomb_matches as (
    select * from {{ source('postgres_raw', 'statsbomb_matches') }}
    where identity_status = 'new_external_match'
      and match_date is not null
)
select
    fixture_id,
    coalesce(provider, source_provider) as provider,
    source_provider,
    coalesce(date_utc, date::timestamp at time zone 'UTC') as date_utc,
    "timestamp" as fixture_timestamp,
    timezone,
    referee,
    referee_id,
    venue_id,
    venue_name,
    venue_city,
    cast(null as text) as venue_country,
    status_short,
    status_long,
    league_id,
    provider_league_id,
    nullif(trim(competition_key), '') as competition_key,
    nullif(trim(competition_type), '') as competition_type,
    league_name,
    season,
    nullif(trim(season_label), '') as season_label,
    provider_season_id,
    nullif(trim(season_name), '') as season_name,
    season_start_date,
    season_end_date,
    round,
    stage_id,
    nullif(trim(stage_name), '') as stage_name,
    round_id,
    nullif(trim(round_name), '') as round_name,
    nullif(trim(group_name), '') as group_name,
    leg as leg_number,
    attendance,
    weather_description,
    weather_temperature_c,
    weather_wind_kph,
    home_team_id,
    home_team_name,
    away_team_id,
    away_team_name,
    home_goals,
    away_goals,
    home_goals_ht,
    away_goals_ht,
    home_goals_ft,
    away_goals_ft,
    year,
    month,
    case
        when ingested_run ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}Z$' then ingested_run
        when ingested_run ~ '[0-9]{8}T[0-9]{6}Z$'
            then concat(
                substring(ingested_run from '([0-9]{4})[0-9]{4}T[0-9]{6}Z$'),
                '-',
                substring(ingested_run from '[0-9]{4}([0-9]{2})[0-9]{2}T[0-9]{6}Z$'),
                '-',
                substring(ingested_run from '[0-9]{6}([0-9]{2})T[0-9]{6}Z$'),
                'T',
                substring(ingested_run from '[0-9]{8}T([0-9]{6})Z$'),
                'Z'
            )
        else ingested_run
    end as ingested_run,
    source_run_id,
    ingested_at
from source_matches

union all

select
    900000000000 + match_id as fixture_id,
    source_name as provider,
    source_name as source_provider,
    match_date::timestamp at time zone 'UTC' as date_utc,
    cast(null as bigint) as fixture_timestamp,
    'UTC' as timezone,
    referee_name as referee,
    referee_id,
    stadium_id as venue_id,
    stadium_name as venue_name,
    cast(null as text) as venue_city,
    payload -> 'stadium' -> 'country' ->> 'name' as venue_country,
    match_status as status_short,
    match_status as status_long,
    930000000000 + competition_id as league_id,
    competition_id as provider_league_id,
    coalesce(
        canonical_competition_key,
        case competition_id
            when 35 then 'uefa_europa_league'
            when 37 then 'fa_womens_super_league'
            when 44 then 'major_league_soccer'
            when 49 then 'nwsl'
            when 53 then 'uefa_womens_euro'
            when 55 then 'uefa_euro'
            when 72 then 'fifa_womens_world_cup'
            when 81 then 'liga_profesional_argentina'
            when 87 then 'copa_del_rey'
            when 116 then 'north_american_league'
            when 131 then 'serie_a_women'
            when 135 then 'frauen_bundesliga'
            when 182 then 'liga_f'
            when 223 then 'copa_america'
            when 1238 then 'indian_super_league'
            when 1267 then 'african_cup_of_nations'
            when 1470 then 'fifa_u20_world_cup'
            else null
        end
    ) as competition_key,
    case
        when payload -> 'competition' ->> 'country_name' = 'International' then 'international'
        else 'domestic'
    end as competition_type,
    case
        when payload -> 'competition' ->> 'competition_name' = 'North American League' then 'Liga Norte-Americana'
        else payload -> 'competition' ->> 'competition_name'
    end as league_name,
    season_id::int as season,
    season_label,
    season_id as provider_season_id,
    payload -> 'season' ->> 'season_name' as season_name,
    cast(null as date) as season_start_date,
    cast(null as date) as season_end_date,
    competition_stage_name as round,
    competition_stage_id as stage_id,
    competition_stage_name as stage_name,
    cast(null as bigint) as round_id,
    cast(null as text) as round_name,
    cast(null as text) as group_name,
    cast(null as int) as leg_number,
    cast(null as int) as attendance,
    cast(null as text) as weather_description,
    cast(null as numeric) as weather_temperature_c,
    cast(null as numeric) as weather_wind_kph,
    910000000000 + home_team_id as home_team_id,
    home_team_name,
    910000000000 + away_team_id as away_team_id,
    away_team_name,
    home_score as home_goals,
    away_score as away_goals,
    cast(null as int) as home_goals_ht,
    cast(null as int) as away_goals_ht,
    home_score as home_goals_ft,
    away_score as away_goals_ft,
    extract(year from match_date)::text as year,
    extract(month from match_date)::text as month,
    coalesce(
        to_char(updated_at::timestamp at time zone 'UTC', 'YYYY-MM-DD"T"HH24MISS"Z"'),
        '2026-06-19T000000Z'
    ) as ingested_run,
    'statsbomb_open_data' as source_run_id,
    updated_at as ingested_at
from statsbomb_matches
