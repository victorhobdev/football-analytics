{{ config(materialized='view') }}

select
    tm_player_id,
    local_player_id as player_id,
    md5(concat('player:', local_player_id::text)) as player_sk,
    player_name_raw,
    confidence,
    match_method
from control.tm_player_xref
where identity_status = 'linked_to_local_player'
  and review_status = 'auto_approved'
  and local_player_id is not null
