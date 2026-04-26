# Data quality closure report

## Status

Fechado no escopo controlavel localmente.

Este fechamento cobre as recomendacoes executaveis sem reprocessamento amplo, sem revisao manual de candidatos ambiguos e sem depender de nova cobertura de provider.

## Blocos concluidos

- Contrato editorial minimo criado em `quality/editorial-data-quality-contract.md`.
- Inventario SQL criado e executado em `quality/data_quality_inventory.sql`.
- Rotas publicas de mercado neutralizam sentinels tecnicos e nao inventam moeda.
- `type_id = 9688` e tratado como `loan_return` no BFF e em `mart.stg_player_transfers.movement_kind`.
- Rota publica de mercado filtra eventos depois de `PRODUCT_DATA_CUTOFF`.
- Rota publica de tecnicos neutraliza nomes de time/tecnico tecnicos e nao trata placeholder como foto real.
- World Cup expoe contrato comum de identidade para `competition`, `team` e `player`.
- Backfill seguro de tecnicos foi executado de forma idempotente e auditado.
- Quality gates semanticos foram adicionados para dimensoes publicas, competicoes, imagens placeholder, tecnico-performance, atribuicoes publicas e movement kind de transferencias.

## Limitacoes transformadas em estado explicito

- Cobertura historica de tecnicos segue limitada por payload indisponivel ou candidatos que exigem segunda fonte/revisao manual.
- Imagens placeholder ainda existem como dado operacional, mas sao classificadas e bloqueadas como foto real na superficie ajustada.
- World Cup ainda tem router dedicado, mas o payload publico agora segue o contrato comum de identidade.

## Validacoes finais

- API: `python -m pytest api/tests/test_coaches_routes.py api/tests/test_market_routes.py api/tests/test_world_cup_routes.py api/tests/test_public_surface_contract.py -q`
- dbt: `dbt test` dos seis gates semanticos.
- Frontend: `pnpm typecheck` e `pnpm build`.
- Smoke real da rota de mercado confirmou `future_items=0` para `PRODUCT_DATA_CUTOFF=2025-12-31`.

## Nota operacional

`pnpm lint` nao existe em `frontend/package.json`; as validacoes disponiveis no frontend sao `typecheck` e `build`.
