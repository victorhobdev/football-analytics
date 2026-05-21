# SportMonks reliability ingestion report

## Run

- Run id: `sportmonks_reliability_pilot_1777075981`
- API requests: `657`
- Product cutoff: `2025-12-31`

## Coach assignment coverage

- Global before: `567/34322` (1.65%)
- Global after: `8668/34322` (25.25%)
- Flamengo 2020-2025 before: `0/290` (0.0%)
- Flamengo 2020-2025 after: `114/290` (39.31%)
- Provider window 2024-2025 before: `0/9456` (0.0%)
- Provider window 2024-2025 after: `6579/9456` (69.57%)
- Flamengo 2024-2025 before: `0/114` (0.0%)
- Flamengo 2024-2025 after: `114/114` (100.0%)

## Coach ingestion

- Fixtures fetched by year: `{2020: 0, 2021: 0, 2022: 0, 2023: 0, 2024: 11683, 2025: 4896}`
- Team scopes requested by year: `{2024: 353, 2025: 176}`
- Blocked years: `{2020: ["No result(s) found matching your request. Either the query did not return any results or you don't have access to it via your current subscription."], 2021: ["No result(s) found matching your request. Either the query did not return any results or you don't have access to it via your current subscription."], 2022: ["No result(s) found matching your request. Either the query did not return any results or you don't have access to it via your current subscription."], 2023: ["No result(s) found matching your request. Either the query did not return any results or you don't have access to it via your current subscription."]}`
- Fixtures fetched total: `16579`
- Coach identities observed: `1942`
- Raw fixture-coach rows observed: `21382`
- Local public candidate rows: `8668`
- Public assignments materialized: `8668`
- Blocked conflicts materialized: `0`

## Flamengo coverage by competition

- `brasileirao_a` 2021: `0/38` (0.0%)
- `copa_do_brasil` 2021: `0/8` (0.0%)
- `libertadores` 2021: `0/13` (0.0%)
- `brasileirao_a` 2022: `0/38` (0.0%)
- `copa_do_brasil` 2022: `0/10` (0.0%)
- `libertadores` 2022: `0/13` (0.0%)
- `brasileirao_a` 2023: `0/38` (0.0%)
- `copa_do_brasil` 2023: `0/10` (0.0%)
- `libertadores` 2023: `0/8` (0.0%)
- `brasileirao_a` 2024: `38/38` (100.0%)
- `copa_do_brasil` 2024: `10/10` (100.0%)
- `libertadores` 2024: `10/10` (100.0%)
- `brasileirao_a` 2025: `38/38` (100.0%)
- `copa_do_brasil` 2025: `4/4` (100.0%)
- `libertadores` 2025: `13/13` (100.0%)
- `supercopa_do_brasil` 2025: `1/1` (100.0%)

## Transfer ingestion

- Everton Ribeiro events fetched: `4`
- December 2023 window events fetched: `2587`
- Unique transfer events upserted: `2591`
- Type distribution: `{'219': 433, '220': 208, '9688': 1828, '218': 122}`

## Table counts

- `raw.sportmonks_coaches`: `1942` -> `1942`
- `raw.sportmonks_fixture_coaches`: `21382` -> `21382`
- `raw.sportmonks_transfer_events`: `2591` -> `2591`
- `mart.stg_sportmonks_fixture_coach_assignments`: `21382` -> `21382`
- `mart.stg_sportmonks_transfer_events`: `2591` -> `2591`
- `mart.coach_identity`: `1942` -> `1942`
- `mart.stg_coach_lineup_assignments`: `8668` -> `8668`
- `mart.fact_coach_match_assignment`: `8668` -> `8668`
- `raw.player_transfers`: `61213` -> `61213`
- `mart.stg_player_transfers`: `61213` -> `61213`

## Residual blockers

- SportMonks did not return Flamengo fixtures for 2020-2023 with the current subscription/historical coverage.
- Older coach assignments remain blocked until historical add-on/data access or fallback manual source is available.
- `coach_tenure` remains derived from match assignments; it was not treated as authoritative.
- Transfer currency remains null unless a trusted enrichment source supplies it.
