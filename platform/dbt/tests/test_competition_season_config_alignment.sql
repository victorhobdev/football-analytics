with config_rows as (
    select
        competition_key,
        season_label
    from {{ ref('competition_season_config') }}
    where competition_key in ('copa_do_brasil', 'libertadores', 'champions_league')
),
catalog_rows as (
    select
        competition_key,
        season_label
    from control.season_catalog
)
select
    c.competition_key,
    c.season_label
from config_rows c
left join catalog_rows s
  on s.competition_key = c.competition_key
 and s.season_label = c.season_label
where s.competition_key is null
