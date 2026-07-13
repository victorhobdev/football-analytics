# Power BI — Football Analytics

Este diretório contém o relatório analítico público do portfólio. O modelo cobre todo o projeto; `sportmonks|la_liga|2024_25` é apenas o recorte fixo usado para reconciliar SQL e DAX.

## Abrir

- Desenvolvimento versionável: abra `FootballAnalytics_DesempenhoCompetitivo.pbip` no Power BI Desktop.
- Distribuição: abra `FootballAnalytics_DesempenhoCompetitivo.pbix` no Power BI Desktop.

O relatório foi aberto novamente no Power BI Desktop 2.155.756.0 e consultado com o cache salvo. O modelo carregado retornou 259.872 partidas, 519.734 linhas time-partida e 607.096 linhas jogador-partida.

## Conteúdo

- `FootballAnalytics_DesempenhoCompetitivo.Report`: cinco páginas e 55 visuais em PBIR.
- `FootballAnalytics_DesempenhoCompetitivo.SemanticModel`: modelo TMDL com oito tabelas, nove relacionamentos e 66 medidas.
- `screenshots`: evidências renderizadas das páginas Panorama, Times, Evolução e mando e Jogadores.
- `scripts/export_powerbi_snapshots.py`: exporta os marts para Parquet local.
- `data/manifest.json`: contagens, tamanhos e hashes do snapshot validado.
- `validation`: SQL de cobertura e reconciliação.

As páginas cobrem panorama, benchmark de times, forma recente e mando, eficiência de jogadores por 90 minutos e uma matriz explícita de cobertura. Conversão de finalizações só é exibida com pelo menos 95% de cobertura e 50 finalizações; métricas por 90 exigem 900 minutos.

## Atualizar

Execute o exportador na raiz do repositório. Ele lê a conexão do `.env` sem gravar credenciais e substitui os Parquets locais em `C:\Users\Public\football-analytics-bi-data`.

```powershell
python bi/scripts/export_powerbi_snapshots.py
```

Depois abra o PBIP e atualize as tabelas sequencialmente na ordem documentada em [`docs/bi/REFRESH_MANUAL.md`](../docs/bi/REFRESH_MANUAL.md). O refresh automático no serviço não faz parte deste MVP.

## Publicação

O relatório base foi publicado em `Meu workspace` e por **Publicar na Web**. A [URL pública](https://app.powerbi.com/view?r=eyJrIjoiZjI0MzhlOTMtMzE0Mi00NmY2LWJlNmMtMDRiZTc2YmNmZjBhIiwidCI6IjE0MDAyMTc4LWEwZDAtNGYxNC1iZGQ2LTJiMjNiYTJiNThkYyJ9) está integrada em `/analises`; a substituição pública deve ser validada novamente após cada evolução do PBIX. `NEXT_PUBLIC_POWER_BI_EMBED_URL` pode sobrescrever a URL por ambiente.
