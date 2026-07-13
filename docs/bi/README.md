# Power BI — Football Analytics

O Power BI e a camada analitica publica do portfolio. O site preserva a exploracao de competicoes, partidas, times e jogadores; rankings, classificacao, comparacoes, tendencias e cobertura ficam no relatorio incorporado em `/analises`.

## Escopo

O modelo cobre todo o conjunto publicado em `mart.*`. Nenhuma consulta fixa uma competição ou temporada. O segmentador de escopo usa `provider + competition_key + season_label`.

`sportmonks | la_liga | 2024_25` é somente a fixture de reconciliação. No snapshot local de 2026-07-12 ela possui 380 partidas com placar, 20 times e 760 linhas em `FactTeamMatch`.

## Conteudo versionado

- [Contrato do modelo](MODELO_PUBLICO.md)
- [Dicionario de KPIs](DICIONARIO_KPIS.md)
- [Qualidade e limitacoes](QUALIDADE_E_LIMITACOES.md)
- [Atualizacao manual](REFRESH_MANUAL.md)
- [Validação SQL x DAX](VALIDACAO_SQL_DAX.md)
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
