{{ config(materialized='view') }}

with elo_matches as (
    select * from {{ source('postgres_raw', 'elo_matches') }}
),
resolved as (
    select
        em.record_hash as elo_match_hash,
        coalesce(
            case
                when ex.identity_status = 'linked_to_sportmonks' then ex.local_fixture_id
                else null
            end,
            case
                when px.publication_status = 'publishable' then px.canonical_external_match_id
                else null
            end
        ) as match_id,
        ex.identity_status,
        px.publication_status,
        ex.competition_key,
        em.division,
        ex.match_date,
        em.home_team_name,
        em.away_team_name,
        case when nullif(trim(em.home_elo_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_elo_raw)::numeric else null end as home_elo,
        case when nullif(trim(em.away_elo_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_elo_raw)::numeric else null end as away_elo,
        case when nullif(trim(em.form3_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.form3_home_raw)::numeric else null end as form3_home,
        case when nullif(trim(em.form5_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.form5_home_raw)::numeric else null end as form5_home,
        case when nullif(trim(em.form3_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.form3_away_raw)::numeric else null end as form3_away,
        case when nullif(trim(em.form5_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.form5_away_raw)::numeric else null end as form5_away,
        case when nullif(trim(em.ft_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.ft_home_raw)::numeric else null end as ft_home_goals,
        case when nullif(trim(em.ft_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.ft_away_raw)::numeric else null end as ft_away_goals,
        em.ft_result,
        case when nullif(trim(em.ht_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.ht_home_raw)::numeric else null end as ht_home_goals,
        case when nullif(trim(em.ht_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.ht_away_raw)::numeric else null end as ht_away_goals,
        em.ht_result,
        case when nullif(trim(em.home_shots_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_shots_raw)::numeric else null end as home_shots,
        case when nullif(trim(em.away_shots_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_shots_raw)::numeric else null end as away_shots,
        case when nullif(trim(em.home_target_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_target_raw)::numeric else null end as home_shots_on_target,
        case when nullif(trim(em.away_target_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_target_raw)::numeric else null end as away_shots_on_target,
        case when nullif(trim(em.home_fouls_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_fouls_raw)::numeric else null end as home_fouls,
        case when nullif(trim(em.away_fouls_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_fouls_raw)::numeric else null end as away_fouls,
        case when nullif(trim(em.home_corners_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_corners_raw)::numeric else null end as home_corners,
        case when nullif(trim(em.away_corners_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_corners_raw)::numeric else null end as away_corners,
        case when nullif(trim(em.home_yellow_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_yellow_raw)::numeric else null end as home_yellow_cards,
        case when nullif(trim(em.away_yellow_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_yellow_raw)::numeric else null end as away_yellow_cards,
        case when nullif(trim(em.home_red_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.home_red_raw)::numeric else null end as home_red_cards,
        case when nullif(trim(em.away_red_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.away_red_raw)::numeric else null end as away_red_cards,
        case when nullif(trim(em.odd_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.odd_home_raw)::numeric else null end as odd_home,
        case when nullif(trim(em.odd_draw_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.odd_draw_raw)::numeric else null end as odd_draw,
        case when nullif(trim(em.odd_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.odd_away_raw)::numeric else null end as odd_away,
        case when nullif(trim(em.max_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.max_home_raw)::numeric else null end as max_home,
        case when nullif(trim(em.max_draw_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.max_draw_raw)::numeric else null end as max_draw,
        case when nullif(trim(em.max_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.max_away_raw)::numeric else null end as max_away,
        case when nullif(trim(em.over25_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.over25_raw)::numeric else null end as over25,
        case when nullif(trim(em.under25_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.under25_raw)::numeric else null end as under25,
        case when nullif(trim(em.max_over25_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.max_over25_raw)::numeric else null end as max_over25,
        case when nullif(trim(em.max_under25_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.max_under25_raw)::numeric else null end as max_under25,
        case when nullif(trim(em.handi_size_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.handi_size_raw)::numeric else null end as handicap_size,
        case when nullif(trim(em.handi_home_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.handi_home_raw)::numeric else null end as handicap_home,
        case when nullif(trim(em.handi_away_raw), '') ~ '^-?[0-9]+(\.[0-9]+)?$' then trim(em.handi_away_raw)::numeric else null end as handicap_away,
        em.ingested_at,
        row_number() over (
            partition by coalesce(
                case when ex.identity_status = 'linked_to_sportmonks' then ex.local_fixture_id else null end,
                case when px.publication_status = 'publishable' then px.canonical_external_match_id else null end
            )
            order by
                case when ex.identity_status = 'linked_to_sportmonks' then 0 else 1 end,
                em.record_hash
        ) as match_row_num
    from elo_matches em
    inner join control.elo_match_xref ex
      on ex.elo_match_hash = em.record_hash
    left join control.external_match_publication_xref px
      on px.source = 'eloratings'
     and px.source_entity_id = em.record_hash
    where ex.identity_status in ('linked_to_sportmonks', 'new_coverage')
)
select *
from resolved
where match_id is not null
  and match_row_num = 1
