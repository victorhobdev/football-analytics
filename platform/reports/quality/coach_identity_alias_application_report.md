# Coach identity alias application report

## Escopo

- Run: `coach_alias_application_20260425T152648Z`
- Modo: `EXECUCAO`
- Janela de validacao publica: `2020-01-01` ate `2025-12-31`.
- Identidades antigas foram preservadas em `mart.coach_identity`.
- A unificacao publica ocorre por `mart.coach_identity_alias` e pela reatribuicao das facts para a identidade canonica.

## Antes e depois

- `active_coach_aliases`: `4` -> `4`
- `active_team_aliases`: `4` -> `4`
- `assigned_identity_distinct`: `810` -> `810`
- `assigned_name_norm_distinct`: `807` -> `807`
- `public_assignment_rows`: `19267` -> `19267`
- `rows_still_on_alias_identity`: `0` -> `0`

## Escritas

- `refreshed_canonical_identity_alias_payloads`: `3`
- `moved_source_refs`: `0`
- `moved_non_conflicting_tenures`: `0`
- `moved_fact_assignments`: `0`
- `updated_resolution_stage_rows`: `0`
- `updated_assignment_stage_rows`: `0`

## Qualidade

- `public_assignments_outside_window`: `0`
- `duplicate_match_team_rows`: `0`
- `rows_still_on_alias_identity`: `0`

## Aliases de tecnico ativos

- `Tite` <= `Adenor Bacchi` (sportmonks:474720)
- `Rafael Paiva` <= `Cledson Rafael de Paiva` (sportmonks:37690429)
- `Abel Moreira Ferreira` <= `Abel Ferreira` (wikidata:Q318415)
- `Abel Moreira Ferreira` <= `Abel Ferreira` (wikidata_P286_team_to_person:Q318415)

## Aliases de clube ativos

- `Palmeiras` <= `Sociedade Esportiva Palmeiras` (wikidata:Q80964)
- `Palmeiras` <= `Sociedade Esportiva Palmeiras` (wikidata_P286_team_to_person:Q80964)
- `Palmeiras` <= `Sociedade Esportiva Palmeiras` (manual_verified_name:-)
- `Palmeiras` <= `SE Palmeiras` (manual_verified_name:-)
