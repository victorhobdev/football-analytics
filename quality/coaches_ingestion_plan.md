# Plano de ingestao confiavel de tecnicos

## Problema

A pagina de tecnicos depende de um dado estrutural: quem era o tecnico principal de cada time em cada partida.
Hoje a base mistura passagens incompletas, auxiliares, escopos de Copa do Mundo e registros futuros. Isso gera tres riscos:

- tecnicos conhecidos omitidos porque a passagem nao foi ingerida;
- tecnico auxiliar herdando jogos por sobreposicao de datas;
- eventos posteriores ao horizonte do produto aparecendo na interface.

## Horizonte de exibicao

Enquanto a plataforma estiver limitada a dados ate `2025-12-31`, qualquer registro posterior pode existir no banco, mas nao deve entrar em respostas publicas.

Regra de produto:

- `start_date > 2025-12-31`: nao exibir;
- `start_date <= 2025-12-31` e `end_date > 2025-12-31`: exibir recortado ate `2025-12-31`;
- status ativo deve ser interpretado como `ativo no corte`, nao como ativo hoje;
- metricas de jogos nunca devem considerar partidas depois de `2025-12-31`.

## Entidade canonica

Separar tres conceitos:

- `coach_identity`: pessoa canonica, com nome, nomes alternativos, nacionalidade quando disponivel e assets.
- `coach_tenure`: passagem de uma pessoa por um time, com papel, inicio, fim, fonte e confianca.
- `coach_match_assignment`: tecnico principal atribuido a uma partida/time.

O produto deve calcular desempenho a partir de `coach_match_assignment`, nao apenas de intervalo de datas.

## Modelo minimo

### `coach_identity`

- `coach_identity_id`
- `provider`
- `provider_coach_id`
- `canonical_name`
- `display_name`
- `aliases`
- `image_url`
- `identity_confidence`
- `source_refs`

### `coach_tenure`

- `coach_tenure_id`
- `coach_identity_id`
- `team_id`
- `role`: `head_coach`, `interim_head_coach`, `assistant`, `unknown`
- `start_date`
- `end_date`
- `source`
- `source_confidence`
- `is_date_estimated`
- `is_current_as_of_source`
- `source_updated_at`

### `coach_match_assignment`

- `match_id`
- `team_id`
- `coach_identity_id`
- `coach_tenure_id`
- `assignment_method`: `lineup_source`, `single_head_coach_tenure`, `manual_override`, `inferred`
- `assignment_confidence`
- `conflict_reason`

## Ordem de ingestao

### Bloco 1: auditoria da base atual

Objetivo: medir o buraco real antes de ingerir.

Checks:

- times com partidas sem tecnico principal;
- jogos com mais de um tecnico elegivel para o mesmo time;
- passagens com datas invertidas;
- passagens futuras em relacao ao corte de produto;
- tecnicos sem nome resolvido;
- registros `assistant` ou `position_id` secundario recebendo jogos.

Saida esperada:

- fila de correcoes manuais;
- lista de clubes prioritarios;
- cobertura por competicao/temporada.

### Bloco 2: linha do tempo por clube

Objetivo: completar `coach_tenure` antes de recalcular desempenho.

Prioridade inicial:

- Flamengo 2020-2025;
- clubes brasileiros Serie A 2020-2025;
- selecoes em Copa do Mundo;
- competicoes internacionais ja visiveis no produto.

Regra:

- uma passagem so entra como `head_coach` se houver fonte explicita;
- auxiliar/interino deve ter papel proprio;
- datas estimadas entram marcadas como estimadas, nunca como dado definitivo.

### Bloco 3: resolucao de identidade

Objetivo: impedir duplicidade e nomes ruins.

Regras:

- todo tecnico exibido precisa ter `display_name`;
- valores como `not applicable`, `unknown`, `null`, `N/A` nao entram como nome;
- aliases devem resolver acentos, abreviacoes e nomes comuns;
- merge de identidade exige evidencia de pelo menos dois sinais: nome, time, periodo, provider id ou fonte externa.

### Bloco 4: atribuicao por partida

Objetivo: desempenho deve ser por partida atribuida, nao por intervalo bruto.

Ordem de decisao:

1. se houver tecnico da partida na fonte de lineup/sumula, usar esse dado;
2. se houver exatamente um `head_coach` elegivel na data, usar ele;
3. se houver interino explicito na data, usar interino;
4. se houver conflito, nao atribuir automaticamente;
5. conflito vai para fila manual.

### Bloco 5: assets

Objetivo: melhorar visual sem bloquear confianca estatistica.

Regras:

- asset nao define identidade;
- foto real precisa estar vinculada ao `coach_identity_id`;
- placeholder e imagem generica devem ser marcados explicitamente;
- ausencia de foto usa avatar gerado por iniciais.

## Gates de qualidade

Antes de publicar dados novos:

- 100% dos tecnicos exibidos com nome resolvido;
- 0 passagens com `start_date > end_date`;
- 0 partidas com mais de um tecnico principal atribuido para o mesmo time;
- 0 partidas com tecnico auxiliar recebendo jogo quando existe tecnico principal elegivel;
- 0 respostas publicas com datas posteriores ao horizonte de produto;
- cobertura de atribuicao por competicao/temporada reportada no payload.

## Contratos de frontend

A UI deve diferenciar:

- `historico confirmado`;
- `ativo no corte`;
- `sem jogos materializados`;
- `pendente de ingestao`;
- `conflito de atribuicao`.

Dados pendentes podem aparecer como placeholder, mas nao devem participar de ranking de desempenho sem atribuicao confiavel.

## Proximo bloco recomendado

Criar uma tabela/relatorio de auditoria com:

- `team_id`;
- `team_name`;
- `season`;
- `matches_total`;
- `matches_with_coach_assignment`;
- `matches_without_assignment`;
- `matches_with_conflict`;
- `coach_tenures_missing_name`;
- `future_tenures_hidden`.

Esse relatorio vira o painel de qualidade da ingestao de tecnicos.
