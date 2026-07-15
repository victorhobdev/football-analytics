# Dicionário de medidas DAX

Catálogo gerado a partir do TMDL executável. **73 medidas**; fórmulas completas em `bi/FootballAnalytics_DesempenhoCompetitivo.SemanticModel/definition/tables/Medidas.tmdl`.

## Regras de negócio críticas

- **PPG:** pontos divididos por jogos do time.
- **PPG Últimos 5:** PPG dos cinco jogos mais recentes dentro do contexto filtrado.
- **Conversão de Finalizações:** só aparece com 95%+ de cobertura, 50+ finalizações e gols não superiores às tentativas.
- **Métricas por 90:** só aparecem com 900+ minutos.
- **Percentil PPG:** posição relativa entre times do contexto selecionado; não é classificação oficial.
- **Ausência:** valores sem cobertura permanecem nulos e não são convertidos em zero.

## Benchmark

| Medida | Formato |
| --- | --- |
| PPG Médio do Recorte | `0.00` |
| Delta PPG vs Recorte | `+0.00;-0.00;0.00` |
| Percentil PPG | `0%` |
| PPG Últimos 5 | `0.00` |
| Delta Forma 5 Jogos | `+0.00;-0.00;0.00` |

## Competição

| Medida | Formato |
| --- | --- |
| Gols por Partida | `0.00` |
| Vitórias Mandante | `0` |
| Vitórias Visitante | `0` |
| Empates da Competição | `0` |
| Taxa Vitória Mandante % | `0.0%;-0.0%;0.0%` |
| Taxa Vitória Visitante % | `0.0%;-0.0%;0.0%` |
| Taxa de Empates % | `0.0%;-0.0%;0.0%` |

## Jogadores

| Medida | Formato |
| --- | --- |
| Gols | `0` |
| Assistências | `0` |
| Minutos | `0` |
| Finalizações | `0` |
| Finalizações no Alvo | `0` |
| Nota Média | `0.00` |
| Cartões Amarelos | `0` |
| Cartões Vermelhos | `0` |
| Cartões Totais | `0` |
| Jogos do Jogador | `0` |
| Participações em Gol | `0` |
| Gols por 90 (900+ min) | `0.00` |
| Participações por 90 (900+ min) | `0.00` |
| Precisão de Finalização do Jogador % | `0.0%;-0.0%;0.0%` |
| Participação nos Gols do Time % | `0.0%;-0.0%;0.0%` |

## Mando

| Medida | Formato |
| --- | --- |
| PPG Casa | `0.00` |
| PPG Fora | `0.00` |
| Delta de Mando | `0.00` |
| Delta de Mando (20+ jogos) | `0.00` |

## Qualidade

| Medida | Formato |
| --- | --- |
| Cobertura Estatísticas de Time % | `0.0%;-0.0%;0.0%` |
| Partidas sem Placar | `0` |
| Cobertura de Placar % | `0.0%;-0.0%;0.0%` |
| Status do Recorte | `Texto` |
| Cobertura de Nota % | `0.0%;-0.0%;0.0%` |
| Dados disponíveis até | `dd/MM/yyyy HH:mm` |
| Cobertura de Minutos % | `0.0%;-0.0%;0.0%` |
| Escopos | `0` |
| Partidas Declaradas | `0` |
| Cobertura de Placar Declarada % | `0.0%;-0.0%;0.0%` |
| Cobertura de Jogadores Declarada % | `0.0%;-0.0%;0.0%` |
| Escopos com Ranking de Jogadores | `0` |

## Resumo executivo

| Medida | Formato |
| --- | --- |
| Time de Referência | `Texto` |
| PPG (10+ jogos) | `0.00` |
| Resumo - O que aconteceu | `Texto` |
| Resumo - Onde | `Texto` |
| Resumo - Por que importa | `Texto` |
| Resumo - Ação sugerida | `Texto` |
| Resumo - Confiança | `Texto` |

## Tempo

| Medida | Formato |
| --- | --- |
| Pontos Acumulados | `0` |

## Times

| Medida | Formato |
| --- | --- |
| Vitórias | `0` |
| Empates | `0` |
| Derrotas | `0` |
| Pontos | `0` |
| PPG | `0.00` |
| Aproveitamento % | `0.0%;-0.0%;0.0%` |
| Gols Pró | `0` |
| Gols Contra | `0` |
| Saldo de Gols | `0` |
| Taxa de Vitória % | `0.0%;-0.0%;0.0%` |
| Posse Média % | `0.0%;-0.0%;0.0%` |
| Precisão de Passe % | `0.0%;-0.0%;0.0%` |
| Finalizações do Time | `0` |
| Finalizações no Alvo do Time | `0` |
| Gols por Jogo do Time | `0.00` |
| Gols em Jogos com Estatísticas | `0` |
| Conversão de Finalizações % | `0.0%;-0.0%;0.0%` |
| Precisão de Finalização % | `0.0%;-0.0%;0.0%` |

## Volume

| Medida | Formato |
| --- | --- |
| Partidas | `0` |
| Jogos do Time | `0` |
| Times | `0` |
| Gols Totais | `0` |
