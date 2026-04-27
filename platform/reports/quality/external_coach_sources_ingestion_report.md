# External coach sources ingestion report

## Escopo

- Ambiente separado: `data/external_coach_sources/`
- Nenhuma promocao para `mart.coach_identity`, `mart.coach_tenure` ou `mart.fact_coach_match_assignment`.
- Fontes: Wikidata SPARQL, DBpedia SPARQL e MediaWiki API.

## Totais

- Run id: `external_coach_sources_1777082244`
- Base dir: `C:\Users\Vitinho\Desktop\Projetos\football-analytics\data\external_coach_sources\external_coach_sources_1777082244`
- Fatos externos normalizados: `157017`
- Fatos com nome de tecnico: `155567`
- Fatos com nome de time: `155567`
- Fatos com data inicial: `19865`
- Fatos relacionados a Flamengo: `336`

## Distribuicao por fonte

- `dbpedia_managerClub`: `121076`
- `wikidata_P286_team_to_person`: `17838`
- `wikidata_P6087_person_to_team`: `15676`
- `mediawiki_infobox_en`: `977`
- `mediawiki_raw_line_pt`: `871`
- `mediawiki_raw_line_en`: `579`

## Cobertura potencial por fatos datados

- `brasileirao_b` 2025 team `234948`: `38/38` (100.0%)
- `la_liga` 2020 team `594`: `38/38` (100.0%)
- `la_liga` 2020 team `2975`: `38/38` (100.0%)
- `la_liga` 2020 team `13258`: `38/38` (100.0%)
- `la_liga` 2021 team `594`: `38/38` (100.0%)
- `la_liga` 2021 team `2975`: `38/38` (100.0%)
- `la_liga` 2021 team `13258`: `38/38` (100.0%)
- `la_liga` 2022 team `594`: `38/38` (100.0%)
- `la_liga` 2022 team `13258`: `38/38` (100.0%)
- `la_liga` 2023 team `594`: `38/38` (100.0%)
- `la_liga` 2023 team `2975`: `38/38` (100.0%)
- `la_liga` 2023 team `13258`: `38/38` (100.0%)
- `la_liga` 2024 team `2975`: `38/38` (100.0%)
- `la_liga` 2024 team `13258`: `38/38` (100.0%)
- `ligue_1` 2020 team `79`: `38/38` (100.0%)
- `ligue_1` 2020 team `591`: `38/38` (100.0%)
- `ligue_1` 2021 team `79`: `38/38` (100.0%)
- `ligue_1` 2021 team `591`: `38/38` (100.0%)
- `ligue_1` 2022 team `79`: `38/38` (100.0%)
- `ligue_1` 2022 team `591`: `38/38` (100.0%)

## Amostra Flamengo

- `wikidata_P6087_person_to_team` | coach `Miguel Ângelo da Luz` | team `Clube de Regatas do Flamengo` | 1994-01-01 ate 1996-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Miguel Ângelo da Luz` | team `Clube de Regatas do Flamengo` | 1994-01-01 ate 2002-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Miguel Ângelo da Luz` | team `Clube de Regatas do Flamengo` | 2000-01-01 ate 1996-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Miguel Ângelo da Luz` | team `Clube de Regatas do Flamengo` | 2000-01-01 ate 2002-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Jorge Sampaoli` | team `Clube de Regatas do Flamengo` | 2023-04-14 ate 2023-09-28 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Rogério Ceni` | team `Clube de Regatas do Flamengo` | 2020-01-01 ate 2021-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Renato Gaúcho` | team `Clube de Regatas do Flamengo` | ? ate ? | conf `0.58`
- `wikidata_P6087_person_to_team` | coach `Nelsinho Baptista` | team `Clube de Regatas do Flamengo` | 2003-01-01 ate ? | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Dorival Júnior` | team `Clube de Regatas do Flamengo` | 2012-01-01 ate 2013-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Dorival Júnior` | team `Clube de Regatas do Flamengo` | 2018-01-01 ate ? | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Dorival Júnior` | team `Clube de Regatas do Flamengo` | 2022-01-01 ate ? | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Freddy Rincón` | team `Associação Atlética Flamengo` | ? ate ? | conf `0.58`
- `wikidata_P6087_person_to_team` | coach `Filipe Luís` | team `Clube de Regatas do Flamengo (categorias de base)` | 2024-01-01 ate 2024-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Filipe Luís` | team `Clube de Regatas do Flamengo` | 2024-01-01 ate ? | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Jaime de Almeida` | team `Clube de Regatas do Flamengo` | ? ate ? | conf `0.58`
- `wikidata_P6087_person_to_team` | coach `Deivid de Souza` | team `Clube de Regatas do Flamengo` | 2014-07-01 ate 2015-05-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Deivid de Souza` | team `Clube de Regatas do Flamengo` | 2015-04-01 ate 2015-04-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Jorge Jesus` | team `Clube de Regatas do Flamengo` | 2019-06-01 ate 2020-07-17 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Evaristo de Macedo` | team `Clube de Regatas do Flamengo` | 1993-01-01 ate 1995-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Evaristo de Macedo` | team `Clube de Regatas do Flamengo` | 1999-01-01 ate 1999-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Evaristo de Macedo` | team `Clube de Regatas do Flamengo` | 2002-01-01 ate 2003-01-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Modesto Bría` | team `Clube de Regatas do Flamengo` | ? ate ? | conf `0.58`
- `wikidata_P6087_person_to_team` | coach `Rogério Lourenço` | team `Clube de Regatas do Flamengo` | 2010-04-01 ate 2010-08-01 | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Mano Menezes` | team `Clube de Regatas do Flamengo` | 2013-01-01 ate ? | conf `0.72`
- `wikidata_P6087_person_to_team` | coach `Tite` | team `Clube de Regatas do Flamengo` | 2023-01-01 ate ? | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Maurício Souza` | team `Clube de Regatas do Flamengo` | 2021-11-29 ate 2021-12-29 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Jorge Sampaoli` | team `Clube de Regatas do Flamengo` | 2023-04-17 ate 2023-09-28 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Rogério Ceni` | team `Clube de Regatas do Flamengo` | 2020-11-10 ate 2021-07-10 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Dorival Júnior` | team `Clube de Regatas do Flamengo` | 2022-06-10 ate 2022-11-25 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Domènec Torrent` | team `Clube de Regatas do Flamengo` | 2020-07-31 ate 2020-11-09 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Paulo Sousa` | team `Clube de Regatas do Flamengo` | 2021-12-29 ate 2022-06-10 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Filipe Luís` | team `Clube de Regatas do Flamengo` | 2024-09-30 ate 2026-03-02 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Jorge Jesus` | team `Clube de Regatas do Flamengo` | 2019-06-01 ate 2020-07-17 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Vítor Pereira` | team `Clube de Regatas do Flamengo` | 2023-01-01 ate 2023-04-10 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Reinaldo Llanta` | team `Clube de Regatas do Flamengo` | 2017-08-14 ate 2018-01-07 | conf `0.72`
- `wikidata_P286_team_to_person` | coach `Tite` | team `Clube de Regatas do Flamengo` | 2023-10-09 ate 2024-09-30 | conf `0.72`
- `dbpedia_managerClub` | coach `Paulo César Carpegiani` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Cândido de Oliveira` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Cláudio Coutinho` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Fábio Moreno` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Gilmar Popoca` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Valdir Espinosa` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Paulo Silas` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Nelson Simões` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Moacir Pereira` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Waldemar Lemos` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Ricardo Gomes` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Rodrigo Caio` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Modesto Bria` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Deivid` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Marcelo Cabo` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Reinaldo Rueda` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Rodrigo Caetano` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Sebastião Rocha (football manager)` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Washington Rodrigues` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Izidor Kürschner` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Flávio Costa` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Dino Sani` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `Jayme de Almeida` | team `CR Flamengo` | ? ate ? | conf `0.42`
- `dbpedia_managerClub` | coach `João Pedro (footballer, born 1989)` | team `CR Flamengo` | ? ate ? | conf `0.42`

## Erros de fonte

- Nenhum erro de fonte.

## Proximo acoplamento seguro

- Criar camada de resolucao `external_coach_source_candidate -> coach_identity` com score de nome, data e time.
- Criar camada de resolucao `external team -> dim_team` sem upsert automatico.
- Promover primeiro apenas fatos com `source in wikidata_*`, time local resolvido e intervalo de datas cobrindo partida.
- DBpedia e MediaWiki raw entram como evidencia auxiliar, nao como verdade final.
