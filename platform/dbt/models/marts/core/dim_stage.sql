{{ config(
    indexes=[
        {'columns': ['competition_key', 'season_label', 'stage_id'], 'type': 'btree'},
        {'columns': ['provider', 'stage_id'], 'type': 'btree'}
    ]
) }}

with stages as (
    select * from {{ ref('stg_competition_stages') }}
),
season_config as (
    select
        competition_key,
        season_label,
        format_family,
        season_format_code
    from {{ ref('competition_season_config') }}
),
enriched as (
    select
        s.provider,
        s.stage_id,
        s.league_id,
        s.provider_league_id,
        s.season_id,
        s.competition_key,
        s.season_label,
        s.provider_season_id,
        s.stage_name,
        s.sort_order,
        s.finished,
        s.is_current,
        s.starting_at,
        s.ending_at,
        s.ingested_run,
        s.updated_at,
        sc.format_family,
        sc.season_format_code,
        trim(both '_' from regexp_replace(lower(coalesce(s.stage_name, '')), '[^a-z0-9]+', '_', 'g')) as stage_code
    from stages s
    left join season_config sc
      on sc.competition_key = s.competition_key
     and sc.season_label = s.season_label
),
classified as (
    select
        *,
        case
            when season_format_code = 'ucl_league_table_knockout_v1'
             and stage_code = 'league_stage' then 'league_table'
            when stage_code = 'group_stage' then 'group_table'
            when season_format_code = 'lib_qualification_group_knockout_v1'
             and stage_code in ('1st_round', '2nd_round', '3rd_round') then 'qualification_knockout'
            when season_format_code = 'sud_qualification_group_playoff_knockout_v1'
             and stage_code = '1st_round' then 'qualification_knockout'
            when season_format_code like 'fic_annual_champions_knockout_v1%'
             and stage_code in ('play_off', '1st_round', '2nd_round') then 'qualification_knockout'
            when season_format_code like 'ucl_%'
             and (
                 stage_code in ('preliminary_round_semi_finals', 'preliminary_round_final', 'play_offs')
                 or stage_code like '%qualifying_round'
             ) then 'qualification_knockout'
            when season_format_code = 'sud_qualification_group_playoff_knockout_v1'
             and stage_code = 'round_of_32' then 'knockout'
            when stage_code in ('knockout_round_play_offs', 'round_of_16', '8th_finals', 'quarter_finals', 'semi_finals', 'final') then 'knockout'
            when format_family = 'knockout'
             and stage_code <> '' then 'knockout'
            else null
        end as stage_format
    from enriched
),
deduped as (
    select
        provider,
        stage_id,
        league_id,
        provider_league_id,
        season_id,
        competition_key,
        season_label,
        provider_season_id,
        stage_name,
        stage_code,
        sort_order,
        stage_format,
        finished,
        is_current,
        starting_at,
        ending_at,
        ingested_run,
        updated_at,
        row_number() over (
            partition by provider, stage_id
            order by updated_at desc nulls last, ingested_run desc nulls last
        ) as row_num
    from classified
    where stage_id is not null
)
select
    md5(concat(provider, ':stage:', stage_id::text)) as stage_sk,
    provider,
    stage_id,
    league_id,
    provider_league_id,
    season_id,
    competition_key,
    season_label,
    provider_season_id,
    stage_name,
    nullif(stage_code, '') as stage_code,
    sort_order,
    stage_format,
    case
        when stage_format = 'league_table' then 'single_table'
        when stage_format = 'group_table' then 'grouped_table'
        when stage_format in ('knockout', 'qualification_knockout') then 'not_applicable'
        else null
    end as standings_context_mode,
    case
        when stage_format in ('knockout', 'qualification_knockout') then 'knockout'
        when stage_format in ('league_table', 'group_table') then 'not_applicable'
        else null
    end as bracket_context_mode,
    case
        when stage_format = 'group_table' then 'multiple_groups'
        when stage_format in ('league_table', 'knockout', 'qualification_knockout') then 'not_applicable'
        else null
    end as group_mode,
    cast(null as text) as leg_mode,
    case
        when stage_format = 'qualification_knockout' then 'qualification'
        when stage_format = 'knockout' then 'standard'
        when stage_format in ('league_table', 'group_table') then 'not_applicable'
        else null
    end as elimination_mode,
    finished,
    is_current,
    starting_at,
    ending_at,
    now() as updated_at
from deduped
where row_num = 1
