# Football Analytics Performance Budgets

Este documento registra os budgets operacionais da frente de otimizacao. Os
valores devem ser medidos em ambiente local/prod equivalente antes de cada wave.

## Budgets iniciais por endpoint

| Area | Endpoint | Target p50 local | Target payload | Observacao |
| --- | --- | ---: | ---: | --- |
| Home | `/api/v1/home` | <= 150 ms | <= 15 KB | Servido por `mart.competition_serving_summary`. |
| Jogadores | `/api/v1/players?pageSize=20` | <= 150 ms | <= 15 KB | Recorte global deve usar `mart.player_serving_summary`. |
| Rankings | `/api/v1/rankings/player-goals?pageSize=20` | <= 200 ms | <= 15 KB | Recorte global deve usar `mart.player_serving_summary`. |
| Partidas | `/api/v1/matches?pageSize=20` | <= 150 ms | <= 20 KB | Depende de indices em dims usadas no join. |
| Mercado | `/api/v1/market/transfers?pageSize=24` | <= 150 ms | <= 15 KB | Manter filtros server-side. |
| Times | `/api/v1/teams?pageSize=20` | <= 100 ms | <= 10 KB | Ja esta abaixo do budget local. |

## Budgets de assets

| Tipo | Target |
| --- | ---: |
| Avatar/thumb acima da dobra | <= 40 KB transferidos |
| Card de competicao/time | <= 120 KB transferidos |
| Hero editorial | <= 350 KB transferidos |
| Manifest lookup em rota quente | <= 50 ms apos cache local |

## Regras de validacao

- Registrar antes/depois com tempo de rota, payload e logs de query.
- Nao adicionar indice sem `EXPLAIN (ANALYZE, BUFFERS)` ou log de endpoint.
- Nao alterar layout para ganhar performance sem screenshot comparavel.
- Toda serving mart nova precisa ter migration local e model dbt equivalente.
- Dados globais historicos podem usar cache HTTP; requests autenticados ou com cookie ficam `no-store`.

## Comandos de medicao

```powershell
Measure-Command { Invoke-WebRequest "http://127.0.0.1:8000/api/v1/players?pageSize=20" | Out-Null }
```

```sql
explain (analyze, buffers)
-- query exata do endpoint
;
```
