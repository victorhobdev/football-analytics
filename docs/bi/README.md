# Power BI — Football Analytics

O Power BI é a camada analítica pública do projeto. O site preserva a exploração de competições, partidas, classificações oficiais, times e jogadores; rankings analíticos, comparações, tendências e cobertura ficam no relatório incorporado em `/analises`.

## Escopo

O modelo cobre todo o conjunto publicado em `mart.*`. Nenhuma consulta fixa uma competição ou temporada. O segmentador de escopo usa `provider + competition_key + season_label`.

`sportmonks | la_liga | 2024_25` é somente a fixture de reconciliação. No snapshot local de 2026-07-12 ela possui 380 partidas com placar, 20 times e 760 linhas em `FactTeamMatch`.

## Conteudo versionado

- [Contrato do modelo](MODELO_PUBLICO.md)
- [Dicionario de KPIs](DICIONARIO_KPIS.md)
- [Qualidade e limitacoes](QUALIDADE_E_LIMITACOES.md)
- [Atualizacao manual](REFRESH_MANUAL.md)
- [Validação SQL x DAX](VALIDACAO_SQL_DAX.md)
- [Performance, acessibilidade e arquitetura](PERFORMANCE_E_ARQUITETURA.md)
- [Dicionário das medidas](DICIONARIO_MEDIDAS.md)
- [Estudo estatístico sobre mando](../../analysis/home_advantage.py)
- [Caso SQL avançado e performance](../../analysis/sql/team_form_performance.sql)
- `../../bi/validation`: consultas executaveis de cobertura e reconciliacao.
- `../../bi/README.md`: abertura, estrutura e estado de publicação dos artefatos.

## Executar as validacoes

Com o PostgreSQL local em execucao:

```powershell
Get-Content -Raw bi/validation/selecionar_recorte.sql |
  docker exec -i football_postgres psql -U football -d football_dw -v ON_ERROR_STOP=1 -f -

Get-Content -Raw bi/validation/reconciliation_laliga_2024_25.sql |
  docker exec -i football_postgres psql -U football -d football_dw -v ON_ERROR_STOP=1 -f -
```

Não publique credenciais, conexões locais, nem dados que não estejam no schema `mart` curado. O [iframe público](https://app.powerbi.com/view?r=eyJrIjoiZjI0MzhlOTMtMzE0Mi00NmY2LWJlNmMtMDRiZTc2YmNmZjBhIiwidCI6IjE0MDAyMTc4LWEwZDAtNGYxNC1iZGQ2LTJiMjNiYTJiNThkYyJ9) foi publicado e validado anonimamente em 2026-07-12.

`Publicar na Web` não aceita filtros por URL. A aplicação mantém competição e temporada visíveis como contexto solicitado, mas a seleção precisa ser repetida nos segmentadores do relatório. Pré-filtro automático exige incorporação segura ou Power BI Embedded.
