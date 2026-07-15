# Performance, acessibilidade e arquitetura do Power BI

Evidências capturadas em 2026-07-12 no Power BI Desktop 2.155.756.0, com o filtro `sportmonks | la_liga | 2024_25` na página **1. Resumo executivo**.

## Baseline medido

| Ferramenta | Escopo | Resultado |
| --- | --- | ---: |
| Performance Analyzer | 15 visuais da página | 64–257 ms por visual |
| Performance Analyzer | visual mais lento | 257 ms |
| DAX Studio 3.5.2 | consulta com 7 medidas e 20 times | 27 ms |
| DAX Studio | Formula Engine | 19 ms (70,4%) |
| DAX Studio | Storage Engine | 8 ms (29,6%) |
| DAX Studio | consultas SE / cache | 5 / 1 acerto |
| DAX Studio | pico aproximado de memória | 5.084 KB |

Nenhum visual ultrapassou 300 ms e a consulta analítica terminou em 27 ms. Por isso, não foi aplicada uma reescrita DAX especulativa: o baseline não mostrou gargalo. Os arquivos brutos permitem repetir e auditar a conclusão:

- [`PERFORMANCE_ANALYZER.json`](PERFORMANCE_ANALYZER.json)
- [`DAX_SERVER_TIMINGS.json`](DAX_SERVER_TIMINGS.json)
- [`DICIONARIO_MEDIDAS.md`](DICIONARIO_MEDIDAS.md)

O caso SQL separado apresentou uma melhoria mensurável de 5.453,303 ms para 3.199,425 ms (-41,33%) após materialização temporária e índice. Veja [`TEAM_FORM_SQL.md`](../analysis/TEAM_FORM_SQL.md).

## Recursos profissionais implementados

- página **Resumo executivo** com acontecimento, localização, relevância, ação possível e confiança;
- bookmark `Exemplo - La Liga 2024-25` para uma narrativa reproduzível;
- tooltips analíticos nos gráficos principais;
- texto alternativo e ordem de tabulação em todos os 94 visuais;
- layouts móveis próprios nas seis páginas públicas;
- drill-through de time e jogador em duas páginas ocultas;
- dicionário versionado das 73 medidas;
- regras de suficiência: time de referência exige 10 jogos; conversão exige 95% de cobertura; métricas por 90 exigem 900 minutos.

As cores de texto verificadas contra fundo branco atendem WCAG AA para texto normal: `#003526` 13,66:1, `#00513b` 9,37:1, `#57657a` 5,92:1 e `#17382d` 12,80:1. A inspeção final deve incluir navegação real por teclado, pois ordem de tabulação configurada não garante sozinha a experiência de cada leitor de tela.

## Import, DirectQuery e Direct Lake

O relatório usa **Import** a partir de snapshots Parquet locais. Essa opção foi mantida porque torna a demonstração portátil, rápida, reproduzível e independente da disponibilidade do PostgreSQL durante o acesso público. O custo é um refresh manual e dados não instantâneos.

**DirectQuery** seria indicado se a atualização próxima do tempo real justificasse gateway, disponibilidade do banco, controle de concorrência e latência de cada interação. Não foi escolhido porque adicionaria operação e exposição de infraestrutura sem benefício para este portfólio.

**Direct Lake** passa a fazer sentido com adoção de Microsoft Fabric/OneLake, volume ou frequência de atualização maiores e capacidade contratada. No estado atual, introduzir Fabric apenas para demonstrar a tecnologia aumentaria custo e complexidade sem resolver um problema observado.

## Como repetir

1. Abra o PBIP, selecione um único escopo e use **Otimizar > Analisador de desempenho > Iniciar gravação > Atualizar visuais > Exportar**.
2. Conecte o DAX Studio à instância local do relatório, habilite **Server Timings**, execute a consulta preservada em `DAX_SERVER_TIMINGS.json` e compare duração, FE, SE e número de consultas.
3. Só otimize quando a nova medição identificar um gargalo; preserve os arquivos antes/depois com o mesmo filtro e cache declarado.
