# Football Analytics

Portfólio de análise de dados aplicado a futebol: ingestão e transformação de dados públicos, modelo dimensional, reconciliação SQL × DAX, Power BI versionável e uma aplicação web para exploração do domínio.

[Acessar a plataforma](https://football-analytics-victor-hugos-projects-f5572824.vercel.app) · [Abrir o case na aplicação](https://football-analytics-victor-hugos-projects-f5572824.vercel.app/landing)

![Football Analytics - página inicial](frontend/public/readme/home.jpg)

## Pergunta do projeto

Como transformar fontes heterogêneas de resultados e estatísticas de futebol em análises comparáveis sem ocultar ausência de dados, misturar provedores ou apresentar agregações como classificações oficiais?

## Entrega analítica

- Modelo estrela com fatos de partidas, times por partida e jogadores por partida.
- Dimensões conformadas de data, escopo, time e jogador.
- Snapshots Parquet gerados apenas a partir da camada `mart.*` curada.
- Consultas SQL independentes para cobertura e reconciliação.
- Modelo TMDL com 73 medidas DAX e limites explícitos de amostra.
- Relatório PBIR com seis páginas públicas, duas páginas ocultas de drill-through e layout móvel.
- Estudo estatístico reproduzível em Python e caso de performance com SQL avançado.
- Power BI público integrado em `/analises`.
- Catálogos, partidas, classificações oficiais e perfis preservados na aplicação Next.js.

## Snapshot validado

| Evidência | Valor |
| --- | ---: |
| Partidas | 259.872 |
| Linhas time–partida | 519.734 |
| Linhas jogador–partida | 607.096 |
| Escopos fonte–competição–temporada | 1.004 |
| Cobertura de placar | 99,998% |
| Cobertura de estatísticas de times | 5,43% |
| Cobertura de notas de jogadores | 67,63% |
| Cobertura de minutos | 71,62% |

Os percentuais são evidências do snapshot de 2026-07-12, não promessas para atualizações futuras.

## Power BI

As seis páginas visíveis cobrem:

1. Resumo executivo orientado a decisão.
2. Panorama do acervo.
3. Benchmark e eficiência de times.
4. Forma recente e mando observado.
5. Produção e eficiência de jogadores.
6. Cobertura e confiabilidade.

Times e jogadores possuem páginas de drill-through. Conversão de finalizações só aparece com pelo menos 95% de cobertura e 50 finalizações; métricas por 90 exigem 900 minutos.

Abra o projeto versionável em [`bi/FootballAnalytics_DesempenhoCompetitivo.pbip`](bi/FootballAnalytics_DesempenhoCompetitivo.pbip) ou consulte a [documentação do BI](docs/bi/README.md).

## Exemplo reconciliado — La Liga 2024/25

- Barcelona: 88 pontos em 38 jogos, 2,3158 PPG.
- Real Madrid: 84 pontos em 38 jogos, 2,2105 PPG.
- Barcelona: 102 gols em 677 finalizações, conversão de 15,07% no recorte coberto.
- Alexander Sørloth: 20 gols em 1.559 minutos, 1,1546 gol por 90.

As consultas que sustentam esses valores estão em [`bi/validation`](bi/validation).

## Cases de Python e SQL

- [A vantagem de jogar em casa diminuiu?](docs/analysis/HOME_ADVANTAGE.md): pandas, exploração, intervalos de confiança, Welch, Hedges g e controle por competição sobre 207.770 partidas.
- [Forma recente e posição relativa em SQL](docs/analysis/TEAM_FORM_SQL.md): `LAG`, `LEAD`, janelas, percentis, `RANK`, `EXPLAIN ANALYZE` e benchmark antes/depois.
- [Performance e arquitetura do Power BI](docs/bi/PERFORMANCE_E_ARQUITETURA.md): evidências do Performance Analyzer e DAX Studio, acessibilidade e decisão entre Import, DirectQuery e Direct Lake.

## Limitações declaradas

- Não há xG; conversão de finalizações não representa qualidade da chance.
- A classificação DAX não implementa desempates oficiais, deduções ou regulamentos eliminatórios.
- Notas de provedores diferentes não são tratadas como uma escala única.
- Publicar na Web não aceita pré-filtros por URL. A aplicação preserva o contexto solicitado e orienta a seleção manual no relatório público.
- O refresh do Power BI é manual nesta fase.

## Arquitetura

```text
Fontes públicas
      ↓
PostgreSQL → dbt / camada mart → validações SQL
      ↓
Snapshots Parquet → Power Query → modelo TMDL / DAX → Power BI
      ↓
FastAPI / BFF → Next.js para catálogo, partidas e perfis
```

## Stack

Next.js 15 · React 19 · TypeScript · FastAPI · PostgreSQL · Airflow · dbt · Power BI · Power Query · DAX · PBIP/PBIR

## Executar localmente

Para validar a configuração sem expor credenciais:

```powershell
Copy-Item .env.example .env
docker compose --env-file .env.example config --quiet
```

Para subir o ambiente local completo no Windows:

```powershell
.\start-local.ps1
```

Aplicação: `http://localhost:3001`

Power BI integrado: `http://localhost:3001/analises`

O `start-local.ps1` exige o `.env` local e snapshots de serving/deltas em `artifacts/`. Esses artefatos não são versionados; portanto, esse caminho ainda não é um clone limpo completo.

## Validação rápida

```powershell
pnpm --dir frontend exec tsc --noEmit
python bi/scripts/build_pbir_report.py
python -m zipfile -t bi/FootballAnalytics_DesempenhoCompetitivo.pbix
```

O mesmo conjunto de verificações é executado pelo [CI](.github/workflows/ci.yml).

Para atualizar dados e republicar, siga [`docs/bi/REFRESH_MANUAL.md`](docs/bi/REFRESH_MANUAL.md).

Para hospedar a aplicação em uma VM OCI Always Free, siga [`deploy/oci/README.md`](deploy/oci/README.md).
