{{ config(materialized='view') }}

with published_leagues as (
    select
        competition_key,
        min(league_id) as league_id,
        max(league_name) as league_name
    from {{ source('postgres_raw', 'fixtures') }}
    where competition_key is not null
      and league_id is not null
    group by competition_key
),
canonical_team_identity as (
    {% if var('canonical_snapshot_schema', '') %}
    select canonical_team_id, identity_state
    from {{ adapter.quote(var('canonical_identity_schema', 'shadow_team_identity_20260715')) }}.canonical_team
    {% else %}
    select canonical_team_id, identity_state
    from control.team_identity
    {% endif %}
),
external_candidates as (
    select
        px.canonical_external_match_id as fixture_id,
        px.source as provider,
        px.source as source_provider,
        bx.match_date as date_utc,
        cast(null as text) as venue_name,
        bx.home_team_name_raw as home_team_name,
        bx.away_team_name_raw as away_team_name,
        bm.home_score as home_score_raw,
        bm.away_score as away_score_raw,
        bm.rodada as round_name,
        px.competition_key,
        pl.league_id,
        pl.league_name,
        extract(year from bx.match_date)::int as season,
        bx.match_date::text as season_label,
        bm.ingested_at,
        'dataset_brasileirao:name:' || lower(regexp_replace(trim(bx.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g')) as home_source_team_key,
        'dataset_brasileirao:name:' || lower(regexp_replace(trim(bx.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g')) as away_source_team_key
    from control.external_match_publication_xref px
    join control.brasileirao_fixture_xref bx
      on bx.brasileirao_match_id = px.source_entity_id
    join raw.brasileirao_matches bm
      on bm.match_id = bx.brasileirao_match_id
    left join published_leagues pl
      on pl.competition_key = px.competition_key
    where px.source = 'dataset_brasileirao'
      and px.publication_status = 'publishable'
      and bx.identity_status = 'new_coverage'
      and bx.review_status in ('auto_approved', 'approved')

    union all

    select
        px.canonical_external_match_id,
        px.source,
        px.source,
        tx.match_date,
        tg.stadium,
        tx.home_team_name_raw,
        tx.away_team_name_raw,
        tg.home_club_goals,
        tg.away_club_goals,
        tg.round,
        px.competition_key,
        pl.league_id,
        coalesce(pl.league_name, cpm.provider_name),
        nullif(tg.season, '')::int,
        tg.season,
        tg.ingested_at,
        coalesce(
            'transfermarkt:club:' || nullif(trim(tg.home_club_id), ''),
            'transfermarkt:name:' || lower(regexp_replace(trim(tx.home_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))
        ),
        coalesce(
            'transfermarkt:club:' || nullif(trim(tg.away_club_id), ''),
            'transfermarkt:name:' || lower(regexp_replace(trim(tx.away_team_name_raw), '[^[:alnum:]]+', ' ', 'g'))
        )
    from control.external_match_publication_xref px
    join control.tm_game_fixture_xref tx
      on tx.tm_game_id = px.source_entity_id
    join raw.tm_games tg
      on tg.game_id = tx.tm_game_id
    join control.competition_provider_map cpm
      on cpm.provider = 'transfermarkt'
     and cpm.provider_league_code = tg.competition_id
    left join published_leagues pl
      on pl.competition_key = cpm.competition_key
    where px.source = 'transfermarkt'
      and px.publication_status = 'publishable'
      and tx.identity_status = 'new_coverage'
      and tx.review_status in ('auto_approved', 'approved')
      and nullif(tg.season, '') ~ '^[0-9]+$'

    union all

    select
        px.canonical_external_match_id,
        px.source,
        px.source,
        ex.match_date,
        cast(null as text),
        ex.home_team_name_raw,
        ex.away_team_name_raw,
        em.ft_home_raw,
        em.ft_away_raw,
        cast(null as text),
        ex.competition_key,
        pl.league_id,
        coalesce(pl.league_name, cpm.provider_name),
        extract(year from ex.match_date)::int,
        extract(year from ex.match_date)::text,
        em.ingested_at,
        'eloratings:' || ex.competition_key || ':' || ex.home_team_name_raw
          || case when ex.home_team_name_raw = 'Belenenses'
                  then case when ex.match_date < date '2018-07-01' then ':pre_2018' else ':post_2018' end
                  else '' end,
        'eloratings:' || ex.competition_key || ':' || ex.away_team_name_raw
          || case when ex.away_team_name_raw = 'Belenenses'
                  then case when ex.match_date < date '2018-07-01' then ':pre_2018' else ':post_2018' end
                  else '' end
    from control.external_match_publication_xref px
    join control.elo_match_xref ex
      on ex.elo_match_hash = px.source_entity_id
    left join raw.elo_matches em
      on em.record_hash = ex.elo_match_hash
    left join control.competition_provider_map cpm
      on cpm.provider = 'eloratings'
     and cpm.competition_key = ex.competition_key
    left join published_leagues pl
      on pl.competition_key = ex.competition_key
    where px.source = 'eloratings'
      and px.publication_status = 'publishable'
      and ex.identity_status = 'new_coverage'
      and ex.review_status in ('auto_approved', 'approved')
),
resolved as (
    select
        e.*,
        home_identity.canonical_team_id as home_canonical_id,
        away_identity.canonical_team_id as away_canonical_id
    from external_candidates e
    join raw.provider_entity_map hm
      on hm.provider = e.provider
     and hm.entity_type = 'team'
     and hm.source_team_key = e.home_source_team_key
     and hm.mapping_state = 'approved'
     and (hm.valid_from is null or hm.valid_from <= e.date_utc::date)
     and (hm.valid_to is null or e.date_utc::date < hm.valid_to)
    join raw.provider_entity_map am
      on am.provider = e.provider
     and am.entity_type = 'team'
     and am.source_team_key = e.away_source_team_key
     and am.mapping_state = 'approved'
     and (am.valid_from is null or am.valid_from <= e.date_utc::date)
     and (am.valid_to is null or e.date_utc::date < am.valid_to)
    join canonical_team_identity home_identity
      on home_identity.canonical_team_id = case when hm.canonical_id ~ '^[0-9]+$' then hm.canonical_id::bigint end
     and home_identity.identity_state = 'active'
    join canonical_team_identity away_identity
      on away_identity.canonical_team_id = case when am.canonical_id ~ '^[0-9]+$' then am.canonical_id::bigint end
     and away_identity.identity_state = 'active'
    where hm.canonical_id ~ '^[0-9]+$'
      and am.canonical_id ~ '^[0-9]+$'
),
typed as (
    select
        fixture_id,
        provider,
        source_provider,
        date_utc::timestamp at time zone 'UTC' as date_utc,
        cast(null as bigint) as fixture_timestamp,
        'UTC'::text as timezone,
        cast(null as text) as referee,
        cast(null as bigint) as referee_id,
        cast(null as bigint) as venue_id,
        venue_name,
        cast(null as text) as venue_city,
        cast(null as text) as venue_country,
        'FT'::text as status_short,
        'Finished'::text as status_long,
        league_id,
        cast(null as bigint) as provider_league_id,
        competition_key,
        cast(null as text) as competition_type,
        league_name,
        season,
        season_label,
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
        cast(home_canonical_id as bigint) as home_team_id,
        home_team_name,
        cast(away_canonical_id as bigint) as away_team_id,
        away_team_name,
        case when home_score_raw ~ '^-?[0-9]+$' then home_score_raw::int else null end as home_goals,
        case when away_score_raw ~ '^-?[0-9]+$' then away_score_raw::int else null end as away_goals,
        cast(null as int) as home_goals_ht,
        cast(null as int) as away_goals_ht,
        case when home_score_raw ~ '^-?[0-9]+$' then home_score_raw::int else null end as home_goals_ft,
        case when away_score_raw ~ '^-?[0-9]+$' then away_score_raw::int else null end as away_goals_ft,
        extract(year from date_utc)::text as year,
        extract(month from date_utc)::text as month,
        to_char(ingested_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24MISS"Z"') as ingested_run,
        provider as source_run_id,
        ingested_at
    from resolved
)
select *
from typed
