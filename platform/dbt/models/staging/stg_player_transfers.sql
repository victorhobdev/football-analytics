with source_transfers as (
    select * from {{ source('postgres_raw', 'player_transfers') }}
)
select
    provider,
    transfer_id,
    player_id,
    nullif(trim(coalesce(payload -> 'player' ->> 'name', payload ->> 'player_name')), '') as player_name,
    from_team_id,
    to_team_id,
    transfer_date,
    completed,
    career_ended,
    type_id,
    case
        when career_ended then 'career_end'
        when type_id = 219 then 'permanent_transfer'
        when type_id = 218 then 'loan_out'
        when type_id = 9688 then 'loan_return'
        when type_id = 220 then 'free_transfer'
        else 'unknown'
    end as movement_kind,
    position_id,
    amount,
    payload,
    ingested_run,
    updated_at
from source_transfers
