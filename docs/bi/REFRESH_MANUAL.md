# Atualização manual e publicação pública

1. Atualize o pipeline e os marts no PostgreSQL local.
2. Na raiz do repositório, execute `python bi/scripts/export_powerbi_snapshots.py`. O script lê o `.env`, consulta os marts e grava os Parquets no diretório técnico padrão `C:\Users\Public\football-analytics-bi-data`; credenciais não são incluídas nos arquivos. Para outro local, use `python bi/scripts/export_powerbi_snapshots.py --output-dir .\bi\data\snapshots` ou defina `BI_SNAPSHOT_DIR`.
3. No Power BI Desktop, ajuste o parâmetro M `SnapshotRoot` para o mesmo diretório dos Parquets. O valor versionado usa o diretório técnico padrão; ao usar um caminho alternativo, o parâmetro e o exportador precisam apontar para a mesma pasta.
4. Compare `bi/data/manifest.json` com a execução e rode `bi/validation/selecionar_recorte.sql` para verificar cobertura.
5. Rode `fact_team_match_validation.sql`, `reconciliation_team_metrics.sql` e `reconciliation_player_metrics.sql` com os mesmos filtros do relatório.
6. Abra `bi/FootballAnalytics_DesempenhoCompetitivo.pbip` no Power BI Desktop.
7. Atualize sequencialmente: `DimScope`, `DimDate`, `DimTeam`, `DimPlayer`, `FactMatch`, `FactTeamMatch` e `FactPlayerMatch`. Salve após concluir. O refresh simultâneo produziu dependência cíclica no ambiente validado; a sequência individual foi concluída com sucesso.
8. Valide `sportmonks|la_liga|2024_25` com `reconciliation_laliga_2024_25.sql` e compare SQL com os cards e matrizes DAX. No Desktop, confira o bookmark `Exemplo - La Liga 2024-25`, os layouts de telefone das seis páginas públicas, tooltips, ordem de tabulação, textos alternativos e o drill-through por `Time` e `Jogador` nas duas páginas de detalhe.
9. Considere as cinco imagens em `bi/screenshots` como evidência parcial: elas cobrem `Panorama`, `Times`, `Evolução e mando`, `Jogadores` e `Cobertura`; a página `Resumo executivo` não tem screenshot versionado.
10. Repita as medições do Performance Analyzer e do DAX Studio conforme [`PERFORMANCE_E_ARQUITETURA.md`](PERFORMANCE_E_ARQUITETURA.md). Só aplique otimização quando houver regressão medida.
11. Salve o PBIP e exporte `bi/FootballAnalytics_DesempenhoCompetitivo.pbix`; use esse PBIX para upload/substituição no Power BI Service. O upload inicial foi concluído em `Meu workspace` em 2026-07-12.
12. Autentique a conta proprietária no navegador, gere ou atualize **Publicar na Web**, abra a URL em janela anônima e confira o embed em `/analises`.
13. Registre a data, URL pública e reconciliação nesta documentação.

O refresh é manual neste MVP. Não configure gateway, DirectQuery, RLS ou credenciais do PostgreSQL no Power BI Service. **Estado atual:** PBIP e PBIX estão válidos; upload, iframe, integração no frontend e validação anônima foram concluídos.
