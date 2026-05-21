# Publicacao serving 2025

Este diretorio define a publicacao correta para producao: banco enxuto de serving,
sem dump completo de pipeline, e assets visuais fora do banco.

## Diagnostico objetivo

O produto e fechado: somente competicoes suportadas e temporadas encerradas ate
2025. O dump completo de aproximadamente 9 GB publicado na Oracle inclui camadas
de pipeline e historico que nao sao necessarias em runtime.

Evidencia de uso em runtime:

- A API troca de banco por configuracao em `api/src/core/config.py`: primeiro
  `FOOTBALL_PG_DSN`, depois `DATABASE_URL`, depois `POSTGRES_*`.
- Os routers da API consultam apenas os objetos listados abaixo.
- O frontend resolve logos em `/api/visual-assets/{clubs|competitions|players}/{id}`.
- As imagens de campeao usam paths estaticos em
  `/images/competition-season/editions/...`.

## Escopo de serving

Objetos diretos e de suporte para a API/frontend atual:

- `publication.serving_scope`
- `mart_control.competition_season_config`
- `control.historical_stat_definitions`
- `mart.competition_historical_stats`
- `mart.competition_structure_hub`
- `mart.dim_coach`
- `mart.dim_competition`
- `mart.dim_date`
- `mart.dim_group`
- `mart.dim_player`
- `mart.dim_round`
- `mart.dim_stage`
- `mart.dim_team`
- `mart.dim_tie`
- `mart.dim_venue`
- `mart.fact_fixture_lineups`
- `mart.fact_fixture_player_stats`
- `mart.fact_group_standings`
- `mart.fact_match_events`
- `mart.fact_matches`
- `mart.fact_stage_progression`
- `mart.fact_tie_results`
- `mart.player_match_summary`
- `mart.stg_player_transfers`
- `mart.stg_team_coaches`
- `raw.competition_rounds`
- `raw.competition_stages`
- `raw.fixture_lineups`
- `raw.fixture_player_statistics`
- `raw.fixtures`
- `raw.match_events`
- `raw.match_statistics`
- `raw.standings_snapshots`

Observacao: `mart.stg_player_transfers` e `mart.stg_team_coaches` mantem nome de
staging, mas sao serving enquanto os endpoints atuais dependem delas.

Fora do serving:

- schemas `bronze` e `silver`
- Airflow, dbt runtime, Great Expectations, MinIO e Metabase
- tabelas raw nao listadas acima
- tabelas mart nao consultadas pelos routers atuais
- dump historico completo e dados de ingestao

## Escopo de dados

O script `load_serving_subset_from_source.sql` cria `publication.serving_scope`
com as competicoes suportadas pelo frontend e temporadas fechadas ate 2025.

Inclui:

- competicoes: `brasileirao_a`, `brasileirao_b`, `libertadores`,
  `sudamericana`, `copa_do_brasil`, `supercopa_do_brasil`,
  `fifa_intercontinental_cup`, `premier_league`, `champions_league`,
  `la_liga`, `serie_a_italy`, `bundesliga`, `ligue_1`, `primeira_liga`
- temporadas anuais encerradas 2021 a 2025, quando suportadas
- temporadas europeias encerradas de `2021_22` a `2024_25`
- aliases/source ids usados pelo produto, como `71/648`, `390/1122` e `732/654`
- alias de API: `serie_a_italy` e publicado no frontend, mas o banco/API usam
  `serie_a_it` como chave interna de serving

Nao inclui temporada futura ou dados fora das competicoes publicadas.

## Geracao do snapshot

Executar sempre contra banco candidato novo, vazio e paralelo. Nao rodar contra o
banco atualmente publicado.

Pre-condicao: o usuario que executa o carregamento no candidato precisa poder
criar a extensao `postgres_fdw` para a carga.

1. Criar banco candidato.

```powershell
createdb football_serving_candidate
```

2. Restaurar somente DDL do banco fonte para o candidato.

```powershell
pg_dump $env:SOURCE_DSN --schema-only --schema=control --schema=mart_control --schema=mart --schema=raw --no-owner --no-acl | psql $env:CANDIDATE_DSN
```

3. Carregar somente o subset de serving.

```powershell
psql $env:CANDIDATE_DSN `
  -v source_host=$env:SOURCE_PGHOST `
  -v source_port=$env:SOURCE_PGPORT `
  -v source_db=$env:SOURCE_PGDATABASE `
  -v source_user=$env:SOURCE_PGUSER `
  -v source_password=$env:SOURCE_PGPASSWORD `
  -f db/publication/load_serving_subset_from_source.sql
```

4. Validar o candidato.

```powershell
psql $env:CANDIDATE_DSN -f db/publication/validate_serving_snapshot.sql
```

Resultado esperado:

- todos os `required_objects` com `exists_in_candidate = true`
- `out_of_scope_matches = 0`
- `future_matches_after_2025 = 0`
- `raw_fixture_orphans = 0`
- `event_orphans = 0`
- `lineup_orphans = 0`
- `player_stat_orphans = 0`
- `fdw_source_server_leftover = 0`
- `foreign_source_schemas_leftover = 0`
- contagem por competicao/temporada compativel com o portfolio publicado

5. Gerar dump enxuto.

```powershell
pg_dump -Fc $env:CANDIDATE_DSN -f artifacts/football_serving_2025.dump
```

## Substituicao segura

Fluxo correto:

1. Restaurar `football_serving_2025.dump` em banco novo na Oracle, por exemplo
   `football_serving_2025`.
2. Criar usuario read-only da aplicacao para esse banco.
3. Rodar `validate_serving_snapshot.sql` na Oracle contra o banco novo.
4. Subir a API apontando para o banco novo em ambiente paralelo ou porta interna.
5. Rodar os testes minimos de API, paginas e assets.
6. Trocar a API publicada alterando apenas a configuracao de banco.

Variavel preferencial para troca:

```text
FOOTBALL_PG_DSN=postgresql://app_user:***@127.0.0.1:5432/football_serving_2025
```

Alternativas suportadas pelo codigo:

- `DATABASE_URL`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`

Rollback simples:

1. Restaurar o valor antigo de `FOOTBALL_PG_DSN` ou `DATABASE_URL`.
2. Reiniciar o servico da API.
3. Manter o banco antigo intacto ate a validacao final do novo banco.

## Assets visuais

Nao armazenar imagem no banco.

Assets de clubes, competicoes, jogadores e tecnicos:

- artefato externo: `data/visual_assets`
- manifests esperados: `manifests/clubs.json`, `manifests/coaches.json`,
  `manifests/competitions.json`, `manifests/players.json`
- rota runtime: `/api/visual-assets/{category}/{assetId}`
- modo self-host no mesmo filesystem do Next:

```text
FOOTBALL_VISUAL_ASSETS_ROOT=/srv/football-analytics/visual_assets
```

O codigo tambem aceita `VISUAL_ASSETS_ROOT` como fallback. O path default local
continua sendo `../data/visual_assets`.

Modo Vercel + assets estaticos na Oracle/Nginx/CDN:

```text
FOOTBALL_VISUAL_ASSETS_MANIFEST_BASE_URL=https://assets.example.com/visual_assets/manifests/
FOOTBALL_VISUAL_ASSETS_PUBLIC_BASE_URL=https://assets.example.com/visual_assets/
```

Nesse modo, a rota Next le o manifest remoto, resolve o `assetId` e responde
com redirect para o arquivo estatico. Isso evita imagem no banco e evita
empacotar centenas de MB de imagens no deploy do frontend.

Imagens de campeao:

- ficam no bundle estatico do frontend em
  `frontend/public/images/competition-season/editions`
- sao referenciadas por `frontend/src/features/competitions/utils/champion-media.generated.ts`
- devem entrar no deploy do frontend como arquivos estaticos

Validacao minima de assets:

```powershell
node -e "const fs=require('fs'),p=require('path'); const root=process.env.FOOTBALL_VISUAL_ASSETS_ROOT || p.resolve('data/visual_assets'); for (const c of ['clubs','coaches','competitions','players']) { const m=JSON.parse(fs.readFileSync(p.join(root,'manifests',c+'.json'),'utf8')); const missing=m.entries.filter(e=>{ if (!e.local_path) return false; const rel=e.local_path.replace(/\\/g,'/').replace(/^data\/visual_assets\//,''); return !fs.existsSync(p.join(root,rel)); }); console.log(c, m.entries.length, 'missing=', missing.length); process.exitCode ||= missing.length ? 1 : 0; }"
```

Backfill de tecnicos via Wikidata/Wikimedia Commons:

```powershell
python scripts/ingest_wikidata_coach_assets.py
python scripts/ingest_wikidata_coach_assets.py --reconcile-manifest
python scripts/ingest_wikidata_coach_assets.py --export-missing-csv quality/coaches_missing_assets.csv
```

Sync especifico da vertical da Copa:

1. Atualizar os manifests oficiais de override e validar os arquivos locais:

```powershell
python tools/world_cup_assets_sync.py
```

2. Sincronizar o delta da Copa para o root de producao dos visual assets:

```powershell
python tools/world_cup_assets_sync.py --target-root /srv/football-analytics/visual_assets
```

3. No modo self-host do Next + API na mesma VM, apontar:

```text
FOOTBALL_VISUAL_ASSETS_ROOT=/srv/football-analytics/visual_assets
```

4. No modo Vercel + assets estaticos servidos por Nginx/CDN, publicar o mesmo
   `target_root` em `/visual_assets` e configurar:

```text
FOOTBALL_VISUAL_ASSETS_MANIFEST_BASE_URL=https://assets.example.com/visual_assets/manifests/
FOOTBALL_VISUAL_ASSETS_PUBLIC_BASE_URL=https://assets.example.com/visual_assets/
```

5. Validar o bundle sincronizado:

```powershell
python tools/world_cup_assets_sync.py --target-root /srv/football-analytics/visual_assets
curl http://127.0.0.1:3001/api/visual-assets/competitions/wc_mens
curl http://127.0.0.1:3001/api/visual-assets/clubs/world-cup-brazil
curl http://127.0.0.1:3001/api/visual-assets/players/7040061729933986054
```

O script materializa `competitions.overrides.json`, `clubs.overrides.json` e
atualiza `players.overrides.json` com os assets publicados da Copa, preservando
overrides manuais e aliases `USE_BASE` ja aprovados. O sync copia apenas os
manifests e arquivos referenciados por esses overrides, evitando reempacotar o
acervo inteiro.

Checagens HTTP:

```text
/api/visual-assets/competitions/648
/api/visual-assets/competitions/1122
/api/visual-assets/competitions/654
/images/competition-season/editions/brasileirao_a__2025.jpg
```

## Validacao ponta a ponta

Endpoints minimos:

- `/health`
- `/api/v1/home`
- `/api/v1/search`
- `/api/v1/competition-structure?competitionKey=libertadores&seasonLabel=2025`
- `/api/v1/group-standings` com `competitionKey`, `seasonLabel`, `stageId`
- `/api/v1/ties` com `competitionKey`, `seasonLabel`, `stageId`
- `/api/v1/competition-analytics?competitionKey=libertadores&seasonLabel=2025`
- `/api/v1/team-journey-history`
- `/api/v1/team-progression`
- `/api/v1/competition-historical-stats?competitionKey=libertadores&asOfYear=2025`
- `/api/v1/standings`
- `/api/v1/matches`
- `/api/v1/matches/{matchId}`
- `/api/v1/teams`
- `/api/v1/teams/{teamId}`
- `/api/v1/players`
- `/api/v1/players/{playerId}`
- `/api/v1/coaches`
- `/api/v1/market/transfers`
- `/api/v1/rankings/{rankingType}`

Paginas minimas:

- home
- hub de competicoes
- pagina de competicao/temporada de liga
- pagina de competicao/temporada de mata-mata/hibrida
- lista e detalhe de partidas
- lista e detalhe de times
- lista e detalhe de jogadores
- rankings
- busca

Criterio de aceite:

- dados retornando do banco candidato
- imagens de clubes e competicoes sem fallback indevido
- imagem de campeao carregando nas paginas de temporada
- nenhum endpoint minimo com erro 5xx
- rollback ainda disponivel pelo DSN antigo
