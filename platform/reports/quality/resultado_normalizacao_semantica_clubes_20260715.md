# Resultado da normalização semântica de clubes

**Data da análise:** 2026-07-15  
**Ambiente:** PostgreSQL local `football_dw`  
**Escopo:** análise, manifesto e materialização em schema sombra; nenhuma dimensão ou fato ativo foi reescrito  
**Resultado materializado em sombra:** **1.931 clubes únicos entre 3.060 registros legados**

## Conclusão executiva

Os 3.060 `team_id` de `mart.dim_team` não representam 3.060 clubes. A aplicação combinada de chaves nativas de provedor, partidas coincidentes, contexto de país/gênero/tipo, normalização de grafia e pesquisa externa confirmou **1.129 representações excedentes**. A cardinalidade canônica materializada em sombra é, portanto:

```text
3.060 registros legados
- 1.128 uniões entre representações
-     1 colapso contextual dos três legados Belenenses em clube + SAD
= 1.931 clubes canônicos
```

A soma inclui uma exceção importante: um único registro Elo chamado `Belenenses` muda de referente depois da separação entre o clube e a SAD. Ele não pode ser ligado por uma relação simples de um legado para um canônico; precisa ser dividido por contexto temporal.

O número anterior de **2.733** era apenas `3.060 - 327`, isto é, o resultado parcial dos componentes detectados por sobreposição de partidas. Os 327 não eram “casos restantes”; eram IDs excedentes já detectados por uma única técnica. A contagem de 1.931 substitui esse resultado parcial.

O critério congelado de 1.933 tinha um erro de aritmética: `raízes + 1` contava quatro entidades para os três legados Belenenses. A linha Elo mista e os dois IDs Transfermarkt formam dois canônicos, não quatro. O executor materializou o número corrigido e deixou o delta explícito.

## O que foi analisado

- 3.060 linhas e 3.060 IDs distintos em `mart.dim_team`;
- 519.744 lados de partidas em `mart.stg_matches`;
- 401 identidades legadas do Transfermarkt ligadas sem ambiguidade a `club_id` nativo;
- identidades de SportMonks, StatsBomb, Brasileirão, Elo e Fjelstul;
- nome, país, gênero, tipo de entidade, competição, cronologia e adversários;
- perfis e documentos externos para casos sem cobertura sobreposta ou com risco de homônimo;
- equipes masculinas, femininas, reservas/B, clubes extintos, refundados e SADs.

O script reproduzível é [analyze_team_identity_uniqueness.py](../../scripts/analyze_team_identity_uniqueness.py). Ele é somente leitura e não atualiza `raw`, `control` ou `mart`.

## Método e contribuição de cada evidência

As contagens abaixo são incrementais: uma ligação já provada por uma etapa anterior não é contada novamente.

| evidência | reduções incrementais |
|---|---:|
| fingerprint de partida entre fontes | 325 |
| mesmo `club_id` nativo do Transfermarkt | 43 |
| fragmentos Elo de mesmo nome e país | 405 |
| mesmo nome, país, gênero e tipo entre componentes | 249 |
| revisão externa de variantes sem sobreposição | 28 |
| nomes exatos revisados com contexto incompleto | 38 |
| grafia normalizada idêntica, com contexto compatível | 40 |
| **uniões totais** | **1.128** |
| colapso contextual Belenenses/B SAD (3 → 2) | **+1 redução** |
| **redução líquida** | **1.129** |

### 1. Fingerprint de partidas

O fingerprint usa data, competição, placar relativo e adversário normalizado. Exige fontes diferentes e pelo menos cinco partidas coincidentes. A técnica encontrou 181 componentes e 327 IDs excedentes no resultado bruto. Os vínculos de Belenenses foram retirados da união automática depois da verificação jurídica; restaram 325 uniões incrementais válidas.

Essa técnica confirma, por exemplo, três das quatro representações do Flamengo. A quarta, do Transfermarkt, não tem sobreposição temporal e foi resolvida pela chave nativa e pesquisa externa.

### 2. Chave nativa do Transfermarkt

Todos os 401 IDs legados do Transfermarkt usados no staging puderam ser associados a exatamente um `club_id` de `raw.tm_games`; nenhum ficou ambíguo. Cinquenta grupos repetiam o mesmo `club_id` em competições diferentes. Quarenta e três dessas reduções ainda não haviam sido obtidas pelo fingerprint.

O Flamengo do Transfermarkt usa `club_id=614`, correspondente ao [perfil do CR Flamengo no Transfermarkt](https://www.transfermarkt.com/flamengo-rio-de-janeiro/datenfakten/verein/614). Isso liga `Clube de Regatas do Flamengo` ao mesmo clube das outras três fontes sem depender de sobreposição de temporadas.

### 3. Fragmentação da fonte Elo

A view ativa criou IDs pela combinação de provedor, competição e nome. Assim, o mesmo clube recebeu outro ID ao mudar de divisão. Foram confirmadas 405 reduções desse tipo usando mesmo nome e mesmo país.

Nenhum par Elo assim agrupado jogou em ambos os IDs na mesma data. Isso é compatível com promoção/rebaixamento e incompatível com duas equipes simultâneas sendo fundidas silenciosamente.

Foi encontrada uma falha adicional no mapeamento: a divisão `EC` havia sido publicada como `copa_america_ec`/Equador. Na fonte, `EC` é a English Conference. A própria [página de dados ingleses do Football-Data](https://www.football-data.co.uk/data.php) lista a Conference junto das divisões da Inglaterra. A interpretação errada separava artificialmente Aldershot, York, Wrexham, Luton e dezenas de outros clubes ingleses.

### 4. Contexto semântico

Nome não foi usado isoladamente. Uma união por nome ou grafia exigiu compatibilidade de:

- país ou território;
- masculino/feminino;
- clube/seleção;
- equipe principal/reserva quando identificável;
- chave nativa ou contexto de competição;
- ausência de conflito cronológico ou jurídico conhecido.

Os metadados de gênero e país do StatsBomb foram lidos de `raw.statsbomb_competition_seasons`, inclusive para cinco IDs legados ausentes da definição ativa do staging. Isso impediu que Valencia, Sevilla, Köln e outras equipes femininas fossem incorporadas aos times masculinos só porque o nome normalizado era igual.

## Decisões externas relevantes

### Flamengo

Os quatro legados representam o mesmo clube:

| legado | fonte | decisão |
|---:|---|---|
| 1024 | SportMonks | mesmo canônico |
| 990561002513 | dataset Brasileirão | mesmo canônico |
| 1048633958805 | Transfermarkt `club_id=614` | mesmo canônico |
| 1049232567028 | Elo | mesmo canônico |

O ID legado escolhido como “sobrevivente” não tem significado de negócio. O executor deve alocar um novo ID interno e ligar as quatro identidades de origem a ele.

### Homônimos que permanecem separados

| nome repetido | entidades distintas |
|---|---|
| Liverpool | Liverpool FC, Inglaterra; Liverpool FC, Uruguai |
| Everton | Everton FC, Inglaterra; Everton de Viña del Mar, Chile |
| Boavista | Boavista FC, Portugal; Boavista-RJ, Brasil |
| Athletic Club | Athletic Club de Bilbao, Espanha; Athletic Club-MG, Brasil |
| Nacional | Club Nacional de Football, Uruguai; CD Nacional, Madeira |
| Peñarol | Peñarol, Uruguai; Penarol-AM, Brasil |
| Portuguesa | Portuguesa-SP, Brasil; Portuguesa FC, Venezuela |
| Universidad Católica | Universidad Católica, Chile; Universidad Católica, Equador |
| Apollon | Apollon Limassol, Chipre; Apollon Smyrnis, Grécia |

A CBF identifica o confronto de 2025 como [Portuguesa-SP x Botafogo-PB](https://www.cbf.com.br/futebol-brasileiro/jogos/copa-do-brasil/masculino/2025/550098/portuguesa-saf-x-botafogo-pb-saf/828956?view=documentos). A CONMEBOL identifica o outro registro como [Portuguesa (VEN) x Palestino (CHI)](https://www.conmebol.com/pt-br/noticias-pt-br/duas-mudancas-de-estadio-na-1a-fase/). A CONMEBOL também publica país junto de Nacional, Peñarol, Boca Juniors e Universidad Católica em seus [grupos e potes oficiais](https://gol.conmebol.com/libertadores/es/news/sorteo-de-la-fase-de-grupos-de-la-conmebol-libertadores-2026-fecha-horario-clasificados).

No caso de Apollon, o jogo de 2022 contra o Maccabi Haifa é oficialmente listado pela UEFA como [Apollon Limassol FC (CYP)](https://uefadirect.uefa.com/202/en/static/_content/results-ucl.pdf), enquanto o ID Elo disputa a liga grega.

### Masculino, feminino e equipe B

Continuam separados, entre outros:

- Manchester United e Manchester United feminino;
- Aston Villa e Aston Villa feminino;
- Villarreal e Villarreal feminino;
- Athletic Bilbao e Athletic Bilbao feminino;
- Real Madrid e Real Madrid B;
- Barcelona e Barcelona B;
- Villarreal e Villarreal B;
- Málaga e Málaga B.

### Belenenses e B SAD

O Clube de Futebol Os Belenenses afirma oficialmente que [Belenenses e B SAD não têm relação](https://www.osbelenenses.com/2022/04/tribunal-da-relacao-confirma-belenenses-e-b-sad-nao-tem-qualquer-relacao/) após a separação. O acordo posterior também reconhece que os registos anteriores a 30 de junho de 2018 pertencem ao clube, conforme o [comunicado oficial de 2024](https://www.osbelenenses.com/2024/12/acordo-entre-clube-de-futebol-os-belenenses-e-a-sua-antiga-sociedade-anonima-sad/).

No banco:

- `1002633571734 — Belenenses` cobre 2000-08-20 a 2022-05-14 e mistura os dois referentes;
- `1025187804228 — CF Os Belenenses` cobre o período anterior à cisão;
- `1030245672235 — B SAD` cobre o período posterior.

Decisão: criar dois canônicos e uma identidade de origem contextual/temporal para o legado Elo. Não fundir os três IDs em um clube.

### Clubes extintos, refundados ou sucedidos

- Evian e Thonon foram agrupados apenas para as partidas do antigo Evian Thonon Gaillard cobertas no banco. A entidade refundada futura não deve herdar o vínculo automaticamente.
- Desportivo Aves e Aves foram agrupados para o histórico até 2020; AVS Futebol SAD e Aves 1930 permanecem separados.
- O Estrela da Amadora antigo, extinto em 2011, permanece separado do projeto atual. O [histórico oficial do Estrela](https://estrelamadora.pt/historia/) registra a refundação em 2011 e a fusão de 2020 que originou o Club Football Estrela da Amadora. As duas grafias atuais foram agrupadas entre si.
- Extremadura CF e Extremadura UD permanecem separados; são entidades sucessoras distintas.
- Os dois nomes Telford presentes nos dados de 2011–2015 foram agrupados como AFC Telford United. O [histórico oficial](https://telfordunited.com/internal/history/) confirma que o AFC foi criado em 2004 para substituir o Telford United extinto; não existe partida pré-2004 nesses dois registros analisados.
- `Osters` e `Oster` foram agrupados como Östers IF; a [UEFA identifica Öster como Östers IF](https://www.uefa.com/uefachampionsleague/history/clubs/50153--oster/).

## Pares de alta semelhança rejeitados

A revisão de grafia produziu 43 pares residuais acima de 0,82. Eles foram mantidos separados porque correspondem a homônimos, reservas, gênero distinto ou sucessores legais. Exemplos:

- Villa Nova ≠ Vila Nova;
- Reggiana ≠ Reggina;
- Ferroviária ≠ Ferroviário;
- SC Bastia ≠ CA Bastia;
- Fluminense-RJ ≠ Fluminense-PI;
- Rio Branco-ES ≠ Rio Branco-VN;
- São Raimundo-AM ≠ São Raimundo-RR;
- San Martín de Tucumán ≠ San Martín de San Juan;
- Botafogo-RJ ≠ Botafogo-PB;
- Granada CF ≠ Granada 74;
- Estrela da Amadora antigo ≠ Club Football Estrela da Amadora atual.

Isso demonstra por que fuzzy name não pode executar merge sozinho.

## Estado real do banco

O resultado de 1.931 é a cardinalidade **materializada em sombra**, não um cutover ativo:

- `mart.dim_team` continua com 3.060 linhas;
- `mart.fact_matches` continua com 259.872 `match_id` distintos;
- os fatos ainda referenciam IDs legados;
- `control.team_identity` ainda contém o bootstrap um-para-um de 3.060 IDs provisórios;
- nenhum merge, rekey ou delete foi executado nos marts ativos;
- `shadow_team_identity_20260715.canonical_team` contém 1.931 IDs novos;
- o crosswalk sombra contém 5.884 chaves, incluindo chaves nativas SportMonks/Transfermarkt e chaves contextuais Elo/Brasileirão;
- `shadow_team_identity_20260715.fact_matches_rekeyed` mantém 259.872 linhas, sem órfãos e sem `home_team_id = away_team_id`;
- os 43 pares negativos estão em `shadow_team_identity_20260715.negative_decision` e no TSV versionado.

## Plano de materialização para o agente executor

1. Congelar este resultado como manifesto versionado de decisões `merge`, `separate` e `split_context`.
2. Alocar **1.931 IDs internos novos**, sem derivá-los de nome, fonte, competição ou temporada. O número 1.933 foi rejeitado pela divergência Belenenses documentada acima.
3. Atualizar um único crosswalk autoritativo em `raw.provider_entity_map`, usando as chaves nativas reais de cada fonte.
4. Para Belenenses, criar chaves de origem contextuais e temporais; uma linha simples `legacy_id -> canonical_id` não é suficiente.
5. Gravar gênero, tipo, país e status no cadastro canônico; equipes B e femininas recebem IDs próprios.
6. Manter os 43 pares de alta semelhança rejeitados como decisões negativas auditáveis, para que reexecuções não os recoloquem na fila.
7. Reconstruir `dim_team` e todos os fatos em schema sombra. Não fazer updates manuais espalhados pelos marts.
8. Validar que as quatro origens Flamengo apontam para um canônico e que nenhum fato conserva os três IDs aposentados.
9. Somente depois do rekey de clubes, deduplicar partidas por chave de partida: data/hora tolerada, mandante canônico, visitante canônico, competição/edição e placar. Clube sozinho não é chave suficiente para apagar fatos.
10. Preservar filhos de partidas por manifesto; `linked_to_sportmonks` reutiliza `local_fixture_id`.
11. Executar full rebuild duas vezes e exigir idempotência, ausência de órfãos, `home_team_id != away_team_id` e nenhuma identidade `pending` publicada.

## Critérios de aceite específicos desta normalização

- `count(*)` do cadastro canônico de clubes = **1.931**;
- as 3.060 representações legadas estão ligadas, mantidas separadas ou cindidas por decisão explícita;
- Flamengo possui exatamente um canônico;
- Belenenses e B SAD possuem canônicos distintos;
- nenhum masculino foi unido a feminino ou equipe B;
- os nove grupos de homônimos listados permanecem separados;
- o código Elo `EC` é tratado como English Conference;
- a segunda execução produz o mesmo crosswalk e os mesmos IDs internos;
- nenhuma tabela `raw` é reescrita.

## Limite da conclusão

Não existe um identificador mundial único que cubra todas as fontes e toda a história do futebol. O número 1.931 é a contagem de alta confiança para o acervo atual, obtida com regras conservadoras e decisões externas documentadas. Novas fontes ou partidas podem revelar outra cisão histórica ou outro alias; por isso o modelo final precisa aceitar `merged`, decisões negativas e vínculos contextuais sem trocar o ID canônico já publicado.
