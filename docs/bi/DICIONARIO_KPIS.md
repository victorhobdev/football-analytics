# Dicionario de KPIs

As medidas abaixo assumem que `FactTeamMatch` contem somente placares validos. Nomes de tabela podem ser ajustados ao PBIP, mas a formula e o denominador nao.

| KPI | SQL de referencia | DAX |
| --- | --- | --- |
| Partidas | `count(*)` em `FactMatch` | `Partidas = DISTINCTCOUNT(FactMatch[match_id])` |
| Jogos do time | `count(*)` em `FactTeamMatch` | `Jogos do Time = COUNTROWS(FactTeamMatch)` |
| Vitorias | linhas com `result = 'Vitória'` | `Vitórias = CALCULATE([Jogos do Time], FactTeamMatch[result] = "Vitória")` |
| Empates | linhas com `result = 'Empate'` | `Empates = CALCULATE([Jogos do Time], FactTeamMatch[result] = "Empate")` |
| Derrotas | linhas com `result = 'Derrota'` | `Derrotas = CALCULATE([Jogos do Time], FactTeamMatch[result] = "Derrota")` |
| Pontos | `sum(points)` | `Pontos = SUM(FactTeamMatch[points])` |
| PPG | `sum(points) / count(*)` | `PPG = DIVIDE([Pontos], [Jogos do Time])` |
| Gols pro | `sum(goals_for)` | `Gols Pró = SUM(FactTeamMatch[goals_for])` |
| Gols contra | `sum(goals_against)` | `Gols Contra = SUM(FactTeamMatch[goals_against])` |
| Saldo | `sum(goals_for - goals_against)` | `Saldo de Gols = [Gols Pró] - [Gols Contra]` |
| PPG casa | media de `points` com `venue = 'Casa'` | `PPG Casa = CALCULATE([PPG], FactTeamMatch[venue] = "Casa")` |
| PPG fora | media de `points` com `venue = 'Fora'` | `PPG Fora = CALCULATE([PPG], FactTeamMatch[venue] = "Fora")` |
| Delta de mando | `PPG casa - PPG fora` | `Delta de Mando = [PPG Casa] - [PPG Fora]` |
| Gols de jogador | `sum(coalesce(goals, 0))` | `Gols = SUM(FactPlayerMatch[goals])` |
| Assistencias | `sum(coalesce(assists, 0))` | `Assistencias = SUM(FactPlayerMatch[assists])` |
| Finalizacoes | `sum(coalesce(shots_total, 0))` | `Finalizacoes = SUM(FactPlayerMatch[shots_total])` |
| Nota media | `avg(rating)` somente nao nulos | `Nota Media = AVERAGE(FactPlayerMatch[rating])` |

## Cobertura e leitura

`Cobertura de Placar %` compara partidas com placar válido ao total e `Status do Recorte` sinaliza cobertura adequada a partir de 95%. `Cobertura Estatísticas de Time %` e `Cobertura de Nota %` expõem a disponibilidade dos campos opcionais no filtro atual.

Essas medidas não transformam valores ausentes em zero. Rankings baseados em estatísticas opcionais devem ser interpretados junto à cobertura exibida; a classificação por pontos é uma agregação analítica e não aplica desempates regulamentares.

`Delta de Mando (20+ jogos)` retorna vazio para amostras menores que 20 jogos, evitando destacar diferenças instáveis no visual comparativo.

## Evolucao de pontos

Para a linha acumulada, use a data da dimensao e preserve o filtro do time e do escopo:

```DAX
Pontos Acumulados =
CALCULATE (
    [Pontos],
    FILTER ( ALLSELECTED ( DimDate[date_day] ), DimDate[date_day] <= MAX ( DimDate[date_day] ) )
)
```

Uma mesma data acumula todas as partidas daquele dia; essa e a granularidade deliberada da fonte.
