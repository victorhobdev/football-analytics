-- Regra: movement_kind canonico deve preservar a semantica dos tipos SportMonks.
-- Tabela: stg_player_transfers
-- Rationale: type_id 9688 e retorno de emprestimo, nao transferencia definitiva.

select
    transfer_id,
    type_id,
    movement_kind,
    career_ended
from {{ ref('stg_player_transfers') }}
where (
    career_ended is true
    and movement_kind <> 'career_end'
)
or (
    coalesce(career_ended, false) is false
    and (
        (type_id = 219 and movement_kind <> 'permanent_transfer')
        or (type_id = 218 and movement_kind <> 'loan_out')
        or (type_id = 9688 and movement_kind <> 'loan_return')
        or (type_id = 220 and movement_kind <> 'free_transfer')
        or (type_id not in (219, 218, 9688, 220) and movement_kind <> 'unknown')
    )
)
