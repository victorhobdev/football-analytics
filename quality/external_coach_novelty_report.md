# External coach novelty analysis

## Objetivo

Separar o que parece ser dado novo aproveitavel do que tende a ser duplicacao ou evidencia auxiliar.

## Criterio de novidade

- Time externo resolve para `mart.dim_team`.
- Fato tem intervalo datado.
- Intervalo cobre partidas publicas sem tecnico em `mart.fact_coach_match_assignment`.
- Nao ha tecnico canonico com nome parecido no mesmo time/janela.
- Fonte tem peso maior quando vem de Wikidata com statement datado.

## Resumo

- Fatos analisados: `157017`
- Alta chance de novidade: `696`
- Provaveis duplicacoes: `140`
- Time nao resolvido/ambiguo: `120943`
- Soma bruta de partidas potencialmente cobertas por candidatos novos: `36209`

## Distribuicao dos candidatos novos por fonte

- `wikidata_P286_team_to_person`: `360`
- `wikidata_P6087_person_to_team`: `300`
- `mediawiki_infobox_en`: `36`

## Times com mais candidatos novos

- `Internacional`: `15`
- `Inter`: `14`
- `Flamengo`: `14`
- `Arsenal`: `13`
- `Corinthians`: `13`
- `Chelsea`: `12`
- `São Paulo`: `12`
- `Atlético Mineiro`: `12`
- `Santos`: `12`
- `Espanyol`: `12`
- `Paris Saint Germain`: `11`
- `Olympique Marseille`: `11`
- `Cruzeiro`: `11`
- `Hertha BSC`: `10`
- `Olympique Lyonnais`: `9`
- `Real Madrid`: `9`
- `Valencia`: `9`
- `Villarreal`: `8`
- `Celta de Vigo`: `8`
- `Sampdoria`: `8`
- `Vasco da Gama`: `8`
- `Wolverhampton Wanderers`: `7`
- `Deportivo Alavés`: `7`
- `Napoli`: `7`
- `Tottenham Hotspur`: `7`

## Top candidatos com maior chance de novidade

- score `0.95` | `wikidata_P286_team_to_person` | Eintracht Frankfurt | Oliver Glasner | 2021-07-01 ate 2023-06-30 | lacuna `76` jogos | http://www.wikidata.org/entity/statement/Q38245-36d25cb5-49be-ce65-33c0-c0daed693823
- score `0.95` | `wikidata_P286_team_to_person` | Paris Saint Germain | Mauricio Pochettino | 2021-01-02 ate 2022-07-05 | lacuna `73` jogos | http://www.wikidata.org/entity/statement/Q483020-b71774c5-4228-f0cc-721d-9eca0c09391f
- score `0.95` | `wikidata_P286_team_to_person` | Metz | Frédéric Antonetti | 2020-10-13 ate 2022-06-09 | lacuna `70` jogos | http://www.wikidata.org/entity/statement/Q221525-f41298a1-4290-6bee-d504-47487ffe2704
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Marseille | Jorge Sampaoli | 2021-03-08 ate 2022-07-01 | lacuna `49` jogos | http://www.wikidata.org/entity/statement/Q132885-b1a05757-4169-b339-f958-773af9cc42b1
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Lyonnais | Peter Bosz | 2021-05-29 ate 2022-10-09 | lacuna `48` jogos | http://www.wikidata.org/entity/statement/Q704-891d999c-4150-e5c9-74f9-65540e5c8179
- score `0.95` | `wikidata_P286_team_to_person` | Paris Saint Germain | Christophe Galtier | 2022-07-05 ate 2023-06-30 | lacuna `46` jogos | http://www.wikidata.org/entity/statement/Q483020-9ebf3d75-4211-f5a6-4130-a5e56c3249bd
- score `0.95` | `wikidata_P286_team_to_person` | Wolverhampton Wanderers | Bruno Lage | 2021-07-01 ate 2022-10-02 | lacuna `46` jogos | http://www.wikidata.org/entity/statement/Q19500-cc8b1697-48cf-b314-2c67-a76df861c0b3
- score `0.95` | `wikidata_P286_team_to_person` | Bayer 04 Leverkusen | Gerardo Seoane | 2021-07-01 ate 2022-10-05 | lacuna `45` jogos | http://www.wikidata.org/entity/statement/Q104761-1d9f165e-4779-e2b9-aaaf-6f1a4a4369c9
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Marseille | Igor Tudor | 2022-07-04 ate 2023-06-30 | lacuna `44` jogos | http://www.wikidata.org/entity/statement/Q132885-3575805f-4bd1-7f14-8ae5-b2cb47c989bf
- score `0.95` | `wikidata_P286_team_to_person` | FC Augsburg | Enrico Maaßen | 2022-07-01 ate 2023-10-09 | lacuna `41` jogos | http://www.wikidata.org/entity/statement/Q97905916-15DEB245-9FA9-4A6F-9600-0EDDAC560F7E
- score `0.95` | `wikidata_P286_team_to_person` | Borussia Dortmund | Marco Rose | 2021-07-01 ate 2022-05-20 | lacuna `40` jogos | http://www.wikidata.org/entity/statement/Q41420-4181d2e5-411b-f97b-cb7c-8f3c99b854af
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Lyonnais | Rudi Garcia | 2019-10-14 ate 2021-05-24 | lacuna `38` jogos | http://www.wikidata.org/entity/statement/Q704-5346fa9d-4522-1c52-0d60-8f962553dd71
- score `0.95` | `wikidata_P286_team_to_person` | Wolverhampton Wanderers | Nuno Espírito Santo | 2017-07-01 ate 2021-05-23 | lacuna `38` jogos | http://www.wikidata.org/entity/statement/q19500-814A173F-B7D1-44E9-9959-8EB15953FB5B
- score `0.95` | `wikidata_P286_team_to_person` | FC Augsburg | Markus Weinzierl | 2021-04-26 ate 2022-06-30 | lacuna `37` jogos | http://www.wikidata.org/entity/statement/Q97905916-8F7B21F3-D901-4B44-AAC5-76D74466DACF
- score `0.95` | `wikidata_P286_team_to_person` | Eintracht Frankfurt | Adi Hütter | 2018-07-01 ate 2021-06-30 | lacuna `34` jogos | http://www.wikidata.org/entity/statement/q38245-AF728C04-27BB-4259-9558-1D9E9C028E23
- score `0.95` | `wikidata_P286_team_to_person` | VfL Wolfsburg | Oliver Glasner | 2019-07-01 ate 2021-06-30 | lacuna `34` jogos | http://www.wikidata.org/entity/statement/Q101859-83b4112a-48fc-53c9-729e-bdf5fdc72133
- score `0.95` | `wikidata_P286_team_to_person` | Werder Bremen | Florian Kohfeldt | 2017-10-31 ate 2021-05-16 | lacuna `33` jogos | http://www.wikidata.org/entity/statement/q51976-46B25A7A-8B55-4A4A-8A37-9A7AC0A35568
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Lyonnais | Laurent Blanc | 2022-10-09 ate 2023-09-11 | lacuna `32` jogos | http://www.wikidata.org/entity/statement/Q704-044275b3-465f-9cc3-06d0-cda1b9ec937c
- score `0.95` | `wikidata_P286_team_to_person` | FC Augsburg | Heiko Herrlich | 2020-03-10 ate 2021-04-26 | lacuna `31` jogos | http://www.wikidata.org/entity/statement/Q97905916-1D1C7CCC-13D1-4F5B-90F4-FF9D268F2D5C
- score `0.95` | `wikidata_P286_team_to_person` | Hertha BSC | Pál Dárdai | 2021-01-25 ate 2021-11-29 | lacuna `29` jogos | http://www.wikidata.org/entity/statement/Q102720-e7fcaa29-4ace-a2ac-dc46-6f0307336f5a
- score `0.95` | `wikidata_P286_team_to_person` | Hertha BSC | Sandro Schwarz | 2022-06-02 ate 2023-04-16 | lacuna `28` jogos | http://www.wikidata.org/entity/statement/Q102720-76260a21-4271-14fe-48d5-29af6ac8d6e0
- score `0.95` | `wikidata_P286_team_to_person` | VfL Wolfsburg | Florian Kohfeldt | 2021-10-26 ate 2022-05-15 | lacuna `28` jogos | http://www.wikidata.org/entity/statement/Q101859-9657aadb-42db-7cbf-ffe7-3d80c31e8673
- score `0.95` | `wikidata_P286_team_to_person` | Borussia Dortmund | Edin Terzić | 2020-12-13 ate 2021-06-30 | lacuna `27` jogos | http://www.wikidata.org/entity/statement/Q41420-56a6d85b-432c-2942-b7e9-3bcbc2fc11e1
- score `0.95` | `wikidata_P286_team_to_person` | Deportivo Alavés | Javier Calleja Revilla | 2021-04-05 ate 2021-12-28 | lacuna `27` jogos | http://www.wikidata.org/entity/statement/Q223620-3304a905-43d8-239d-4871-47c1e5e39c91
- score `0.95` | `wikidata_P286_team_to_person` | Bayer 04 Leverkusen | Peter Bosz | 2018-12-23 ate 2021-03-23 | lacuna `26` jogos | http://www.wikidata.org/entity/statement/Q104761-2ec73ca0-439f-1a80-227b-35697fde96d5
- score `0.95` | `wikidata_P286_team_to_person` | Olympique Marseille | André Villas-Boas | 2019-07-01 ate 2021-02-02 | lacuna `26` jogos | http://www.wikidata.org/entity/statement/Q132885-e38eedfe-4ac2-ecb3-5431-4e100edcaa09
- score `0.95` | `wikidata_P286_team_to_person` | AFC Bournemouth | Gary O'Neil | 2022-11-28 ate 2023-06-19 | lacuna `23` jogos | http://www.wikidata.org/entity/statement/Q19568-536b102c-4e30-6168-ee07-7dd95003edd7
- score `0.95` | `wikidata_P286_team_to_person` | Paris Saint Germain | Thomas Tuchel | 2018-07-01 ate 2020-12-29 | lacuna `23` jogos | http://www.wikidata.org/entity/statement/Q483020-CA9539D6-9B8A-42FD-8422-7BBA5087E9C7
- score `0.95` | `wikidata_P286_team_to_person` | Wolverhampton Wanderers | Julen Lopetegui | 2022-11-14 ate 2023-08-08 | lacuna `23` jogos | http://www.wikidata.org/entity/statement/Q19500-68d5aa55-4e08-5138-9fd4-88c5a264f768
- score `0.914` | `wikidata_P286_team_to_person` | Atlético Madrid | Diego Simeone | 2011-12-23 ate ? | lacuna `176` jogos | http://www.wikidata.org/entity/statement/Q8701-E2BF6B96-AEF8-4000-A250-EBD55621D263
- score `0.914` | `wikidata_P286_team_to_person` | FC Bayern München | Alexander Straus | 2022-01-01 ate ? | lacuna `106` jogos | http://www.wikidata.org/entity/statement/Q540384-e191fbf2-4268-f293-00e8-3944b6994b8a
- score `0.914` | `wikidata_P286_team_to_person` | Sporting CP | Randall Row | 2016-06-24 ate ? | lacuna `54` jogos | http://www.wikidata.org/entity/statement/Q24828730-02158eba-4d6a-5e6d-cd0d-cbfd419a62e1
- score `0.914` | `wikidata_P286_team_to_person` | Paris Saint Germain | Luis Enrique Martínez García | 2023-07-05 ate ? | lacuna `46` jogos | http://www.wikidata.org/entity/statement/Q483020-4c85a2f6-494d-a56a-77a3-9f50f3944716
- score `0.898` | `wikidata_P286_team_to_person` | Deportivo Alavés | Pablo Machín | 2020-08-05 ate 2021-01-12 | lacuna `18` jogos | http://www.wikidata.org/entity/statement/Q223620-c60d6b60-4fa4-c045-4bb3-06e1fc39a8c8
- score `0.898` | `wikidata_P286_team_to_person` | Hertha BSC | Bruno Labbadia | 2020-04-09 ate 2021-01-24 | lacuna `18` jogos | http://www.wikidata.org/entity/statement/Q102720-30077bbe-4246-1ffa-0574-75c3b838d336
- score `0.88` | `wikidata_P6087_person_to_team` | Atlético Madrid | Diego Simeone | 2011-12-23 ate 2024-01-06 | lacuna `162` jogos | http://www.wikidata.org/entity/statement/Q258115-9A541D6B-17AB-4078-8884-CD41078DC5D0
- score `0.88` | `wikidata_P6087_person_to_team` | Real Sociedad | Natalia Arroyo Clavell | 2020-01-01 ate 2024-06-01 | lacuna `140` jogos | http://www.wikidata.org/entity/statement/Q44172896-dce05010-4462-6518-8be3-85b9c1c4062c
- score `0.88` | `wikidata_P6087_person_to_team` | Paris Saint Germain | Mauricio Pochettino | 2021-01-02 ate 2022-07-05 | lacuna `73` jogos | http://www.wikidata.org/entity/statement/Q313000-62db45ae-4e1e-3511-a3e1-e24e35398eb7
- score `0.88` | `wikidata_P6087_person_to_team` | Metz | Frédéric Antonetti | 2020-10-12 ate 2022-06-09 | lacuna `70` jogos | http://www.wikidata.org/entity/statement/Q128824-60c42eab-43d6-f7c8-8644-1d3cb6993026
- score `0.88` | `wikidata_P6087_person_to_team` | Paris Saint Germain | Christophe Galtier | 2022-01-01 ate 2023-07-05 | lacuna `67` jogos | http://www.wikidata.org/entity/statement/Q129023-b45d7eda-45e4-7c25-0a80-44b6be9f5102

## Flamengo: candidatos mais relevantes

- score `0.855` | `wikidata_P286_team_to_person` | Dorival Júnior | 2022-06-10 ate 2022-11-25 | lacuna `43` jogos | sim existente `0.0`
- score `0.855` | `wikidata_P286_team_to_person` | Jorge Sampaoli | 2023-04-17 ate 2023-09-28 | lacuna `39` jogos | sim existente `0.0`
- score `0.808` | `wikidata_P286_team_to_person` | Paulo Sousa | 2021-12-29 ate 2022-06-10 | lacuna `18` jogos | sim existente `0.0`
- score `0.792` | `wikidata_P6087_person_to_team` | Jorge Sampaoli | 2023-04-14 ate 2023-09-28 | lacuna `40` jogos | sim existente `0.0`
- score `0.762` | `wikidata_P6087_person_to_team` | Dorival Júnior | 2018-01-01 ate ? | lacuna `176` jogos | sim existente `0.4`
- score `0.762` | `wikidata_P6087_person_to_team` | Mano Menezes | 2013-01-01 ate ? | lacuna `176` jogos | sim existente `0.32`
- score `0.762` | `wikidata_P6087_person_to_team` | Nelsinho Baptista | 2003-01-01 ate ? | lacuna `176` jogos | sim existente `0.4`
- score `0.762` | `wikidata_P6087_person_to_team` | Dorival Júnior | 2022-01-01 ate ? | lacuna `117` jogos | sim existente `0.4`
- score `0.762` | `wikidata_P6087_person_to_team` | Tite | 2023-01-01 ate ? | lacuna `56` jogos | sim existente `0.267`
- score `0.761` | `wikidata_P286_team_to_person` | Rogério Ceni | 2020-11-10 ate 2021-07-10 | lacuna `16` jogos | sim existente `0.0`
- score `0.667` | `wikidata_P286_team_to_person` | Tite | 2023-10-09 ate 2024-09-30 | lacuna `12` jogos | sim existente `0.118`
- score `0.558` | `mediawiki_infobox_en` | Dorival Júnior | 2022-01-01 ate 2022-12-31 | lacuna `61` jogos | sim existente `0.0`
- score `0.558` | `mediawiki_infobox_en` | Tite (football manager) | 2023-01-01 ate 2024-12-31 | lacuna `56` jogos | sim existente `0.25`
- score `0.558` | `mediawiki_infobox_en` | Vítor Pereira (footballer, born 1968) | 2023-01-01 ate 2023-12-31 | lacuna `56` jogos | sim existente `0.0`

## Provaveis duplicacoes

- `wikidata_P286_team_to_person` | Gil Vicente | Tozé Marreco | 2024-04-13 ate 2024-08-08 | similaridade `1.0` | overlaps `1`
- `wikidata_P286_team_to_person` | Porto | Vítor Bruno | 2024-07-01 ate 2025-01-20 | similaridade `1.0` | overlaps `4`
- `wikidata_P6087_person_to_team` | São Paulo | Thiago Carpini | 2024-01-01 ate ? | similaridade `1.0` | overlaps `5`
- `wikidata_P286_team_to_person` | Farense | Tozé Marreco | 2024-09-25 ate 2025-06-30 | similaridade `1.0` | overlaps `8`
- `wikidata_P286_team_to_person` | Vasco da Gama | Fábio Carille | 2024-12-19 ate ? | similaridade `1.0` | overlaps `11`
- `wikidata_P286_team_to_person` | Santos | Cléber Xavier | 2025-04-29 ate 2025-08-17 | similaridade `1.0` | overlaps `5`
- `wikidata_P286_team_to_person` | San Lorenzo | Rubén Insúa | 2022-05-18 ate ? | similaridade `1.0` | overlaps `2`
- `wikidata_P286_team_to_person` | VfL Wolfsburg | Daniel Bauer | 2025-05-04 ate 2025-06-30 | similaridade `1.0` | overlaps `1`
- `wikidata_P286_team_to_person` | Sporting Braga | Rui Duarte | 2024-04-03 ate 2024-06-30 | similaridade `1.0` | overlaps `4`
- `wikidata_P286_team_to_person` | Manchester United | Ruud van Nistelrooy | 2024-10-28 ate 2024-11-11 | similaridade `1.0` | overlaps `1`
- `wikidata_P286_team_to_person` | Real Valladolid | Álvaro Rubio | 2024-12-02 ate 2024-12-15 | similaridade `1.0` | overlaps `1`
- `wikidata_P286_team_to_person` | Southampton | Simon Rusk | 2024-12-15 ate 2024-12-22 | similaridade `1.0` | overlaps `1`
- `wikidata_P6087_person_to_team` | Cruzeiro | Fernando Seabra | 2024-01-01 ate ? | similaridade `1.0` | overlaps `31`
- `wikidata_P286_team_to_person` | Vitória | Fábio Carille | 2025-07-10 ate ? | similaridade `1.0` | overlaps `11`
- `wikidata_P6087_person_to_team` | Manchester United | Ruud van Nistelrooy | 2024-10-28 ate 2024-11-11 | similaridade `1.0` | overlaps `1`
- `mediawiki_infobox_en` | Cruzeiro | Fernando Diniz | 2024-01-01 ate 2025-12-31 | similaridade `1.0` | overlaps `14`
- `wikidata_P6087_person_to_team` | Udinese | Fabio Cannavaro | 2024-04-01 ate 2024-06-30 | similaridade `1.0` | overlaps `5`
- `wikidata_P286_team_to_person` | Corinthians | Raphael Laruccia | 2024-07-03 ate 2024-07-12 | similaridade `1.0` | overlaps `2`
- `mediawiki_infobox_en` | Deportivo Alavés | Eduardo Coudet | 2024-01-01 ate 2026-12-31 | similaridade `1.0` | overlaps `22`
- `wikidata_P6087_person_to_team` | Olympique Marseille | Jean-Louis Gasset | 2024-02-01 ate 2024-06-01 | similaridade `1.0` | overlaps `11`

## Arquivos gerados

- Alta novidade: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_high_novelty_candidates.csv`
- Duplicacao provavel: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_likely_duplicates.csv`
- Time nao resolvido: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_unresolved_team_candidates.csv`
- Resumo JSON: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\quality\external_coach_novelty_summary.json`

## Leitura

- O melhor material para acoplamento automatico vem de Wikidata datado.
- DBpedia tem volume alto, mas grande parte e sem data: boa para ampliar nomes/passagens, fraca para atribuir partidas.
- MediaWiki raw deve ser usado como evidencia textual, nao como fonte direta.
