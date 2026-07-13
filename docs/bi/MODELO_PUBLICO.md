# Contrato do modelo publico

## Grao e fontes

| Tabela Power BI | Origem | Grao | Regra |
| --- | --- | --- | --- |
| `FactMatch` | `mart.fact_matches` | uma partida | Mantem todas as partidas para cobertura; `ScoreValid` e verdadeiro somente com os dois placares preenchidos. |
| `FactTeamMatch` | derivada de `FactMatch` | uma partida por time | Duas linhas por partida com placar valido: uma `home`, uma `away`. |
| `FactPlayerMatch` | `mart.fact_fixture_player_stats` + `FactMatch` | partida, jogador e time | Inclui somente partidas com placar valido; nao preenche metricas nulas. |
| `DimScope` | escopos distintos das fatos | provider, competição e temporada | Filtro compartilhado por `scope_key`. |
| `DimDate` | `mart.dim_date` | data | Relacao ativa com `FactMatch[match_date]`, `FactTeamMatch[match_date]` e `FactPlayerMatch[match_date]`. |
| `DimTeam` | `mart.dim_team` | identidade canônica de time | Relaciona por `team_sk`. |
| `DimPlayer` | `mart.dim_player` | identidade canônica de jogador | Relaciona por `player_sk`. |

Use `provider`, `competition_key` e `season_label` via `DimScope`. A chave textual `scope_key = provider|competition_key|season_label` é a dimensão lógica de escopo. Não use apenas `competition_sk` ou `league_id` como filtro de escopo.

## Transformacao minima de `FactTeamMatch`

O Power Query deve reproduzir [`fact_team_match_validation.sql`](../../bi/validation/fact_team_match_validation.sql):

1. Comecar em `mart.fact_matches`.
2. Filtrar `home_goals`, `away_goals`, `home_team_id` e `away_team_id` nulos.
3. Criar as duas linhas casa/fora com `goals_for`, `goals_against` e `venue`.
4. Calcular `wins`, `draws`, `losses` e `points` nessa fato.

`mart.int_team_match_rows` nao e uma fonte do modelo: ele trata placares nulos como zero, o que produziria partidas e pontos inexistentes.

## Relacoes e filtros

- `DimDate` 1:* para cada fato por data; mantenha direcao unica da dimensao para a fato.
- `DimTeam` 1:* para `FactTeamMatch[team_sk]` e `FactPlayerMatch[team_sk]`.
- `DimPlayer` 1:* para `FactPlayerMatch[player_sk]`.
- `DimScope` 1:* para as três fatos por `scope_key`.

Nao conecte fatos diretamente entre si e nao habilite filtro bidirecional apenas para fazer um visual funcionar.

## Publicacao

O relatório usa modo Import sobre snapshots Parquet derivados somente de tabelas `mart.*` curadas. Não há RLS, DirectQuery, gateway, segredos ou refresh automático nesta fase. O PBIX foi publicado em `Meu workspace` e o iframe público está integrado em `/analises`.
