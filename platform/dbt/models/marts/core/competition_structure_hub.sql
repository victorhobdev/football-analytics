{{ config(
    indexes=[
        {'columns': ['competition_key', 'season_label', 'from_stage_id'], 'type': 'btree'}
    ]
) }}

with season_config as (
    select
        competition_key,
        season_label,
        season_format_code
    from {{ ref('competition_season_config') }}
),
rules as (
    select * from {{ ref('stage_progression_config') }}
),
stages as (
    select
        provider,
        competition_key,
        season_label,
        stage_id,
        stage_sk,
        stage_name,
        stage_code,
        stage_format,
        sort_order
    from {{ ref('dim_stage') }}
),
mapped_rules as (
    select
        from_stage.provider,
        season_config.competition_key,
        season_config.season_label,
        season_config.season_format_code,
        rules.rule_order,
        from_stage.stage_id as from_stage_id,
        from_stage.stage_sk as from_stage_sk,
        from_stage.stage_name as from_stage_name,
        from_stage.stage_code as from_stage_code,
        from_stage.stage_format as from_stage_format,
        from_stage.sort_order as from_stage_order,
        rules.progression_scope,
        rules.position_from,
        rules.position_to,
        rules.tie_outcome,
        rules.progression_type,
        to_stage.stage_id as to_stage_id,
        to_stage.stage_sk as to_stage_sk,
        to_stage.stage_name as to_stage_name,
        to_stage.stage_code as to_stage_code,
        to_stage.stage_format as to_stage_format,
        to_stage.sort_order as to_stage_order,
        true as is_inferred
    from season_config
    inner join rules
      on rules.season_format_code = season_config.season_format_code
    inner join stages from_stage
      on from_stage.competition_key = season_config.competition_key
     and from_stage.season_label = season_config.season_label
     and from_stage.stage_code = rules.from_stage_code
     and from_stage.stage_format = rules.from_stage_format
    left join stages to_stage
      on to_stage.competition_key = season_config.competition_key
     and to_stage.season_label = season_config.season_label
     and to_stage.stage_code = rules.to_stage_code
    where rules.to_stage_code is null
       or to_stage.stage_id is not null
)
select
    md5(
        concat_ws(
            '||',
            provider,
            competition_key,
            season_label,
            from_stage_id::text,
            coalesce(to_stage_id::text, 'terminal'),
            progression_scope,
            coalesce(tie_outcome, 'na'),
            coalesce(position_from::text, 'na'),
            coalesce(position_to::text, 'na'),
            progression_type
        )
    ) as competition_structure_rule_id,
    provider,
    competition_key,
    season_label,
    season_format_code,
    rule_order,
    from_stage_id,
    from_stage_sk,
    from_stage_name,
    from_stage_code,
    from_stage_format,
    from_stage_order,
    progression_scope,
    position_from,
    position_to,
    tie_outcome,
    progression_type,
    to_stage_id,
    to_stage_sk,
    to_stage_name,
    to_stage_code,
    to_stage_format,
    to_stage_order,
    is_inferred,
    now() as updated_at
from mapped_rules
