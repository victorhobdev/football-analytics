with match_source as (
{% if var('canonical_snapshot_schema', '') %}
    select
        f.match_id as fixture_id,
        f.provider,
        f.provider_league_id,
        f.competition_key,
        f.season_label,
        f.stage_id,
        f.round_id,
        f.round_name,
        f.date_day::timestamp as date_utc,
        'FT'::text as status_short,
        'Finished'::text as status_long,
        f.leg_number,
        f.home_team_id,
        h.team_name as home_team_name,
        f.away_team_id,
        a.team_name as away_team_name,
        f.home_goals,
        f.away_goals
    from {{ adapter.quote(var('canonical_snapshot_schema')) }}.fact_matches f
    join {{ adapter.quote(var('canonical_snapshot_schema')) }}.dim_team h on h.team_id = f.home_team_id
    join {{ adapter.quote(var('canonical_snapshot_schema')) }}.dim_team a on a.team_id = f.away_team_id
{% else %}
    select * from {{ ref('stg_matches') }}
{% endif %}
),
season_config as (
    select
        competition_key,
        season_label,
        format_family
    from {{ ref('competition_season_config') }}
),
stage_context as (
    select
        provider,
        competition_key,
        season_label,
        stage_id,
        stage_sk,
        stage_name,
        stage_format,
        sort_order
    from {{ ref('dim_stage') }}
    where stage_format in ('knockout', 'qualification_knockout')
),
pure_knockout_matches as (
    select
        m.fixture_id as match_id,
        m.provider,
        m.provider_league_id,
        m.competition_key,
        m.season_label,
        m.stage_id,
        s.stage_sk,
        s.stage_name,
        s.stage_format,
        s.sort_order as stage_order,
        m.round_id,
        m.round_name,
        m.date_utc,
        m.status_short,
        m.status_long,
        case
            when m.leg_number is not null and m.leg_number > 0 then m.leg_number
            else null
        end as raw_leg_number,
        m.home_team_id,
        m.home_team_name,
        m.away_team_id,
        m.away_team_name,
        m.home_goals,
        m.away_goals,
        least(m.home_team_id, m.away_team_id) as team_pair_lo,
        greatest(m.home_team_id, m.away_team_id) as team_pair_hi
    from match_source m
    join season_config c
      on c.competition_key = m.competition_key
     and c.season_label = m.season_label
    join stage_context s
      on s.provider = m.provider
     and s.competition_key = m.competition_key
     and s.season_label = m.season_label
     and s.stage_id = m.stage_id
),
ordered_matches as (
    select
        m.*,
        row_number() over (
            partition by m.provider, m.competition_key, m.season_label, m.stage_id, m.team_pair_lo, m.team_pair_hi
            order by
                case when m.raw_leg_number is null then 1 else 0 end,
                m.raw_leg_number,
                m.date_utc,
                m.match_id
        ) as leg_sequence,
        count(*) over (
            partition by m.provider, m.competition_key, m.season_label, m.stage_id, m.team_pair_lo, m.team_pair_hi
        ) as match_count
    from pure_knockout_matches m
),
first_legs as (
    select *
    from ordered_matches
    where leg_sequence = 1
),
tie_base as (
    select
        fl.provider,
        fl.provider_league_id,
        fl.competition_key,
        fl.season_label,
        fl.stage_id,
        fl.stage_sk,
        fl.stage_name,
        fl.stage_format,
        fl.stage_order,
        fl.team_pair_lo,
        fl.team_pair_hi,
        md5(
            concat_ws(
                '||',
                'tie',
                fl.provider,
                fl.competition_key,
                fl.season_label,
                fl.stage_id::text,
                fl.team_pair_lo::text,
                fl.team_pair_hi::text
            )
        ) as tie_id,
        row_number() over (
            partition by fl.provider, fl.competition_key, fl.season_label, fl.stage_id
            order by fl.date_utc, fl.match_id, fl.team_pair_lo, fl.team_pair_hi
        ) as tie_order,
        fl.home_team_id as home_side_team_id,
        fl.home_team_name as home_side_team_name,
        fl.away_team_id as away_side_team_id,
        fl.away_team_name as away_side_team_name,
        true as is_inferred
    from first_legs fl
),
match_tie_context as (
    select
        om.match_id,
        om.provider,
        om.provider_league_id,
        om.competition_key,
        om.season_label,
        om.stage_id,
        om.stage_sk,
        om.stage_name,
        om.stage_format,
        om.stage_order,
        tb.tie_id,
        tb.tie_order,
        tb.home_side_team_id,
        tb.home_side_team_name,
        tb.away_side_team_id,
        tb.away_side_team_name,
        om.home_team_id,
        om.home_team_name,
        om.away_team_id,
        om.away_team_name,
        om.home_goals,
        om.away_goals,
        om.status_short,
        om.status_long,
        om.date_utc,
        om.match_count,
        coalesce(om.raw_leg_number, om.leg_sequence) as inferred_leg_number,
        case
            when om.home_team_id = tb.home_side_team_id then om.home_goals
            when om.away_team_id = tb.home_side_team_id then om.away_goals
            else null
        end as home_side_goals,
        case
            when om.home_team_id = tb.away_side_team_id then om.home_goals
            when om.away_team_id = tb.away_side_team_id then om.away_goals
            else null
        end as away_side_goals,
        case when om.status_short = 'FTP' then true else false end as has_penalties_status,
        case when om.status_short = 'AET' then true else false end as has_extra_time_status,
        tb.is_inferred
    from ordered_matches om
    join tie_base tb
      on tb.provider = om.provider
     and tb.competition_key = om.competition_key
     and tb.season_label = om.season_label
     and tb.stage_id = om.stage_id
     and tb.team_pair_lo = om.team_pair_lo
     and tb.team_pair_hi = om.team_pair_hi
)
select *
from match_tie_context
