# Guia Mestre da Aplicacao

Data de referencia: `2026-04-11`

Status:
- este e o ponto de partida oficial para os proximos ciclos do produto;
- ele substitui docs antigas de status, arquitetura ampla, inventario expandido e planos ja encerrados;
- contratos tecnicos detalhados continuam separados nos docs de contrato listados ao fim.

## 1. Objetivo deste guia

Consolidar o que importa daqui para frente:

- o que a aplicacao e;
- qual problema ela resolve;
- qual e o fluxo fim a fim, do dado ao frontend;
- qual dado existe de forma confiavel;
- quais superficies de produto ja existem no codigo;
- onde ainda ha gap real;
- qual e a ordem segura para terminar o app sem reabrir frentes desnecessarias.

## 2. Fonte de verdade usada aqui

Evidencia objetiva usada neste guia:

- stack e fluxo operacional em `README.md`;
- catalogo canonico de competicoes no frontend em `frontend/src/config/competitions.registry.ts`;
- catalogo canonico de competicoes no BFF em `api/src/core/context_registry.py`;
- rotas reais em `frontend/src/app/(platform)/**/page.tsx`;
- routers reais do BFF em `api/src/routers/`;
- estado da season surface em:
  - `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
  - `frontend/src/features/competitions/utils/competition-season-surface.ts`
- contratos tecnicos em:
  - `docs/contracts/data_contracts.md`
  - `docs/BFF_API_CONTRACT.md`
  - `docs/MART_FRONTEND_BFF_CONTRACTS.md`
- cobertura da Copa do Mundo em `docs/WORLD_CUP_DATA_READY_BY_EDITION.md`.

Incerteza explicita:

- nesta rodada nao houve validacao SQL live do banco, porque a stack Docker nao estava ativa localmente;
- por isso, os numeros de cobertura abaixo consolidam o ultimo snapshot auditado persistido no repo e o estado atual do codigo;
- onde houver diferenca entre catalogo exposto e cobertura auditada, isso fica marcado.

## 3. O que a aplicacao e

`football-analytics` e uma aplicacao de exploracao de futebol orientada por arquivo historico, nao por temporada ao vivo.

Objetivo de produto:

- navegar por competicoes, temporadas, fases e partidas;
- abrir contexto canonico de clubes, jogadores, tecnicos e comparativos;
- cruzar dado bruto, marts e BFF em uma experiencia de produto consistente;
- expor um acervo multi-competicao e multi-temporada com coverage-state honesto.

Regra de produto que deve guiar design e copy:

- o app fala de edicoes fechadas e acervo;
- nao prometer experiencia live se o contrato nao sustenta;
- nao exibir linguagem interna de arquitetura na UI;
- nao inventar fatos editoriais sem fonte confiavel.

## 4. Fluxo fim a fim

Fluxo oficial:

`ingestao -> bronze -> silver -> raw -> dbt/mart -> BFF -> frontend -> BI`

Camadas:

| Camada | Papel |
| --- | --- |
| Bronze | payload bruto por provider/endpoints |
| Silver | normalizacao intermediaria |
| Raw | base factual canonica para reconciliacao e auditoria |
| Mart | camada de consumo orientada a produto e BI |
| BFF | contrato anti-corruption para o frontend |
| Frontend | navegacao canonica, coverage-state e experiencia de produto |
| BI | consumo analitico em Metabase |

Stack atual do repo:

- Airflow em `infra/airflow/dags/`
- MinIO para bronze/silver
- Postgres para `raw`, `mart` e tabelas de controle
- dbt em `dbt/`
- quality gates em `quality/` e DAGs de validacao
- BFF em `api/`
- frontend em `frontend/`
- dashboards versionados em `bi/metabase/`

## 5. Escopo de dados

### 5.1 Portfolio auditado com cobertura forte

Ultimo snapshot auditado consolidado no repo para o nucleo principal do portfolio:

- `10` competicoes
- `50` escopos competicao-temporada
- `15265` fixtures
- `15262` fixtures finalizados
- `267590` eventos de partida no `mart.fact_match_events`
- `651169` rows em `mart.fact_fixture_player_stats`
- `649695` rows em `mart.fact_fixture_lineups`
- `53221` rows em `mart.player_season_summary`

Competicoes auditadas como baseline forte:

- Campeonato Brasileiro Serie A
- Campeonato Brasileiro Serie B
- Copa Libertadores da America
- Copa do Brasil
- Premier League
- UEFA Champions League
- La Liga
- Serie A (Italia)
- Bundesliga
- Ligue 1

Leitura correta:

- esse e o nucleo factual forte ja comprovado;
- ele sustenta o eixo principal do produto;
- o frontend deve assumir esse nucleo como baseline seguro.

### 5.2 Catalogo canonico exposto hoje pelo app/BFF

O codigo atual do frontend e do BFF expoe `14` competicoes canonicas:

- Brasileirao Serie A
- Brasileirao Serie B
- Libertadores
- Sudamericana
- Copa do Brasil
- Supercopa do Brasil
- FIFA Intercontinental Cup
- Premier League
- Champions League
- La Liga
- Serie A Italy
- Bundesliga
- Ligue 1
- Liga Portugal

Separacao correta entre catalogo e coverage:

| Grupo | Estado |
| --- | --- |
| Nucleo auditado de `10` competicoes | confirmado por snapshot forte no repo |
| `sudamericana` | catalogo e codigo presentes; precisa reconfirmacao live de cobertura consolidada |
| `supercopa_do_brasil` | catalogo presente; sem confirmacao live nesta rodada |
| `fifa_intercontinental_cup` | catalogo presente; ha sinais de suporte no repo, mas sem auditoria consolidada nesta rodada |
| `primeira_liga` | catalogo presente; ha evidencia de onboarding parcial/historico, mas sem snapshot live consolidado nesta rodada |

Conclusao:

- o app ja nasceu multi-competicao no nivel de navegacao;
- o baseline de dado comprovado ainda e mais forte no nucleo de 10 competicoes;
- expansoes mais novas devem ser tratadas como `supported in catalog, validate in runtime`.

### 5.3 Cobertura por dominio

Resumo consolidado do que o warehouse sustenta hoje no nucleo principal:

| Dominio | Estado pratico |
| --- | --- |
| competition structure | disponivel |
| standings | disponivel |
| fixtures | disponivel |
| match statistics | disponivel com gaps residuais de provider |
| head-to-head | disponivel |
| lineups | disponivel com gaps residuais de provider |
| match events | disponivel com gaps residuais de provider |
| fixture player statistics | disponivel com gaps residuais de provider |
| player season statistics | disponivel |
| team coaches | disponivel |
| player transfers | disponivel, mas consumo de produto ainda heterogeneo |
| team sidelined | disponivel no dado, ainda pouco exposto no produto |

O que isso significa para produto:

- competicao/temporada, standings, calendario, match center, times e jogadores ja tem base real;
- modulos secundarios dependem mais de acabamento de contrato/UX do que de ausencia total de dado;
- coverage gap residual e majoritariamente de provider, nao de quebra estrutural do pipeline.

### 5.4 Trilha Copa do Mundo

A Copa do Mundo hoje e uma trilha paralela ao portfolio de clubes.

Cobertura consolidada:

- `22` edicoes de `1930` a `2022` com fixtures/resultados basicos;
- standings, tecnicos, squads e gols disponiveis ao longo das edicoes;
- lineups, bookings e substitutions com cobertura parcial em varias edicoes historicas;
- eventos ricos completos apenas em `2018` e `2022`;
- algumas edicoes historicas tem amostras StatsBomb, mas nao torneio inteiro.

Leitura correta para produto:

- a Copa pode virar um produto proprio de arquivo historico;
- match view rica de torneio completo so e segura em `2018` e `2022`;
- para edicoes mais antigas, o produto precisa assumir leitura historica enxuta, nao event stream completo.

## 6. Contratos e camadas de consumo

Ordem correta de consumo:

1. `mart` quando o dado ja estiver materializado de forma estavel;
2. `raw` apenas como apoio pontual quando o mart ainda nao fechou um caso;
3. BFF como contrato obrigatorio entre warehouse e frontend;
4. frontend sem consultar semantica interna do warehouse diretamente.

Docs oficiais de contrato:

- `docs/contracts/data_contracts.md`: grain, chaves, colunas obrigatorias e contratos por camada;
- `docs/BFF_API_CONTRACT.md`: contrato publico dos endpoints do frontend;
- `docs/MART_FRONTEND_BFF_CONTRACTS.md`: mapeamento entre mart, BFF e necessidades de consumo.

## 7. Estado atual do aplicativo

### 7.1 Superficies principais ja existentes no frontend

Rotas reais identificadas no codigo:

- `/`
- `/competitions`
- `/competitions/[competitionKey]`
- `/competitions/[competitionKey]/seasons/[seasonLabel]`
- `/matches`
- `/matches/[matchId]`
- `/teams`
- `/teams/[teamId]`
- `/players`
- `/players/[playerId]`
- `/competitions/[competitionKey]/seasons/[seasonLabel]/teams/[teamId]`
- `/competitions/[competitionKey]/seasons/[seasonLabel]/players/[playerId]`
- `/rankings/[rankingType]`
- `/head-to-head`
- `/coaches`
- `/coaches/[coachId]`
- `/market`
- `/audit`
- rotas legadas de compatibilidade: `/clubs`, `/clubs/[clubId]`, `/competition/[competitionId]`
- trilha separada: `/competitions/world-cup-2022/**`

### 7.2 Leitura pratica por modulo

| Modulo | Estado observado no codigo |
| --- | --- |
| Home executiva | vivo |
| Catalogo de competicoes | vivo |
| Competition hub | vivo |
| Competition season surface | viva e ja orientada por `league/cup/hybrid`, mas ainda em acabamento de produto/design |
| Matches + match center | vivos |
| Teams + team profile | vivos |
| Players + player profile | vivos |
| Rankings | vivo |
| Busca global | viva |
| Head-to-head | vivo |
| Coaches | vivo |
| Market | API e feature existem, mas a rota publica ainda esta em placeholder |
| Audit | placeholder explicito |
| World Cup 2022 | microsuperficie separada do fluxo canonico principal |

Leitura correta:

- o nucleo principal do app ja existe;
- o que falta nao e "comecar do zero";
- o que falta e convergir superficies, copy, design e fechamento dos modulos secundarios.

### 7.3 Ponto estrutural mais importante no frontend

A tela mais estrategica para fechar agora e:

- `/competitions/[competitionKey]/seasons/[seasonLabel]`

Motivo:

- ela concentra o contexto canonico do produto;
- ela organiza liga, copa e hibrida;
- ela define a hierarquia que depois se propaga para match, team, player e rankings.

Estado atual dessa surface:

- a resolucao por tipo da edicao ja existe em `competition-season-surface.ts`;
- a page usa estrutura real de `competition-structure`, `standings`, `group-standings`, `ties`, `matches` e `rankings`;
- o problema principal remanescente e de hierarquia visual, composicao e acabamento, nao de ausencia de base tecnica.

## 8. Direcao de produto daqui para frente

Regras que devem guiar qualquer proximo ciclo:

- pensar a aplicacao como acervo historico, nao como app live;
- manter rotas canonicas por competicao e temporada;
- preservar filtros globais e contexto travado na rota;
- usar coverage-state como dado de produto, nao como nota tecnica;
- remover copy interna de arquitetura da UI;
- nao abrir backend/BFF novo sem gap real comprovado;
- manter mudancas pequenas e com baixo risco de regressao.

## 9. O que falta para terminar a aplicacao

### 9.1 Fechamento de produto e front

Prioridade alta:

1. fechar a family de `competition season surface` com linguagem final por tipo:
   - `league`
   - `cup`
   - `hybrid`
2. limpar copy tecnica residual e reduzir texto interno na UI;
3. alinhar home, season surface, match center, team profile e player profile na mesma hierarquia de produto;
4. decidir a entrada oficial dos modulos secundarios na shell.

### 9.2 Fechamento funcional dos secundarios

Gaps reais hoje:

- `market`: ja tem dominio e endpoint, mas a rota publica ainda nao entrega a feature;
- `availability/sidelined`: existe no dado, mas ainda nao virou superficie forte;
- `audit`: segue fora da experiencia publica;
- `world cup`: precisa decisao se fica como trilha separada ou se entra no catalogo principal de competicoes.

### 9.3 Cobertura e catalogo

Antes de tratar o app como 100% fechado:

- reconfirmar em runtime as competicoes novas do catalogo (`sudamericana`, `supercopa_do_brasil`, `fifa_intercontinental_cup`, `primeira_liga`);
- validar se o home/BFF esta refletindo a expansao real do warehouse, nao apenas o registry do frontend;
- manter a diferenca entre `catalog available` e `coverage audited` explicita.

## 10. Ordem segura de execucao

Sequencia recomendada:

1. manter este guia como referencia central e parar de abrir ciclos a partir de docs antigas de plano/status;
2. fechar a season surface como eixo principal de design e navegacao;
3. religar `market` ao dominio real ja existente, se o contrato responder bem;
4. decidir se `availability` entra primeiro como secao de squad ou como rota propria;
5. revisar home e shell para copy final de produto;
6. validar catalogo expandido em runtime;
7. so depois disso tratar polish final e release/demo.

## 11. Validacao minima antes de declarar pronto

Backend/dados:

```powershell
python tools/backend_data_readiness_gate.py
python tools/backend_data_readiness_gate.py --mode full
```

Frontend:

```powershell
python tools/frontend_release_gate.py
python tools/frontend_release_gate.py --mode full
```

Stack local:

```powershell
docker compose up -d
docker compose ps
powershell -ExecutionPolicy Bypass -File .\tools\start-local.ps1
```

## 12. Docs que continuam vivos

Manter como referencia oficial:

- `docs/GUIA_MESTRE_APLICACAO.md`
- `docs/contracts/data_contracts.md`
- `docs/BFF_API_CONTRACT.md`
- `docs/MART_FRONTEND_BFF_CONTRACTS.md`
- `docs/COMPETITION_MODEL_REFINEMENT_PLAN.md`
- `docs/COMPETITION_SEASON_SURFACE_REDESIGN_PLAN.md`
- `docs/COMPETITION_SEASON_SURFACE_MOCKUP_ADAPTATION_PLAN.md`
- `docs/WORLD_CUP_DATA_READY_BY_EDITION.md`
- `docs/CHAMPION_VISUAL_ASSETS.md`
- `docs/VISUAL_ASSETS_INGESTION.md`
- `docs/FRONTEND_RELEASE_READINESS.md`
- `docs/BACKEND_DATA_RELEASE_READINESS.md`
- `docs/DEEP_REVIEW_20260410.md`
- `docs/metrics/metrics_dictionary.md`

## 13. Proximo passo seguro

Retomar a implementacao pelo eixo:

- `competition season surface`

Sem reabrir ingestao, sem refatorar arquitetura ampla e sem inventar novo backlog de backend antes de provar gap real na tela.
