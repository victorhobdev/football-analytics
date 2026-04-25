# External coach promotion report

## Escopo

- Modo: `EXECUCAO`
- Fonte promovida: `external_wikidata_P286`
- Janela: `2020-01-01` ate `2025-12-31`
- Apenas candidatos `promotion_status = promotable`.
- `review_needed` e `blocked_conflict` nao foram promovidos.

## Preflight

- `promotable_rows`: `8201`
- `promotable_match_teams`: `8201`
- `promotable_coach_keys`: `280`
- `outside_window`: `0`
- `would_overwrite_protected_assignment`: `0`
- `unresolved_match_team_conflicts`: `0`
- `bad_roles`: `0`
- `non_p286_candidates`: `0`
- `invalid_external_person_id`: `0`
- `invalid_dates`: `0`
- `invalid_names`: `0`
- `identity_conflicts`: `0`

## Escritas

- `identities`: `144`
- `identity_refs`: `560`
- `tenures`: `340`
- `assignments`: `8201`

## Antes e depois

- `coach_identity`: `1959` -> `2103` (`+144`)
- `coach_identity_source_ref`: `0` -> `560` (`+560`)
- `coach_tenure`: `0` -> `340` (`+340`)
- `fact_assignment`: `10903` -> `19104` (`+8201`)
- `fact_public`: `10903` -> `19104` (`+8201`)

## Qualidade pos-promocao

- `external_outside_window`: `0`
- `duplicate_match_team_rows`: `0`
- `external_bad_roles`: `0`
- `external_invalid_names`: `0`

## Leitura

- A promocao e idempotente: rodar de novo atualiza as mesmas linhas externas sem duplicar.
- Assignments existentes de outras fontes nao sao sobrescritos.
- A UI ainda precisa consumir `fact_coach_match_assignment` para refletir a melhoria na pagina de tecnicos.
