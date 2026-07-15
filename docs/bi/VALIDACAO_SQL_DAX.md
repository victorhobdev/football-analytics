# Registro de validação SQL x DAX

## Exportação pública de 2026-07-15

| Filtro | Verificação SQL/Parquet | Resultado | DAX |
| --- | ---: | --- | --- |
| escopos preferenciais | 861 | PASS | pendente de refresh autenticado |
| projeto público | 245.603 partidas | PASS | pendente de refresh autenticado |
| projeto público | 491.198 linhas `FactTeamMatch` | PASS | pendente de refresh autenticado |
| projeto público | 607.096 linhas `FactPlayerMatch` | PASS | pendente de refresh autenticado |
| `sportmonks|la_liga|2024_25` | 380 partidas | PASS | pendente de refresh autenticado |
| `sportmonks|brasileirao_a|2025` | 380 partidas | PASS | pendente de refresh autenticado |

O bloco abaixo preserva a última reconciliação SQL x DAX concluída no Desktop e não deve ser confundido com o snapshot público novo.

Copie esta tabela a cada publicacao. A comparacao so e valida quando SQL e Power BI usam exatamente os mesmos filtros de `provider`, `competition_key`, `season_label`, data e time.

| Data | Filtro | KPI | SQL | DAX | Diferença | Resultado |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 2026-07-12 | projeto completo | Partidas | 259.872 | 259.872 | 0 | PASS |
| 2026-07-12 | projeto completo | Linhas `FactTeamMatch` | 519.734 | 519.734 | 0 | PASS |
| 2026-07-12 | projeto completo | Linhas `FactPlayerMatch` | 607.096 | 607.096 | 0 | PASS |
| 2026-07-12 | `sportmonks|la_liga|2024_25` | Partidas válidas | 380 | 380 | 0 | PASS |
| 2026-07-12 | `sportmonks|la_liga|2024_25` | Times | 20 | 20 | 0 | PASS |
| 2026-07-12 | `sportmonks|la_liga|2024_25` | Gols | 995 | 995 | 0 | PASS |
| 2026-07-12 | `sportmonks|la_liga|2024_25` | Gols por partida | 2,618421 | 2,618421 | 0 | PASS |
| 2026-07-12 | `sportmonks|la_liga|2024_25` | Casa / empate / fora | 169 / 97 / 114 | 169 / 97 / 114 | 0 | PASS |
| 2026-07-12 | Osasuna no recorte | J-V-E-D / pontos | 38-12-16-10 / 52 | 38-12-16-10 / 52 | 0 | PASS |
| 2026-07-12 | Osasuna no recorte | PPG / GF / GC / saldo | 1,368421 / 48 / 52 / -4 | 1,368421 / 48 / 52 / -4 | 0 | PASS |
| 2026-07-12 | Osasuna no recorte | PPG casa / fora / delta | 1,894737 / 0,842105 / 1,052632 | 1,894737 / 0,842105 / 1,052632 | 0 | PASS |
| 2026-07-12 | Barcelona no recorte | Jogos / pontos / PPG / PPG últimos 5 | 38 / 88 / 2,3158 / 2,4 | 38 / 88 / 2,32 / 2,40 | arredondamento | PASS |
| 2026-07-12 | Real Madrid no recorte | Jogos / pontos / PPG / PPG últimos 5 | 38 / 84 / 2,2105 / 2,4 | 38 / 84 / 2,21 / 2,40 | arredondamento | PASS |

O ranking de artilheiros também coincidiu ao usar a identidade canônica da `DimPlayer`: Kylian Mbappé Lottin 31 gols/3 assistências, Robert Lewandowski 27/2, Ante Budimir 21/4, Alexander Sørloth 20/2 e Ayoze Pérez 19/2. Agrupar apenas pelo nome cru subcontava Mbappé; esse método não é válido para reconciliação.

## Achados reproduzíveis do recorte de validação

- Mandantes venceram 169 de 380 jogos (44,47%); visitantes, 114 (30,00%); 97 terminaram empatados (25,53%).
- Foram 995 gols, média de 2,618 por partida.
- O Osasuna somou 52 pontos e apresentou diferença de 1,053 ponto por jogo entre casa e fora.
- Mbappé liderou os gols com 31, quatro acima de Lewandowski.

## Consultas de referencia

- Times: [`reconciliation_team_metrics.sql`](../../bi/validation/reconciliation_team_metrics.sql)
- Jogadores: [`reconciliation_player_metrics.sql`](../../bi/validation/reconciliation_player_metrics.sql)
- Fixture: [`reconciliation_laliga_2024_25.sql`](../../bi/validation/reconciliation_laliga_2024_25.sql)

Aceite: medidas inteiras devem coincidir exatamente; PPG e nota média podem diferir no máximo 0,001 por arredondamento. A reconciliação acima passou e a URL pública foi validada sem autenticação.
