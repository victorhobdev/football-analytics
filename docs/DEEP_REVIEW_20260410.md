# Revisão profunda (domínio + persistência + regressão) — 2026-04-10

## Escopo analisado
- Modelagem e regras de domínio em dbt (`stg_matches`, `int_matches_enriched`, `int_tie_matches`, `int_tie_results`, `fact_standings_snapshots`).
- Persistência em Airflow services e migrations (`warehouse_service`, `standings_mapper`, schema/migrations de `raw`).
- Proteções de regressão em testes Python e dbt.

## Achados prioritários

### 1) Partidas não finalizadas viram empate 0x0 no fato
- Evidência: o enriquecimento usa `COALESCE(home_goals, 0)`/`COALESCE(away_goals, 0)` e força `result='Draw'` quando gols estão nulos; não há filtro por status de finalização. 
- Impacto: partidas `NS`, `PST`, canceladas ou em andamento podem contaminar analytics como se fossem jogos concluídos.

### 2) Resolução de mata-mata ignora regras de desempate por competição/temporada
- Evidência: `int_tie_results` decide vencedor por agregado simples e pênaltis/eventos; `tie_rule_code` do catálogo de temporada não é aplicado na resolução.
- Impacto: risco de campeão/classificado errado em formatos históricos ou específicos (ex.: regra de gol fora, exceções regulamentares).

### 3) Standings mapeadas com `stage_id/round_id=0` por default + deduplicação "keep=last"
- Evidência: mapper converte ausências para `0` e depois deduplica por chave canônica, descartando linhas silenciosamente.
- Impacto: colapso de snapshots distintos na mesma chave e perda silenciosa de estado da competição.

### 4) Integridade relacional fraca no raw para entidades estendidas
- Evidência: tabelas como `raw.standings_snapshots`/`raw.fixture_lineups` têm PK, mas sem FKs para fixtures/teams/stages/rounds.
- Impacto: banco aceita combinações tecnicamente válidas e semanticamente inválidas (órfãos), gerando joins inconsistentes no mart.

### 5) Migrations canônicas rígidas e frágeis ao ambiente
- Evidência: assertivas exigem contagens e nomes específicos de índices/objetos; pequenas variações operacionais quebram migração mesmo sem risco real aos dados.
- Impacto: bloqueio de deploy e evolução segura por acoplamento a estado exato do catálogo.

### 6) Gaps de regressão em fluxos críticos de domínio
- Evidência: há testes para vários mappers, mas não para `standings_mapper`; há testes de formato/consistência, porém sem proteção explícita para status de partida (não finalizada) no caminho de facts/resultados.
- Impacto: regressões em snapshots/resultado esportivo passam despercebidas.
