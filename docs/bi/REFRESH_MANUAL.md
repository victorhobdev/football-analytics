# Atualização manual e publicação pública

1. Atualize o pipeline e os marts no PostgreSQL local.
2. Na raiz do repositório, execute `python bi/scripts/export_powerbi_snapshots.py`. O script lê o `.env`, consulta os marts e grava os Parquets em `C:\Users\Public\football-analytics-bi-data`; credenciais não são incluídas nos arquivos.
3. Compare `bi/data/manifest.json` com a execução e rode `bi/validation/selecionar_recorte.sql` para verificar cobertura.
4. Rode `fact_team_match_validation.sql`, `reconciliation_team_metrics.sql` e `reconciliation_player_metrics.sql` com os mesmos filtros do relatório.
5. Abra `bi/FootballAnalytics_DesempenhoCompetitivo.pbip` no Power BI Desktop.
6. Atualize sequencialmente: `DimScope`, `DimDate`, `DimTeam`, `DimPlayer`, `FactMatch`, `FactTeamMatch` e `FactPlayerMatch`. Salve após concluir. O refresh simultâneo produziu dependência cíclica no ambiente validado; a sequência individual foi concluída com sucesso.
7. Valide `sportmonks|la_liga|2024_25` com `reconciliation_laliga_2024_25.sql` e compare SQL com os cards e matrizes DAX.
8. Use `bi/FootballAnalytics_DesempenhoCompetitivo.pbix` para upload/substituição no Power BI Service. O upload inicial foi concluído em `Meu workspace` em 2026-07-12.
9. Autentique a conta proprietária no navegador, gere ou atualize **Publicar na Web**, abra a URL em janela anônima e confira o embed em `/analises`.
10. Registre a data, URL pública e reconciliação nesta documentação.

O refresh é manual neste MVP. Não configure gateway, DirectQuery, RLS ou credenciais do PostgreSQL no Power BI Service. **Estado atual:** PBIP e PBIX estão válidos; upload, iframe, integração no frontend e validação anônima foram concluídos.
