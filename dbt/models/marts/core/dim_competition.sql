with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
)
select distinct
    league_id,
    league_name,
    cast(null as text) as country,
    now() as updated_at
from fixtures
where league_id is not null
  and league_name is not null
