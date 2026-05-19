# Competition Season Surface Mockup Adaptation Plan

## Status

- Documento novo.
- Este plano substitui o planejamento anterior da season hub para os proximos ciclos.
- A numeracao dos blocos recomeca aqui.

## 1. Objetivo

Adaptar a tela interna da edicao de competicao aos 3 mockups de referencia colocados em `frontend/mockups referencia/`, preservando o dominio real do produto:

- arquivo historico de edicoes encerradas
- rotas canonicas ja validadas
- filtros globais compactos ja validados
- diferenciacao real entre `league`, `cup` e `hybrid`

O objetivo nao e copiar HTML estatico ou semantica de competicao em andamento. O objetivo e transplantar:

- hierarquia visual
- composicao de modulos
- leitura por tipo de competicao
- densidade informativa
- linguagem de produto premium

para o produto real, com contratos e estados honestos.

## 2. Fonte de verdade

### 2.1 Referencia visual primaria

- `frontend/mockups referencia/season_hub_standings_bloco_3/code.html`
- `frontend/mockups referencia/season_hub_standings_bloco_3/screen.png`
- `frontend/mockups referencia/hub_de_competi_o_de_copa_pt_br/code.html`
- `frontend/mockups referencia/hub_de_competi_o_de_copa_pt_br/screen.png`
- `frontend/mockups referencia/hub_de_competi_o_h_brida_mockup/code.html`
- `frontend/mockups referencia/hub_de_competi_o_h_brida_mockup/screen.png`

### 2.2 Fonte de verdade funcional

- Rota de temporada: `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/page.tsx`
- Surface atual: `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- Shell atual: `frontend/src/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell.tsx`
- Filtro global: `frontend/src/shared/components/filters/GlobalFilterBar.tsx`
- Rotas/contexto: `frontend/src/shared/utils/context-routing.ts`
- Resolucao de tipo: `frontend/src/features/competitions/utils/competition-season-surface.ts`

### 2.3 Restricoes de produto que nao podem ser violadas

- Nao mexer na tela geral `/competitions`.
- Nao tratar season hub como experiencia live.
- Nao usar copy de "fase atual", "lider atual", "artilheiro atual", "em andamento", "proxima rodada", "probabilidade de titulo" ou equivalentes.
- Nao inventar fatos historicos quando o contrato nao sustenta a afirmacao.
- Nao abrir backend/BFF novo sem gap real comprovado.

## 3. Diagnostico objetivo do estado atual

### 3.1 O que esta certo e deve ser preservado

- O produto ja diferencia `league`, `cup` e `hybrid` por estrutura real da edicao.
- A rota canonica da temporada esta correta.
- O filtro compacto da season hub ja foi validado.
- A troca de `competicao` e `temporada` ja navega para a rota canonica.
- A shell atual ja removeu parte do excesso editorial do topo antigo.

### 3.2 O que esta insuficiente

- A shell da season hub ainda e generica demais.
- O topo atual ficou limpo, mas perdeu "presenca de produto".
- O layout principal ainda nao e orientado ao tipo da edicao.
- `routeCards` genericos no fim da shell nao ajudam a aproximar a experiencia dos mockups.
- O hero summary atual resolve cards historicos, mas nao resolve a arquitetura da pagina.

### 3.3 O problema real

O problema nao e "falta de mais um card" nem "falta de polish". O problema e estrutural:

- hoje a season hub ainda se comporta como uma pagina unica com conteudos encaixados
- os mockups pedem uma familia de superfices com canvas principal diferente por tipo
- a shell atual nao cria zonas explicitas para:
  - hero orientado a identidade
  - cards historicos
  - canvas principal
  - trilho secundario
  - modulos complementares por tipo

## 4. Leitura correta dos mockups

### 4.1 Mockup de liga

Leitura estrutural:

- topo com breadcrumb, identidade e filtro compacto
- tabs locais fortes logo abaixo
- conteudo principal dominado por classificacao
- rail lateral com modulos contextuais
- visual de workspace analitico

O que adaptar para o produto real:

- manter a tabela como modulo dominante
- trocar semantica live por semantica de edicao encerrada
- substituir widgets probabilisticos/live por modulos historicos ou factuais

### 4.2 Mockup de copa

Leitura estrutural:

- hero/banner forte
- cards metricos ao lado da identidade
- chaveamento como modulo central
- lateral com destaques e memoria de torneio

O que adaptar para o produto real:

- manter banner + cards historicos
- tratar chaveamento como "caminho para o titulo" da edicao encerrada
- evitar copy de jogo futuro ou proximas decisoes se nao houver base historica coerente

### 4.3 Mockup hibrido

Leitura estrutural:

- hero forte
- resumo da fase de grupos
- pre-visualizacao do mata-mata
- lateral de partidas decisivas e destaques

O que adaptar para o produto real:

- expor explicitamente a convivio entre grupos e mata-mata
- manter a fase de grupos como resumo, nao como pagina generica de tabela
- usar a area de chaveamento como preview historico da fase eliminatoria

### 4.4 Conclusao de produto

O reaproveitamento correto dos mockups e:

- copiar a arquitetura visual por tipo
- nao copiar a semantica temporal
- nao copiar widgets sem suporte factual

## 5. Cobertura real de dados

### 5.1 Dados confiaveis hoje

- `competition-structure`
  - escopo da edicao
  - fases
  - grupos
  - transicoes
  - formato estrutural
- `competition-analytics`
  - `seasonSummary.matchCount`
  - agregados por fase
- `ties`
  - confrontos de mata-mata
  - `winnerTeamName` quando resolvido
- `standings`
  - classificacao final e snapshots filtrados
- `group-standings`
  - tabelas de grupos
- `matches`
  - lista de jogos da edicao

### 5.2 Dados parcialmente confiaveis

- `campeao`
  - `league`: confiavel via classificacao final
  - `cup`: confiavel quando o vencedor da chave final estiver resolvido
  - `hybrid`: confiavel via mata-mata final; nao pode cair para lider de grupo ou tabela

### 5.3 Dados nao confiaveis para promessa editorial forte

- `artilheiro oficial da edicao`
  - o ranking atual `player-goals` usa `minSample=180`
  - o ranking aceita `roundId`, `venue`, `lastN` e `dateRange`
  - portanto ele mede artilharia do recorte e nao "artilheiro oficial da edicao" com seguranca

### 5.4 Dados nao cobertos hoje

- probabilidade de titulo
- hall da fama por titulos
- hero editorial com foto/fundo factual por edicao
- qualquer estado "ao vivo"

## 6. Decisoes fixas deste novo plano

### 6.1 Decisao de arquitetura

A season hub passa a ser tratada como:

- shell comum minima
- canvas principal orientado por tipo
- rail secundario orientado por tipo

Nao como:

- uma unica pagina generica com cards e paines encaixados

### 6.2 Decisao sobre o topo

O topo nao deve voltar ao hero verbal antigo.

Ele deve ser:

- mais forte visualmente
- mais proximo dos mockups
- mais economico em texto
- mais orientado a identidade e leitura rapida

### 6.3 Decisao sobre cards historicos

Os cards historicos continuam parte do produto final, mas deixam de ser a "solucao principal". Eles passam a ser uma faixa de resumo historico integrada ao hero.

### 6.4 Decisao sobre variacao por tipo

Os 3 tipos vao compartilhar:

- rota
- shell superior
- filtro
- breadcrumb
- navegacao local
- sistema visual base

Mas vao divergir em:

- modulo principal
- modulo secundario
- hierarquia de leitura abaixo do topo

## 7. Matriz de reaproveitamento vs reescrita

| Area | Acao | Motivo |
| --- | --- | --- |
| `GlobalFilterBar` season hub | reaproveitar | bloco 1 ja validou filtro compacto e navegacao canonica |
| `context-routing` | reaproveitar | base de rota correta e estavel |
| `competition-season-surface` | reaproveitar | classificacao `league/cup/hybrid` ja resolve o dominio central |
| hooks de dados (`structure`, `analytics`, `ties`, `standings`, `group-standings`, `matches`) | reaproveitar | cobertura suficiente para V1 real |
| `CompetitionSeasonSurfaceShell` | reescrever parcialmente | hoje nao oferece slots corretos para composicao por tipo |
| `CompetitionSeasonSurface` | reestruturar fortemente | hoje concentra logica demais e ainda modela a pagina como superficie generica |
| `heroSummary` atual | reaproveitar parcialmente | logica de `campeao` e `matchCount` ainda vale, mas precisa mudar de encaixe |
| `routeCards` genericos | remover/substituir | nao aderem aos mockups nem ao produto final |
| secoes internas de overview/structure/matches/highlights | revisar por tipo | algumas partes servem, outras precisam ser remontadas em nova hierarquia |

## 8. Arquitetura alvo

### 8.1 Shell comum

A shell comum deve conter apenas:

- breadcrumb interno
- area superior com:
  - contexto da edicao
  - identidade visual
  - tags minimas
  - cards historicos
- navegacao local
- slots de layout:
  - `mainCanvas`
  - `secondaryRail`
  - `supportingModules`

Deve sair da shell comum:

- `routeCards` genericos
- grade final fixa de atalhos
- hero summary amarrado a uma unica faixa linear

### 8.2 Shape visual desejado

Shape comum:

- `hero` forte mas compacto
- `summary strip` logo abaixo ou integrado ao hero
- `content grid` assimetrico

Estrutura base:

1. breadcrumb
2. hero/contexto
3. faixa de cards historicos
4. tabs locais
5. grid principal por tipo

### 8.3 Layout alvo por tipo

#### League

- Hero historico + cards historicos
- Tabs locais
- Grid `8/4` ou `9/3`
- Main:
  - classificacao dominante
- Rail:
  - metadados da edicao
  - resumo de janela final
  - modulos factuais leves

#### Cup

- Banner de identidade + cards historicos
- Tabs locais
- Grid `9/3`
- Main:
  - chaveamento / caminho para o titulo
- Rail:
  - destaques factuais da edicao
  - ultimos confrontos relevantes
  - memoria resumida do torneio se houver base

#### Hybrid

- Banner de identidade + cards historicos
- Tabs locais
- Grid `8/4` com duas camadas principais
- Main:
  - resumo da fase de grupos
  - preview do mata-mata
- Rail:
  - partidas decisivas da fase eliminatoria
  - destaques factuais

## 9. Plano de execucao por blocos

### Bloco 0 - Congelar baseline e limpar transicao antiga

#### Objetivo

Congelar a base que ja esta boa e remover pressupostos antigos do plano anterior.

#### O que sera feito

- Tratar este documento como plano mestre.
- Encerrar o uso de `routeCards` como estrutura esperada da season hub final.
- Reclassificar os cards historicos atuais como implementacao transitoria.
- Garantir que o codigo atual seja lido como baseline funcional, nao como arquitetura final.

#### Arquivos-alvo

- `docs/COMPETITION_SEASON_SURFACE_MOCKUP_ADAPTATION_PLAN.md`
- `frontend/src/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell.tsx`
- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`

#### Criterio de aceite

- equipe passa a usar este plano como referencia unica
- execucao futura nao volta a tratar a season hub como pagina generica

#### Risco

- baixo

### Bloco 1 - Reconstrucao da shell comum

#### Objetivo

Transformar a shell atual numa casca realmente reutilizavel para os 3 tipos, com slots adequados para composicao inspirada nos mockups.

#### O que sera feito

- Reescrever `CompetitionSeasonSurfaceShell` para expor slots claros:
  - `hero`
  - `summaryStrip`
  - `mainCanvas`
  - `secondaryRail`
  - `supportingModules`
- Remover `routeCards` da assinatura da shell.
- Preservar:
  - breadcrumb
  - `CanonicalRouteContextSync`
  - `ProfileTabs`
- Definir um grid base unico, capaz de acomodar:
  - liga com tabela dominante
  - copa com bracket dominante
  - hibrido com grupos + bracket preview

#### O que nao sera feito neste bloco

- desenhar o modulo principal de cada tipo
- resolver modulo de artilheiro
- polir cards finais por tipo

#### Arquivos-alvo

- `frontend/src/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell.tsx`
- possivel apoio pequeno em `frontend/src/shared/components/profile/ProfilePrimitives.tsx` somente se a shell exigir slot visual novo

#### Dependencias

- nenhuma dependencia nova de dado

#### Criterio de aceite

- shell deixa de impor `routeCards`
- shell passa a ter slots reais para layouts por tipo
- breadcrumb e tabs locais continuam presentes
- bloco 1 nao quebra filtro compacto validado

#### Riscos

- medio
- risco principal: mexer na shell e regredir leitura do topo ou nav local

### Bloco 2 - Hero e faixa de resumo historico finais

#### Objetivo

Reconstruir o topo para ficar visualmente proximo dos mockups, mas semanticamente correto para edicoes encerradas.

#### O que sera feito

- Reestruturar o hero superior.
- Definir um hero mais forte por identidade, nao por texto longo.
- Integrar os cards historicos na composicao final do topo.
- Reorganizar:
  - `campeao`
  - `artilheiro`
  - `partidas jogadas`

#### Decisao sobre `artilheiro`

- Se nao houver contrato confiavel novo, o card segue neutro.
- O layout deve suportar esse estado sem parecer erro.
- O produto nao vai fingir precisao.

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- `frontend/src/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell.tsx`

#### Dependencias

- `standings`
- `competition-analytics`
- `ties`
- nenhuma dependencia obrigatoria nova

#### Criterio de aceite

- topo final deixa de parecer faixa generica
- cards historicos ficam integrados ao hero
- copy permanece historica e enxuta

#### Riscos

- medio
- risco principal: hero ficar visualmente forte, mas ainda "flat" no desktop

### Bloco 3 - Canvas principal da liga

#### Objetivo

Levar a season hub de `league` para perto do mockup de classificacao.

#### O que sera feito

- Tornar a classificacao o modulo dominante do primeiro viewport util.
- Definir coluna principal e rail secundario.
- Reaproveitar a tabela atual, mas reposiciona-la como nucleo da pagina.
- Adicionar modulos historicos leves no rail:
  - resumo da edicao
  - janela final da temporada
  - destaque factual se houver base

#### O que nao sera feito

- widgets live
- probabilidade de titulo
- tendencia ao vivo

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- possiveis auxiliares internos do dominio de standings, se a composicao ficar grande

#### Dependencias

- `useStandingsTable`
- `useCompetitionAnalytics`
- possivel reaproveitamento de `FinalStandingsPanel`

#### Criterio de aceite

- a liga fica reconhecivel como workspace de classificacao
- a tabela domina a leitura
- a lateral nao usa widgets sem base historica

#### Riscos

- medio
- risco principal: cair em "pagina de tabela com cards jogados ao lado"

### Bloco 4 - Canvas principal da copa

#### Objetivo

Levar a season hub de `cup` para perto do mockup de chaveamento.

#### O que sera feito

- Construir o canvas principal com foco em `caminho para o titulo`.
- Reaproveitar `ties` e `structure` para montar uma visao editorial do mata-mata.
- Definir lateral com modulos secundarios factuais.
- Usar o hero forte da copa como abertura visual.

#### O que nao sera feito

- agenda futura ou "proximas decisoes" se a base nao fizer sentido historico
- live bracket

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- possivel helper minimo de bracket preview, se o JSX ficar ilegivel

#### Dependencias

- `useCompetitionStructure`
- `useStageTies`
- `useMatchesList`

#### Criterio de aceite

- copa deixa de parecer pagina genrica com secoes
- chaveamento vira modulo dominante real
- lateral sustenta a leitura sem concorrer com o canvas principal

#### Riscos

- medio/alto
- risco principal: estrutura de `ties` nao cobrir alguns torneios com a riqueza visual desejada

### Bloco 5 - Canvas principal do hibrido

#### Objetivo

Traduzir o mockup hibrido para uma season hub que mostre, no mesmo canvas, grupos e mata-mata.

#### O que sera feito

- Criar um resumo da fase de grupos com leitura editorial enxuta.
- Criar uma preview do mata-mata.
- Coordenar os dois modulos no mesmo grid principal.
- Adicionar rail secundario com partidas decisivas e destaques factuais.

#### O que nao sera feito

- transformar o hibrido em soma burocratica de uma pagina de grupo + uma pagina de copa

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`

#### Dependencias

- `useCompetitionStructure`
- `useGroupStandingsTable`
- `useStageTies`
- `useMatchesList`
- `useCompetitionAnalytics`

#### Criterio de aceite

- hibrido fica imediatamente legivel como formato misto
- grupos e mata-mata convivem no primeiro scroll
- pagina nao vira colagem de paines

#### Riscos

- alto
- risco principal: excesso de densidade e quebra de hierarquia

### Bloco 6 - Rails secundarias e modulos de apoio

#### Objetivo

Padronizar as laterais secundarias para que cada tipo tenha modulos uteis, honestos e visivelmente alinhados aos mockups.

#### O que sera feito

- Definir uma biblioteca pequena de modulos laterais:
  - `SeasonFactsCard`
  - `MatchesRailCard`
  - `HistoricalNoteCard`
  - `EditionSummaryCard`
- Mapear quais modulos fazem sentido por tipo.
- Eliminar modulos sem suporte factual.

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- possiveis auxiliares internos de season surface

#### Dependencias

- dados ja existentes

#### Criterio de aceite

- laterais deixam de ser sobras da pagina
- cada rail secundario reforca o tipo da competicao

#### Riscos

- medio

### Bloco 7 - Navegacao local, semantica e estados de pagina

#### Objetivo

Fechar a consistencia de navegacao local, nomenclatura e estados de leitura.

#### O que sera feito

- Revisar labels das tabs locais por tipo.
- Corrigir o padrao visual de ativo, se ainda estiver desalinhado.
- Revisar estados:
  - loading
  - vazio
  - erro
  - parcial
- Garantir que a pagina nao quebre quando `structure` vier parcial ou incompleta.

#### Arquivos-alvo

- `frontend/src/features/competitions/components/season-surface/CompetitionSeasonSurfaceShell.tsx`
- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- `frontend/src/shared/components/profile/ProfilePrimitives.tsx`, se o estado ativo realmente exigir ajuste compartilhado

#### Dependencias

- nenhuma dependencia nova

#### Criterio de aceite

- navegacao local consistente
- estados de pagina honestos
- nenhuma linguagem live vazando para a season hub

#### Riscos

- baixo/medio

### Bloco 8 - Integridade de dados e fallbacks honestos

#### Objetivo

Fechar o comportamento do produto quando o dado nao sustenta a promessa visual.

#### O que sera feito

- Formalizar fallbacks por modulo.
- Documentar onde o produto mostra:
  - `Nao identificado`
  - `Sem fonte oficial`
  - `Indisponivel no contrato atual`
- Garantir que nenhum card ou rail invente interpretacao forte sem base.

#### Arquivos-alvo

- `frontend/src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx`
- opcionalmente `docs/` se surgir necessidade de adendo de contrato

#### Criterio de aceite

- fallbacks ficam coerentes e reutilizaveis
- o produto continua premium sem mentir

#### Riscos

- baixo

### Bloco 9 - Validacao final e fechamento

#### Objetivo

Fechar a refatoracao com evidencia objetiva.

#### O que sera feito

- Validar `tsc`.
- Validar `next build`.
- Validar runtime em `league`, `cup` e `hybrid`.
- Validar:
  - breadcrumb
  - filtro compacto
  - navegacao canonica
  - tabs locais
  - modulos principais por tipo
  - fallbacks honestos
- Registrar evidencias de:
  - contrato sustentado
  - gaps residuais
  - riscos aceitos

#### Arquivos-alvo

- sem alvo fixo de produto; foco em validacao

#### Criterio de aceite

- build verde
- runtime estrutural verde
- season hub aderente aos mockups em composicao e hierarquia
- nenhum modulo sem base factual se passando por definitivo

#### Riscos

- baixo, se os blocos anteriores tiverem sido executados de forma incremental

## 10. Ordem segura de implementacao

Ordem obrigatoria:

1. Bloco 1
2. Bloco 2
3. Bloco 3
4. Bloco 4
5. Bloco 5
6. Bloco 6
7. Bloco 7
8. Bloco 8
9. Bloco 9

Justificativa:

- sem shell nova, a composicao por tipo fica improvisada
- sem hero final, os canvases abaixo ainda ficam desconectados
- `league` e o caso estruturalmente mais simples
- `cup` e `hybrid` dependem mais da qualidade da shell e dos modulos reutilizaveis

## 11. Criterio de "pronto"

A season hub so pode ser considerada pronta quando:

- os 3 tipos ficarem visualmente reconheciveis no primeiro viewport
- a composicao ficar claramente inspirada nos mockups de referencia
- a semantica continuar 100% historica
- o filtro canonico continuar funcionando
- `campeao` e `partidas jogadas` estiverem corretos
- `artilheiro` so aparecer como fato se um contrato confiavel existir
- a pagina nao depender de gambiarra de layout ou card genrico para "fechar volume"

## 12. Proximo passo recomendado

Executar o `Bloco 1 - Reconstrucao da shell comum`.

Este e o ponto certo para retomar a implementacao, porque:

- nao reabre rota nem filtro
- prepara a arquitetura correta para os 3 tipos
- elimina o principal desvio de direcao do plano anterior

