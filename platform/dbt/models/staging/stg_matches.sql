with source_matches as (
    select * from {{ source('postgres_raw', 'fixtures') }}
),
statsbomb_matches as (
    select * from {{ source('postgres_raw', 'statsbomb_matches') }}
    where identity_status = 'new_external_match'
      and match_date is not null
),
published_leagues as (
    select
        competition_key,
        min(league_id) as league_id,
        max(league_name) as league_name
    from (
        select
            competition_key,
            league_id,
            league_name
        from {{ source('postgres_raw', 'fixtures') }}
        where competition_key is not null
          and league_id is not null
        union all
        select
            coalesce(
                canonical_competition_key,
                case competition_id
                    when 44 then 'major_league_soccer'
                    when 223 then 'copa_america'
                    when 1267 then 'african_cup_of_nations'
                    else null
                end
            ) as competition_key,
            930000000000 + competition_id::numeric::bigint as league_id,
            payload -> 'competition' ->> 'competition_name' as league_name
        from {{ source('postgres_raw', 'statsbomb_matches') }}
        where match_date is not null
    ) league_scope
    where competition_key is not null
    group by competition_key
),
control_competitions as (
    select
        competition_key,
        competition_name
    from control.competitions
    where is_active = true
),
split_year_competitions as (
    select *
    from (
        values
            ('bundesliga'),
            ('champions_league'),
            ('la_liga'),
            ('ligue_1'),
            ('premier_league'),
            ('primeira_liga'),
            ('serie_a_it')
    ) as split_year(competition_key)
),
brasileirao_external as (
    select
        px.canonical_external_match_id as fixture_id,
        px.source as provider,
        px.source as source_provider,
        bx.match_date::timestamp at time zone 'UTC' as date_utc,
        'UTC' as timezone,
        bm.venue_name,
        bm.home_team_name,
        bm.away_team_name,
        bm.home_score,
        bm.away_score,
        bm.rodada as round_name,
        px.competition_key,
        pl.league_id,
        pl.league_name,
        extract(year from bx.match_date)::int as season_start_year,
        bm.ingested_at
    from control.external_match_publication_xref px
    inner join control.brasileirao_fixture_xref bx
      on bx.brasileirao_match_id = px.source_entity_id
    inner join raw.brasileirao_matches bm
      on bm.match_id = bx.brasileirao_match_id
    left join published_leagues pl
      on pl.competition_key = px.competition_key
    where px.source = 'dataset_brasileirao'
      and px.publication_status = 'publishable'
),
transfermarkt_external as (
    select
        px.canonical_external_match_id as fixture_id,
        px.source as provider,
        px.source as source_provider,
        tx.match_date::timestamp at time zone 'UTC' as date_utc,
        'UTC' as timezone,
        tg.stadium as venue_name,
        tx.home_team_name_raw as home_team_name,
        tx.away_team_name_raw as away_team_name,
        tg.home_club_goals as home_score,
        tg.away_club_goals as away_score,
        tg.round as round_name,
        cpm.competition_key,
        coalesce(pl.league_id, 970000000000 + (('x' || substr(md5(cpm.competition_key), 1, 15))::bit(60)::bigint % 99999999999)) as league_id,
        coalesce(pl.league_name, cc.competition_name, cpm.provider_name) as league_name,
        tg.season::int as season_start_year,
        tg.ingested_at
    from control.external_match_publication_xref px
    inner join control.tm_game_fixture_xref tx
      on tx.tm_game_id = px.source_entity_id
    inner join raw.tm_games tg
      on tg.game_id = tx.tm_game_id
    inner join control.competition_provider_map cpm
      on cpm.provider = 'transfermarkt'
     and cpm.provider_league_code = tg.competition_id
    left join published_leagues pl
      on pl.competition_key = cpm.competition_key
    left join control_competitions cc
      on cc.competition_key = cpm.competition_key
    where px.source = 'transfermarkt'
      and px.publication_status = 'publishable'
      and tg.season ~ '^[0-9]+$'
),
eloratings_external_base as (
    select
        px.canonical_external_match_id as fixture_id,
        px.source as provider,
        px.source as source_provider,
        ex.match_date::timestamp at time zone 'UTC' as date_utc,
        'UTC' as timezone,
        cast(null as text) as venue_name,
        ex.home_team_name_raw as home_team_name,
        ex.away_team_name_raw as away_team_name,
        em.ft_home_raw as home_score,
        em.ft_away_raw as away_score,
        cast(null as text) as round_name,
        ex.competition_key,
        coalesce(pl.league_id, 970000000000 + (('x' || substr(md5(ex.competition_key), 1, 15))::bit(60)::bigint % 99999999999)) as league_id,
        coalesce(pl.league_name, cc.competition_name, cpm.provider_name) as league_name,
        case
            when syc.competition_key is not null
             and extract(month from ex.match_date)::int <= 6
                then extract(year from ex.match_date)::int - 1
            else extract(year from ex.match_date)::int
        end as season_start_year,
        em.ingested_at
    from control.external_match_publication_xref px
    inner join control.elo_match_xref ex
      on ex.elo_match_hash = px.source_entity_id
    left join raw.elo_matches em
      on em.record_hash = ex.elo_match_hash
    left join split_year_competitions syc
      on syc.competition_key = ex.competition_key
    left join published_leagues pl
      on pl.competition_key = ex.competition_key
    left join control_competitions cc
      on cc.competition_key = ex.competition_key
    left join control.competition_provider_map cpm
      on cpm.provider = 'eloratings'
     and cpm.competition_key = ex.competition_key
    where px.source = 'eloratings'
      and px.publication_status = 'publishable'
),
external_matches as (
    select * from brasileirao_external
    union all
    select * from transfermarkt_external
    union all
    select * from eloratings_external_base
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
    930000000000 + competition_id::numeric::bigint as league_id,
    competition_id::numeric::bigint as provider_league_id,
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
    season_id::numeric::int as season,
    season_label,
    season_id::numeric::bigint as provider_season_id,
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

union all

select
    fixture_id,
    provider,
    source_provider,
    date_utc,
    cast(null as bigint) as fixture_timestamp,
    timezone,
    cast(null as text) as referee,
    cast(null as bigint) as referee_id,
    case
        when nullif(trim(venue_name), '') is not null
            then 960100000000 + (('x' || substr(md5(lower(trim(venue_name))), 1, 15))::bit(60)::bigint % 99999999999)
        else null
    end as venue_id,
    nullif(trim(venue_name), '') as venue_name,
    cast(null as text) as venue_city,
    cast(null as text) as venue_country,
    'FT' as status_short,
    'Finished' as status_long,
    league_id,
    league_id as provider_league_id,
    em.competition_key,
    cast(null as text) as competition_type,
    league_name,
    season_start_year as season,
    case
        when syc.competition_key is not null
            then concat(season_start_year::text, '_', right((season_start_year + 1)::text, 2))
        else season_start_year::text
    end as season_label,
    cast(null as bigint) as provider_season_id,
    cast(null as text) as season_name,
    cast(null as date) as season_start_date,
    cast(null as date) as season_end_date,
    round_name as round,
    cast(null as bigint) as stage_id,
    cast(null as text) as stage_name,
    cast(null as bigint) as round_id,
    round_name,
    cast(null as text) as group_name,
    cast(null as int) as leg_number,
    cast(null as int) as attendance,
    cast(null as text) as weather_description,
    cast(null as numeric) as weather_temperature_c,
    cast(null as numeric) as weather_wind_kph,
    960200000000 + (('x' || substr(md5(concat(provider, ':', em.competition_key, ':', lower(trim(home_team_name)))), 1, 15))::bit(60)::bigint % 99999999999) as home_team_id,
    home_team_name,
    960200000000 + (('x' || substr(md5(concat(provider, ':', em.competition_key, ':', lower(trim(away_team_name)))), 1, 15))::bit(60)::bigint % 99999999999) as away_team_id,
    away_team_name,
    nullif(home_score, '')::numeric::int as home_goals,
    nullif(away_score, '')::numeric::int as away_goals,
    cast(null as int) as home_goals_ht,
    cast(null as int) as away_goals_ht,
    nullif(home_score, '')::numeric::int as home_goals_ft,
    nullif(away_score, '')::numeric::int as away_goals_ft,
    extract(year from date_utc)::text as year,
    extract(month from date_utc)::text as month,
    coalesce(
        to_char(ingested_at::timestamp at time zone 'UTC', 'YYYY-MM-DD"T"HH24MISS"Z"'),
        '2026-06-20T000000Z'
    ) as ingested_run,
    provider as source_run_id,
    ingested_at
from external_matches em
left join split_year_competitions syc
  on syc.competition_key = em.competition_key
