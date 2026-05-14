with matches as (
    select
        md5(concat('competition:', league_id::text)) as competition_sk,
        league_id,
        season,
        match_id,
        round as round_label,
        coalesce((regexp_match(round, '([0-9]+)'))[1]::int, 0) as round_number_api,
        date_day,
        home_team_id,
        away_team_id,
        coalesce(home_goals, 0) as home_goals,
        coalesce(away_goals, 0) as away_goals
    from {{ ref('int_matches_enriched') }}
    where league_id is not null
      and season is not null
      and match_id is not null
      and home_team_id is not null
      and away_team_id is not null
),
matches_with_round_key as (
    select
        competition_sk,
        league_id,
        season,
        match_id,
        round_label,
        case
            when round_number_api > 0 then round_number_api
            else dense_rank() over (
                partition by competition_sk, season
                order by date_day nulls last, match_id
            )
        end as round_key,
        date_day,
        home_team_id,
        away_team_id,
        home_goals,
        away_goals
    from matches
),
team_match_rows as (
    select
        competition_sk,
        league_id,
        season,
        match_id,
        round_key,
        round_label,
        date_day,
        md5(concat('team:', home_team_id::text)) as team_sk,
        home_team_id as team_id,
        home_goals as goals_for,
        away_goals as goals_against,
        case when home_goals > away_goals then 1 else 0 end as wins_in_match,
        case
            when home_goals > away_goals then 3
            when home_goals = away_goals then 1
            else 0
        end as points_in_match
    from matches_with_round_key

    union all

    select
        competition_sk,
        league_id,
        season,
        match_id,
        round_key,
        round_label,
        date_day,
        md5(concat('team:', away_team_id::text)) as team_sk,
        away_team_id as team_id,
        away_goals as goals_for,
        home_goals as goals_against,
        case when away_goals > home_goals then 1 else 0 end as wins_in_match,
        case
            when away_goals > home_goals then 3
            when away_goals = home_goals then 1
            else 0
        end as points_in_match
    from matches_with_round_key
),
deduped_match_team as (
    select
        competition_sk,
        league_id,
        season,
        match_id,
        round_key,
        round_label,
        date_day,
        team_sk,
        team_id,
        goals_for,
        goals_against,
        wins_in_match,
        points_in_match
    from (
        select
            tm.*,
            row_number() over (
                partition by tm.competition_sk, tm.season, tm.match_id, tm.team_id
                order by tm.round_key desc, tm.date_day desc nulls last, tm.match_id desc
            ) as row_num
        from team_match_rows tm
    ) ranked_match_team
    where row_num = 1
),
points_by_round as (
    select
        competition_sk,
        league_id,
        season,
        round_key,
        min(round_label) as round_label,
        team_sk,
        team_id,
        sum(points_in_match)::int as points_in_round,
        sum(goals_for)::int as goals_for_round,
        sum(goals_for - goals_against)::int as goal_diff_round,
        sum(wins_in_match)::int as wins_in_round
    from deduped_match_team
    group by competition_sk, league_id, season, round_key, team_sk, team_id
),
accumulated as (
    select
        competition_sk,
        league_id,
        season,
        round_key,
        coalesce(round_label, concat('Round ', round_key::text)) as round_label,
        team_sk,
        team_id,
        sum(points_in_round) over (
            partition by competition_sk, season, team_id
            order by round_key
            rows between unbounded preceding and current row
        )::int as points_accumulated,
        sum(goals_for_round) over (
            partition by competition_sk, season, team_id
            order by round_key
            rows between unbounded preceding and current row
        )::int as goals_for_accumulated,
        sum(goal_diff_round) over (
            partition by competition_sk, season, team_id
            order by round_key
            rows between unbounded preceding and current row
        )::int as goal_diff_accumulated,
        sum(wins_in_round) over (
            partition by competition_sk, season, team_id
            order by round_key
            rows between unbounded preceding and current row
        )::int as wins_accumulated
    from points_by_round
),
ranked as (
    select
        competition_sk,
        league_id,
        season,
        round_key,
        round_key as round,
        round_label,
        team_sk,
        team_id,
        points_accumulated,
        goals_for_accumulated,
        goal_diff_accumulated,
        dense_rank() over (
            partition by competition_sk, season, round_key
            order by
                points_accumulated desc,
                wins_accumulated desc,
                goal_diff_accumulated desc,
                goals_for_accumulated desc,
                team_sk asc
        )::int as position
    from accumulated
)
select * from ranked
