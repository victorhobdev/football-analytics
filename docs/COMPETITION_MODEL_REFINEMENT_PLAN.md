# Competition Model Refinement Plan

Data de referencia: `2026-03-25`  
Status: planejamento refinado, sem mudanca de codigo neste ciclo.

## 1. Objetivo

Refinar o dominio de competicoes para suportar, no mesmo modelo:

- ligas;
- copas hibridas (`fase classificatoria -> fase eliminatoria`);
- copas somente eliminatorias;
- mudancas de formato por temporada da mesma competicao;
- futura extensao para competicoes de clubes e de selecoes.

Restricao central:

- preservar o que ja esta verde;
- evitar big-bang rename;
- fazer a migracao por semantica e contrato, nao por refactor amplo.

---

## 2. Diagnostico atual com evidencia objetiva

## 2.1 O que ja existe e deve ser preservado

Base semantica util ja existe no repositorio:

- `raw.competition_seasons`, `raw.competition_stages` e `raw.competition_rounds` ja existem e fazem parte do escopo consolidado em `docs/GUIA_MESTRE_APLICACAO.md`.
- `competition_key`, `season_label` e `provider_season_id` ja entram no pipeline e ja sao validados em `infra/airflow/dags/data_quality_checks.py`.
- o frontend e parte do BFF ja navegam por contexto canonico `competitionId + competitionKey + seasonLabel` em:
  - `frontend/src/config/competitions.registry.ts`
  - `frontend/src/shared/utils/context-routing.ts`
  - `api/src/core/context_registry.py`

Leitura correta:

- o projeto nao esta preso so a ligas no nivel de navegacao;
- o problema principal esta na semantica de competicao por edicao/fase, nao na inexistencia total de estrutura.

## 2.2 Onde o modelo ainda esta preso a `league`

Ha forte legado semantico em `league_id` / `league_name`:

- `dbt/models/marts/core/dim_competition.sql`
- `dbt/models/marts/core/fact_standings_snapshots.sql`
- `dbt/models/marts/analytics/league_summary.sql`
- `dbt/models/marts/analytics/standings_evolution.sql`
- `dbt/models/marts/core/schema.yml`
- `dbt/models/marts/analytics/schema.yml`

Leitura correta:

- a camada mart ja tem `competition_sk`, mas ainda carrega nomenclatura e parte da logica de liga;
- isso nao bloqueia ligas, mas dificulta copas e mudancas de formato.

## 2.3 Onde a semantica atual quebra para copas

O ponto mais fragil hoje esta em standings:

- `api/src/routers/standings.py` resolve a fase por maior numero de times (`count(distinct ss.team_id) desc`);
- a mesma rota reconstrui tabela a partir de `raw.fixtures` para qualquer `stage`;
- o payload atual e uma tabela unica de linhas, sem suporte explicito a grupos multiplos;
- `api/tests/test_standings_routes.py` cobre Premier League e disponibilidade vazia, mas nao cobre:
  - copa eliminatoria pura;
  - fase de grupos multipla;
  - mesma competicao com formatos diferentes por temporada.

Leitura correta:

- liga regular funciona;
- copa eliminatoria pura pode ganhar uma "tabela" artificial;
- copa hibrida com grupos pode perder a semantica de grupos;
- a Champions em temporadas diferentes nao pode depender so de `competition_key`.

## 2.4 Separacao correta do problema

| Categoria | Estado atual | Evidencia | Leitura |
|---|---|---|---|
| Codigo | problema real | `standings.py`, marts com `league_*`, registry frontend com enum curto | a semantica esta parcialmente generalizada, mas incompleta |
| Dados | base boa, sem catalogo semantico suficiente | `competition_key`, `season_label`, `competition_stages`, `competition_rounds` ja existem | falta classificar formato por edicao e papel de cada fase |
| Validacao | boa para identidade de escopo; fraca para formato | `data_quality_checks.py` valida escopo semantico, nao valida familia de formato | faltam testes de comportamento por tipo de competicao |
| Ambiente | sem blocker real para este plano | este ciclo e documental | nao ha impeditivo tecnico para definir o desenho |

---

## 3. Escopo correto

O escopo nao e "aceitar copas".

O escopo correto e:

1. separar identidade da competicao de formato da edicao;
2. separar tipo de competicao de tipo de participante;
3. tornar fase/rodada entidades semanticas de primeiro nivel para BFF e frontend;
4. impedir que standings seja inferido por heuristica fraca.

Fora de escopo deste plano:

- implementar bracket completo agora;
- redesenhar todas as tabelas fisicas de uma vez;
- trocar toda ocorrencia de `league_*` no repositorio neste ciclo;
- implementar agora paginas especificas de selecoes.

---

## 4. Modelo alvo

## 4.1 Entidades canonicas

O modelo alvo deve ser:

`competicao -> edicao -> fase -> rodada -> partida`

### Competicao

Identidade estatica da competicao, independente da temporada.

Campos minimos recomendados:

- `competition_id`
- `competition_key`
- `display_name`
- `competition_category` = `league | cup`
- `scope` = `domestic | continental | global`
- `participant_scope` = `club | national_team`
- `season_calendar` = `annual | split_year`

### Edicao

Recorte da competicao em uma temporada especifica.  
Esta e a entidade que precisa carregar a semantica de formato.

Campos minimos recomendados:

- `competition_key`
- `season_label`
- `provider`
- `provider_season_id`
- `format_family` = `league | hybrid | knockout`
- `format_variant`
- `standings_mode`
- `default_hub_tab`
- `season_start_date`
- `season_end_date`

### Fase

Camada que explica o papel competitivo da etapa dentro da edicao.

Campos minimos recomendados:

- `stage_id`
- `competition_key`
- `season_label`
- `stage_order`
- `stage_type` = `league_phase | group_stage | knockout | final | qualification | playoff`
- `is_standings_eligible`
- `grouping_mode` = `single_table | grouped_tables | none`

### Rodada

Ordem navegavel dentro da fase.

Campos minimos recomendados:

- `round_id`
- `stage_id`
- `round_order`
- `round_name`
- `is_current`

## 4.2 Onde guardar a semantica

Para baixo risco:

- `raw.*` continua fiel ao provider;
- semantica de negocio entra em `control.*` e desce para `mart`/BFF;
- nao inferir formato apenas por nome da competicao nem por nome da fase.

Recomendacao pragmatica:

- manter `control.competitions` como catalogo estavel da competicao;
- estender `control.season_catalog` com metadados de edicao;
- criar uma tabela curada para semantica de fase, por exemplo `control.stage_semantics`.

---

## 5. Taxonomia recomendada

## 5.1 Nao sobrecarregar `type`

O enum atual do frontend:

- `domestic_league`
- `domestic_cup`
- `international_cup`

e util para agrupamento visual, mas e insuficiente como semantica de produto.

Ele deve ser quebrado em dimensoes ortogonais:

| Dimensao | Exemplos |
|---|---|
| `competition_category` | `league`, `cup` |
| `scope` | `domestic`, `continental`, `global` |
| `participant_scope` | `club`, `national_team` |
| `format_family` | `league`, `hybrid`, `knockout` |
| `format_variant` | `single_table`, `multi_group_then_knockout`, `league_phase_then_knockout`, `knockout_only` |

Isso evita explosao de enums e ja prepara:

- Champions antiga e nova;
- Libertadores;
- Copa do Brasil;
- Club World Cup;
- World Cup de selecoes.

## 5.2 Exemplos de classificacao

| Competicao / edicao | participant_scope | format_family | format_variant |
|---|---|---|---|
| Premier League 2024/2025 | `club` | `league` | `single_table` |
| Libertadores 2024 | `club` | `hybrid` | `multi_group_then_knockout` |
| Copa do Brasil 2024 | `club` | `knockout` | `knockout_only` |
| Champions 2023/2024 | `club` | `hybrid` | `multi_group_then_knockout` |
| Champions 2024/2025 | `club` | `hybrid` | `league_phase_then_knockout` |
| Club World Cup 2025 | `club` | definir por edicao | nao fixar no catalogo da competicao |
| World Cup 2026 | `national_team` | definir por edicao | nao fixar no catalogo da competicao |

---

## 6. Regras por familia de competicao

## 6.1 Liga

Regras:

- standings e valido em toda a edicao;
- tabela e unica;
- `default_hub_tab = standings`;
- fase pode existir, mas nao precisa governar a navegacao principal.

## 6.2 Copa hibrida

Regras:

- standings so existe em fases elegiveis;
- calendario existe para todas as fases;
- fase precisa virar seletor explicito no BFF/frontend;
- se a fase atual nao suporta standings, o sistema deve:
  1. usar a ultima fase elegivel para standings como referencia historica, ou
  2. retornar `not_applicable`;
- essa decisao deve ser explicita no contrato, nao heuristica.

Recomendacao:

- `GET /standings` deve carregar `mode = single_table | grouped_tables | not_applicable`;
- quando houver grupos, o payload nao pode ser uma lista unica achatada.

## 6.3 Copa somente eliminatoria

Regras:

- `standings_mode = not_applicable`;
- `default_hub_tab = calendar`;
- o hub da temporada deve privilegiar fase, rodada e chaveamento futuro;
- nao fabricar tabela de pontos a partir de jogos eliminatorios.

---

## 7. Topico obrigatorio: Champions com mudanca de formato por temporada

## 7.1 Problema

A Champions nao pode ser modelada como um objeto com formato fixo.

O projeto ja carrega temporadas historicas e a competicao mudou de formato recentemente.  
Logo, `competition_key = champions_league` nao basta para derivar:

- se a fase classificatoria e multipla por grupos;
- se existe tabela unica de fase classificatoria;
- qual payload de standings o frontend deve esperar.

## 7.2 Solucao recomendada

Manter a mesma competicao canonica e diferenciar a semantica por edicao.

Exemplo:

- `champions_league / 2020_21 .. 2023_24`
  - `format_family = hybrid`
  - `format_variant = multi_group_then_knockout`
  - `standings_mode = grouped_tables`
- `champions_league / 2024_25+`
  - `format_family = hybrid`
  - `format_variant = league_phase_then_knockout`
  - `standings_mode = single_table` na fase classificatoria

## 7.3 Implicacao pratica

O seletor de comportamento deve ser:

- `competition_key + season_label`

e nao:

- so `competition_key`;
- so `season_calendar`;
- so `stage_name`;
- maior numero de times da fase.

## 7.4 Recomendacao de contrato

Para a Champions e qualquer competicao que mude de formato:

- a edicao define o `format_variant`;
- a fase define `is_standings_eligible` e `grouping_mode`;
- o BFF responde conforme a edicao corrente;
- o frontend renderiza conforme `mode`, sem if hardcoded por competicao.

---

## 8. Preparacao para Club World Cup e World Cup de selecoes

## 8.1 Club World Cup

Nao deve entrar como excecao.  
Deve entrar como mais uma competicao com:

- `participant_scope = club`;
- formato definido por edicao;
- fases e standings governados pela mesma semantica de edicao.

## 8.2 World Cup de selecoes

Este caso exige uma separacao que hoje ainda nao esta explicita:

- `participant_scope = national_team`

Isso importa porque, no futuro, o produto nao pode assumir que toda entidade de time e clube.

Impactos futuros previsiveis:

- rotulos de UI (`club` vs `team`);
- paginas/perfis;
- assets;
- eventual camada de identidade de participantes.

Recomendacao:

- incluir `participant_scope` agora no catalogo canonico;
- nao misturar esse problema com o redesenho de perfis neste ciclo.

---

## 9. Plano incremental de execucao

## Bloco 1 - Catalogo semantico da competicao e da edicao

Objetivo:

- parar de depender de heuristica implita.

Entregaveis:

- revisar `control.competitions`;
- estender `control.season_catalog` com `format_family`, `format_variant`, `standings_mode`, `default_hub_tab`;
- preencher os `50` escopos atuais do portfolio.

Risco:

- baixo; sem mudanca de comportamento ainda.

## Bloco 2 - Semantica de fase

Objetivo:

- classificar cada `stage` de forma canonica.

Entregaveis:

- tabela curada `control.stage_semantics`;
- mapeamento por `provider + competition_key + season_label + stage_id`;
- campos `stage_type`, `stage_order`, `is_standings_eligible`, `grouping_mode`.

Risco:

- baixo a medio; depende de cobertura consistente de `stage_id`.

## Bloco 3 - BFF stage-aware

Objetivo:

- corrigir o contrato que mais sofre com formatos distintos.

Entregaveis:

- `GET /standings` passa a respeitar `edition + stage semantics`;
- suporte a `single_table`, `grouped_tables` e `not_applicable`;
- selecao de fase deixa de usar "maior numero de times";
- payload passa a informar modo, fase ativa e elegibilidade.

Risco:

- medio; precisa manter ligas verdes durante a migracao.

## Bloco 4 - Frontend sem enums sobrecarregados

Objetivo:

- impedir regra hardcoded por competicao.

Entregaveis:

- `frontend/src/config/competitions.registry.ts` evolui de um `type` unico para campos ortogonais;
- season hub passa a esconder/alternar `standings` quando nao aplicavel;
- competicoes hibridas passam a expor fase de maneira explicita.

Risco:

- medio; depende do novo contrato do BFF.

## Bloco 5 - Marts e nomenclatura de compatibilidade

Objetivo:

- aproximar mart do dominio canonico sem quebrar o que ja consome `league_*`.

Entregaveis:

- adicionar aliases/campos `competition_*` ao lado de `league_*`;
- criar caminho de migracao de `league_summary` para `competition_summary` antes de remover qualquer legado;
- evitar rename massivo enquanto houver consumidores ativos.

Risco:

- medio; deve ser feito depois do catalogo e do BFF.

---

## 10. Validacao recomendada

## 10.1 Matriz minima de regressao

Validar ao menos estes casos:

- Premier League 2024/2025 -> liga regular, tabela unica;
- Libertadores 2024 -> hibrida, grupos + mata-mata;
- Copa do Brasil 2024 -> mata-mata puro, sem standings;
- Champions 2023/2024 -> grupos + mata-mata;
- Champions 2024/2025 -> league phase + mata-mata.

## 10.2 O que precisa ficar verde

- resolucao canonica de competicao continua estavel;
- identidade semantica (`competition_key`, `season_label`, `provider_season_id`) continua valida;
- standings nao inventa tabela para copa eliminatoria;
- standings de formato com grupos nao perde a segmentacao;
- mudanca de formato da mesma competicao nao exige if hardcoded no frontend.

## 10.3 Comandos uteis de verificacao

PowerShell:

```powershell
docker compose exec -T postgres psql -U football -d football_dw -c "SELECT competition_key, season_label, provider, provider_season_id FROM control.season_catalog ORDER BY competition_key, season_label;"
```

```powershell
docker compose exec -T postgres psql -U football -d football_dw -c "SELECT league_id, season, stage_id, count(distinct team_id) AS teams FROM raw.standings_snapshots GROUP BY league_id, season, stage_id ORDER BY league_id, season, stage_id;"
```

```powershell
docker compose exec -T api pytest api/tests/test_standings_routes.py
```

---

## 11. Proximo passo seguro

O proximo passo mais seguro nao e mexer no frontend nem renomear mart.

O proximo passo seguro e:

1. consolidar um catalogo curado por edicao em `control.season_catalog`;
2. classificar as fases atuais em uma tabela curada de semantica;
3. rodar uma auditoria simples cobrindo os `50` escopos atuais antes de alterar o contrato de standings.

Leitura final:

- a base do projeto ja aceita "competicoes";
- o que falta e tornar esse suporte explicitamente orientado a edicao e a fase;
- sem isso, copas continuam entrando como excecao, e a Champions recente vai seguir quebrando a semantica historica.
