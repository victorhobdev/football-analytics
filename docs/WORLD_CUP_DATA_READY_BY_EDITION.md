# Copa do Mundo - Dados prontos por edicao

Atualizado em: 2026-04-11

Este documento lista, por Copa, quais dados ja foram ingeridos, normalizados e publicados em superficies `raw` prontas para consumo de produto.

Escopo considerado:

- `raw.fixtures`
- `raw.fixture_lineups`
- `raw.standings_snapshots`
- `raw.team_coaches`
- `raw.wc_match_events`
- `raw.wc_squads`
- `raw.wc_goals`
- `raw.wc_bookings`
- `raw.wc_substitutions`

Observacoes importantes:

- `fixtures`, `standings`, `team_coaches`, `squads` e `goals` cobrem todas as 22 edicoes de 1930 a 2022, respeitando o formato de cada torneio.
- `lineups`, `bookings` e `substitutions` sao parciais nas edicoes historicas porque dependem da cobertura disponivel nas fontes.
- `wc_match_events` nao deve ser lido como event stream completo em todas as Copas. Em 2018 e 2022 ha eventos ricos StatsBomb para o torneio completo. Em algumas edicoes historicas ha amostras StatsBomb; nas demais, o dominio representa eventos discretos Fjelstul, como gols, cartoes e substituicoes.
- `raw.match_events` continua fora do escopo da Copa. O consumo da Copa deve usar `raw.wc_match_events`.
- Esta tabela nao inclui estatisticas derivadas como `match_statistics` ou `fixture_player_statistics`.

## Tabela por Copa

| Copa | Jogos | Standings | Tecnicos | Squads/elencos | Lineups | Eventos de partida | Gols | Cartoes | Substituicoes | Observacao de cobertura |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1930 | 18 jogos | 13 linhas / 13 selecoes | 14 regs / 13 selecoes | 245 jogadores / 13 selecoes | nao disponivel | 70 eventos / 18 jogos | 70 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1934 | 17 jogos | 0 (formato sem grupos) | 17 regs / 16 selecoes | 342 jogadores / 16 selecoes | nao disponivel | 70 eventos / 17 jogos | 70 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1938 | 18 jogos | 0 (formato sem grupos) | 17 regs / 15 selecoes | 320 jogadores / 15 selecoes | nao disponivel | 84 eventos / 18 jogos | 84 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1950 | 22 jogos | 17 linhas / 13 selecoes | 13 regs / 13 selecoes | 281 jogadores / 13 selecoes | nao disponivel | 88 eventos / 22 jogos | 88 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1954 | 26 jogos | 16 linhas / 16 selecoes | 16 regs / 16 selecoes | 350 jogadores / 16 selecoes | nao disponivel | 140 eventos / 26 jogos | 140 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1958 | 35 jogos | 16 linhas / 16 selecoes | 17 regs / 16 selecoes | 352 jogadores / 16 selecoes | 88 linhas / 2 jogos | 7467 eventos / 33 jogos | 126 gols | nao disponivel | nao disponivel | Eventos ricos StatsBomb em amostra de 2 jogos; restante do dominio de eventos e discreto/parcial. |
| 1962 | 32 jogos | 16 linhas / 16 selecoes | 18 regs / 16 selecoes | 352 jogadores / 16 selecoes | 44 linhas / 1 jogo | 3843 eventos / 28 jogos | 89 gols | nao disponivel | nao disponivel | Eventos ricos StatsBomb em amostra de 1 jogo; restante do dominio de eventos e discreto/parcial. |
| 1966 | 32 jogos | 16 linhas / 16 selecoes | 16 regs / 16 selecoes | 352 jogadores / 16 selecoes | nao disponivel | 89 eventos / 29 jogos | 89 gols | nao disponivel | nao disponivel | Backbone historico com fixtures, tecnicos, squads e gols; sem lineups/cartoes/substituicoes. |
| 1970 | 32 jogos | 16 linhas / 16 selecoes | 16 regs / 16 selecoes | 349 jogadores / 16 selecoes | 923 linhas / 32 jogos | 20384 eventos / 32 jogos | 95 gols | 52 regs / 19 jogos | 208 regs / 32 jogos | Eventos ricos StatsBomb em amostra de 6 jogos; restante do dominio de eventos e discreto/parcial. |
| 1974 | 38 jogos | 24 linhas / 16 selecoes | 16 regs / 16 selecoes | 352 jogadores / 16 selecoes | 1053 linhas / 38 jogos | 19659 eventos / 38 jogos | 97 gols | 89 regs / 33 jogos | 214 regs / 37 jogos | Eventos ricos StatsBomb em amostra de 6 jogos; restante do dominio de eventos e discreto/parcial. |
| 1978 | 38 jogos | 24 linhas / 16 selecoes | 16 regs / 16 selecoes | 352 jogadores / 16 selecoes | 952 linhas / 38 jogos | 382 eventos / 38 jogos | 102 gols | 48 regs / 20 jogos | 232 regs / 38 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 1982 | 52 jogos | 36 linhas / 24 selecoes | 26 regs / 24 selecoes | 526 jogadores / 24 selecoes | 1308 linhas / 52 jogos | 582 eventos / 52 jogos | 146 gols | 104 regs / 43 jogos | 332 regs / 50 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 1986 | 52 jogos | 24 linhas / 24 selecoes | 24 regs / 24 selecoes | 528 jogadores / 24 selecoes | 1391 linhas / 52 jogos | 9116 eventos / 52 jogos | 132 gols | 140 regs / 47 jogos | 378 regs / 52 jogos | Eventos ricos StatsBomb em amostra de 3 jogos; restante do dominio de eventos e discreto/parcial. |
| 1990 | 52 jogos | 24 linhas / 24 selecoes | 24 regs / 24 selecoes | 528 jogadores / 24 selecoes | 1353 linhas / 52 jogos | 3810 eventos / 52 jogos | 115 gols | 175 regs / 48 jogos | 380 regs / 52 jogos | Eventos ricos StatsBomb em amostra de 1 jogo; restante do dominio de eventos e discreto/parcial. |
| 1994 | 52 jogos | 24 linhas / 24 selecoes | 24 regs / 24 selecoes | 528 jogadores / 24 selecoes | 1343 linhas / 52 jogos | 775 eventos / 52 jogos | 141 gols | 236 regs / 52 jogos | 398 regs / 52 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 1998 | 64 jogos | 32 linhas / 32 selecoes | 34 regs / 32 selecoes | 705 jogadores / 32 selecoes | 1745 linhas / 64 jogos | 1114 eventos / 64 jogos | 171 gols | 269 regs / 64 jogos | 674 regs / 64 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 2002 | 64 jogos | 32 linhas / 32 selecoes | 33 regs / 32 selecoes | 736 jogadores / 32 selecoes | 1756 linhas / 64 jogos | 1131 eventos / 64 jogos | 161 gols | 274 regs / 62 jogos | 696 regs / 64 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 2006 | 64 jogos | 32 linhas / 32 selecoes | 32 regs / 32 selecoes | 736 jogadores / 32 selecoes | 1774 linhas / 64 jogos | 1214 eventos / 64 jogos | 147 gols | 335 regs / 64 jogos | 732 regs / 64 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 2010 | 64 jogos | 32 linhas / 32 selecoes | 32 regs / 32 selecoes | 736 jogadores / 32 selecoes | 1763 linhas / 64 jogos | 1118 eventos / 64 jogos | 145 gols | 263 regs / 62 jogos | 710 regs / 64 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 2014 | 64 jogos | 32 linhas / 32 selecoes | 32 regs / 32 selecoes | 736 jogadores / 32 selecoes | 1781 linhas / 64 jogos | 1108 eventos / 64 jogos | 171 gols | 191 regs / 64 jogos | 746 regs / 64 jogos | Eventos discretos Fjelstul: gols/cartoes/substituicoes; nao e event stream completo. |
| 2018 | 64 jogos | 32 linhas / 32 selecoes | 32 regs / 32 selecoes | 736 jogadores / 32 selecoes | 2886 linhas / 64 jogos | 227849 eventos / 64 jogos | 169 gols | 223 regs / 62 jogos | 764 regs / 64 jogos | Eventos ricos StatsBomb full tournament; gols/cartoes/substituicoes tambem disponiveis como registries Fjelstul. |
| 2022 | 64 jogos | 32 linhas / 32 selecoes | 32 regs / 32 selecoes | 831 jogadores / 32 selecoes | 3244 linhas / 64 jogos | 234652 eventos / 64 jogos | 172 gols | 225 regs / 62 jogos | 1174 regs / 64 jogos | Eventos ricos StatsBomb full tournament; gols/cartoes/substituicoes tambem disponiveis como registries Fjelstul. |

## Leitura para produto

- Todas as Copas de 1930 a 2022 ja podem exibir calendario/resultados basicos, selecoes, tecnicos, elencos e gols.
- Copas de 1970 a 2022 ja podem exibir algum nivel de lineups, cartoes e substituicoes, com cobertura parcial em varios anos.
- Copas de 2018 e 2022 sao as unicas prontas hoje para uma experiencia de match view com evento rico de torneio completo.
- Copas com amostra StatsBomb historica (`1958`, `1962`, `1970`, `1974`, `1986`, `1990`) podem exibir eventos ricos apenas nos jogos amostrados; fora desses jogos, a cobertura de eventos e discreta/parcial.
