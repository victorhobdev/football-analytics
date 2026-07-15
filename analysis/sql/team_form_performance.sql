\set ON_ERROR_STOP on
\timing on

-- Case único: forma recente, consistência e posição relativa dos times.
-- Tudo ocorre em tabela temporária e termina com ROLLBACK; o banco não é alterado.
begin;

-- Baseline: a cada análise, reconstruir time-partida a partir de mart.fact_matches.
explain (analyze, buffers, format text)
with team_match as materialized (
    select provider, competition_key, season_label, match_id, date_day match_date,
           home_team_sk team_sk,
           case when home_goals > away_goals then 3 when home_goals = away_goals then 1 else 0 end points
    from mart.fact_matches
    where home_goals is not null and away_goals is not null
    union all
    select provider, competition_key, season_label, match_id, date_day,
           away_team_sk,
           case when away_goals > home_goals then 3 when away_goals = home_goals then 1 else 0 end
    from mart.fact_matches
    where home_goals is not null and away_goals is not null
), sequenced as (
    select *,
           lag(points) over team_calendar previous_points,
           lead(points) over team_calendar next_points,
           avg(points) over team_form form_5_ppg,
           stddev_samp(points) over team_form form_5_stddev,
           row_number() over (
               partition by provider, competition_key, season_label, team_sk
               order by match_date desc, match_id desc
           ) recency
    from team_match
    window
        team_calendar as (
            partition by provider, competition_key, season_label, team_sk
            order by match_date, match_id
        ),
        team_form as (
            partition by provider, competition_key, season_label, team_sk
            order by match_date, match_id rows between 4 preceding and current row
        )
), season_totals as (
    select provider, competition_key, season_label, team_sk,
           count(*) matches, sum(points) points, avg(points) ppg
    from team_match
    group by 1, 2, 3, 4
), current_form as (
    select provider, competition_key, season_label, team_sk,
           previous_points, next_points, form_5_ppg, form_5_stddev
    from sequenced
    where recency = 1
), ranked as (
    select totals.*, current_form.previous_points, current_form.next_points,
           current_form.form_5_ppg, current_form.form_5_stddev,
           rank() over scope_rank points_rank,
           percent_rank() over scope_rank points_percentile,
           ntile(4) over scope_rank performance_quartile
    from season_totals totals
    join current_form using (provider, competition_key, season_label, team_sk)
    window scope_rank as (
        partition by provider, competition_key, season_label
        order by points desc, ppg desc, team_sk
    )
)
select count(*) teams,
       round(avg(form_5_ppg)::numeric, 4) average_form_5,
       round(avg(form_5_stddev)::numeric, 4) average_consistency,
       sum(coalesce(previous_points, 0) + coalesce(next_points, 0)) sequence_check,
       max(points_rank) largest_rank,
       round(avg(points_percentile)::numeric, 4) average_percentile,
       max(performance_quartile) quartiles
from ranked;

-- Otimização para uso recorrente: materializar uma vez o grão time-partida e indexar
-- exatamente a partição/ordenação usada pelas janelas.
create temp table tmp_team_match on commit drop as
select provider, competition_key, season_label, match_id, date_day match_date,
       home_team_sk team_sk,
       case when home_goals > away_goals then 3 when home_goals = away_goals then 1 else 0 end points
from mart.fact_matches
where home_goals is not null and away_goals is not null
union all
select provider, competition_key, season_label, match_id, date_day,
       away_team_sk,
       case when away_goals > home_goals then 3 when away_goals = home_goals then 1 else 0 end
from mart.fact_matches
where home_goals is not null and away_goals is not null;

create index tmp_team_match_scope_calendar
    on tmp_team_match (provider, competition_key, season_label, team_sk, match_date, match_id);
analyze tmp_team_match;

explain (analyze, buffers, format text)
with sequenced as (
    select *,
           lag(points) over team_calendar previous_points,
           lead(points) over team_calendar next_points,
           avg(points) over team_form form_5_ppg,
           stddev_samp(points) over team_form form_5_stddev,
           row_number() over (
               partition by provider, competition_key, season_label, team_sk
               order by match_date desc, match_id desc
           ) recency
    from tmp_team_match
    window
        team_calendar as (
            partition by provider, competition_key, season_label, team_sk
            order by match_date, match_id
        ),
        team_form as (
            partition by provider, competition_key, season_label, team_sk
            order by match_date, match_id rows between 4 preceding and current row
        )
), season_totals as (
    select provider, competition_key, season_label, team_sk,
           count(*) matches, sum(points) points, avg(points) ppg
    from tmp_team_match
    group by 1, 2, 3, 4
), current_form as (
    select provider, competition_key, season_label, team_sk,
           previous_points, next_points, form_5_ppg, form_5_stddev
    from sequenced
    where recency = 1
), ranked as (
    select totals.*, current_form.previous_points, current_form.next_points,
           current_form.form_5_ppg, current_form.form_5_stddev,
           rank() over scope_rank points_rank,
           percent_rank() over scope_rank points_percentile,
           ntile(4) over scope_rank performance_quartile
    from season_totals totals
    join current_form using (provider, competition_key, season_label, team_sk)
    window scope_rank as (
        partition by provider, competition_key, season_label
        order by points desc, ppg desc, team_sk
    )
)
select count(*) teams,
       round(avg(form_5_ppg)::numeric, 4) average_form_5,
       round(avg(form_5_stddev)::numeric, 4) average_consistency,
       sum(coalesce(previous_points, 0) + coalesce(next_points, 0)) sequence_check,
       max(points_rank) largest_rank,
       round(avg(points_percentile)::numeric, 4) average_percentile,
       max(performance_quartile) quartiles
from ranked;

-- Reconciliação com as medidas DAX Pontos, PPG e PPG Últimos 5.
with sequenced as (
    select *,
           avg(points) over (
               partition by provider, competition_key, season_label, team_sk
               order by match_date, match_id rows between 4 preceding and current row
           ) form_5_ppg,
           row_number() over (
               partition by provider, competition_key, season_label, team_sk
               order by match_date desc, match_id desc
           ) recency
    from tmp_team_match
    where provider = 'sportmonks'
      and competition_key = 'la_liga'
      and season_label = '2024_25'
), totals as (
    select team_sk, count(*) matches, sum(points) points, avg(points) ppg
    from sequenced group by team_sk
), current_form as (
    select team_sk, form_5_ppg from sequenced where recency = 1
), ranked as (
    select totals.*, current_form.form_5_ppg,
           rank() over (order by points desc, ppg desc, team_sk) points_rank
    from totals join current_form using (team_sk)
)
select team.team_name, ranked.matches, ranked.points,
       round(ranked.ppg::numeric, 4) ppg,
       round(ranked.form_5_ppg::numeric, 4) form_5_ppg,
       ranked.points_rank
from ranked
join mart.dim_team team using (team_sk)
order by points_rank, team.team_name;

rollback;
