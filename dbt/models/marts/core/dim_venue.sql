with fixtures as (
    select * from {{ source('postgres_raw', 'fixtures') }}
)
select distinct
    venue_id,
    venue_name,
    venue_city,
    now() as updated_at
from fixtures
where venue_id is not null
  and venue_name is not null
