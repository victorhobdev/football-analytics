# Plano operacional de ingestao confiavel de tecnicos

## Decisao central

Ranking e desempenho de tecnico nao devem nascer de `coach_tenure` puro.

O contrato estatistico correto e `fact_coach_match_assignment`: uma atribuicao unica de tecnico principal para cada `match_id + team_id`, com metodo, confianca e motivo de conflito quando nao for publicavel.

`coach_tenure` continua importante para historico de passagens, filtros por clube e contexto do perfil, mas nao pode ser a fonte direta de jogos, vitorias, gols ou aproveitamento.

## Problema atual

A pagina de tecnicos depende de um dado estrutural: quem era o tecnico principal de cada time em cada partida.

Hoje a base mistura:

- passagens incompletas;
- auxiliares e tecnicos principais sem papel confiavel;
- passagens sobrepostas;
- escopos de Copa do Mundo por edicao;
- nomes invalidos como `not applicable`;
- registros futuros em relacao ao horizonte publico do produto.

Isso gera risco direto para uma plataforma baseada em dados: ranking falso, tecnico omitido, auxiliar herdando jogo e status futuro aparecendo como se fosse atual.

## Horizonte de exibicao

O horizonte publico atual do produto e `2025-12-31`.

A regra deve ser centralizada em configuracao compartilhada, nao espalhada em query solta ou frontend:

```text
PRODUCT_DATA_CUTOFF = 2025-12-31
```

Regra publica:

- `start_date > PRODUCT_DATA_CUTOFF`: nao exibir;
- `start_date <= PRODUCT_DATA_CUTOFF` e `end_date > PRODUCT_DATA_CUTOFF`: exibir recortado ate o corte;
- `active` significa `ativo no corte`, nao ativo hoje;
- metricas publicas nunca consideram partidas depois do corte;
- dados futuros podem existir no banco apenas como preparo para release posterior.

## Bloco 0 - Localizar estado atual

Objetivo: entender o mapa real antes de criar tabela nova ou ingerir dado.

Tarefas:

- mapear tabelas atuais de tecnicos, staff, lineups, partidas e times;
- identificar como a pagina atual calcula tecnico/desempenho;
- descobrir se ja existe dado de tecnico por lineup/sumula;
- medir quais rotas e rankings consomem tecnico hoje;
- confirmar onde o corte `PRODUCT_DATA_CUTOFF` precisa ser aplicado.

Saida:

- inventario das tabelas existentes;
- fluxo atual de calculo;
- riscos de consumo publico;
- lista de fontes ja disponiveis para atribuicao por partida.

## Bloco 1 - Criar relatorio de auditoria

Nao ingerir nada novo antes desse bloco.

Objetivo: medir o dano atual por competicao, temporada e time.

Metricas obrigatorias:

```text
por competicao/temporada/time:
- partidas totais
- partidas com tecnico atribuido
- partidas sem tecnico
- partidas com multiplos tecnicos elegiveis
- passagens futuras
- passagens com nome invalido
- passagens de assistant/interino sendo usadas como principal
```

Saida operacional:

- SQL/script reproduzivel;
- CSV/JSON ou tabela de qualidade;
- ranking de areas mais afetadas;
- lista de conflitos para fila manual;
- cobertura por rota publica ou ranking impactado.

Colunas recomendadas:

```text
competition_key
league_id
season
team_id
team_name
matches_total
matches_with_assignment
matches_without_assignment
matches_with_conflict
invalid_name_tenures
future_tenures_hidden
assistant_as_head_risk
public_surface_impacted
```

## Bloco 2 - Criar staging antes das tabelas finais

Nao promover dado bruto direto para canonico.

Staging operacional:

```text
stg_coach_sources
stg_coach_tenures
stg_coach_lineup_assignments
stg_coach_identity_candidates
```

Objetivo:

- preservar fonte original;
- comparar fontes;
- reprocessar sem perder rastreabilidade;
- desfazer erro sem contaminar tabelas finais;
- calcular confianca antes de publicar.

Regras:

- todo registro de staging precisa de `source`, `source_record_id`, `source_payload`, `ingested_run` e `source_updated_at`;
- staging pode conter duplicidade e conflito;
- tabelas canonicas nao podem conter conflito nao resolvido.

## Bloco 3 - Desenhar migracao minima canonica

Criar ou adaptar tabelas canonicas somente depois da auditoria e staging.

### `coach_identity`

Representa a pessoa.

Campos minimos:

```text
coach_identity_id
provider
provider_coach_id
canonical_name
display_name
aliases
image_url
identity_confidence
source_refs
created_at
updated_at
```

Chave natural/idempotencia:

```text
provider + provider_coach_id
```

Regras:

- todo tecnico publico precisa de `display_name`;
- `not applicable`, `unknown`, `null`, `N/A` e equivalentes nao entram como nome;
- merge de identidade exige evidencia, nao apenas string parecida;
- asset nao define identidade.

### `coach_tenure`

Representa passagem por time.

Campos minimos:

```text
coach_tenure_id
coach_identity_id
team_id
role
start_date
end_date
source
source_confidence
is_date_estimated
is_current_as_of_source
source_updated_at
created_at
updated_at
```

Roles:

```text
head_coach
interim_head_coach
assistant
unknown
```

Chave natural/idempotencia:

```text
coach_identity_id + team_id + role + start_date + source
```

Regras:

- `head_coach` so entra com fonte explicita ou regra de promocao validada;
- auxiliar/interino nao deve virar principal por intervalo bruto;
- data estimada precisa ser marcada como estimada;
- passagem futura pode existir, mas nao e publica antes do corte.

### `fact_coach_match_assignment`

Representa a atribuicao por partida.

Campos minimos:

```text
match_id
team_id
coach_identity_id
coach_tenure_id
assignment_method
assignment_confidence
conflict_reason
is_public_eligible
created_at
updated_at
```

Chave natural/idempotencia:

```text
match_id + team_id
```

Constraint forte:

```text
unique(match_id, team_id)
```

Regra: nao pode haver mais de um tecnico principal publico para o mesmo `match_id + team_id`.

## Bloco 4 - Backfill controlado

So iniciar depois do relatorio de auditoria.

Prioridade:

```text
1. areas ja expostas em pagina publica ou ranking afetado
2. Flamengo 2020-2025
3. Serie A BR 2020-2025
4. Copa do Mundo
5. competicoes internacionais ja visiveis
```

Regra de prioridade:

Nao enriquecer area invisivel enquanto pagina publica/ranking continua estatisticamente inseguro.

Validacao manual inicial:

- Flamengo 2020-2025;
- casos conhecidos: Domènec, Rogerio Ceni, Renato Gaucho, Paulo Sousa, Dorival, Vitor Pereira, Sampaoli, Tite, Filipe Luis;
- distinguir tecnico principal, interino e auxiliar;
- comparar partidas atribuidas com calendario real do clube.

## Bloco 5 - Materializar `fact_coach_match_assignment`

Objetivo: parar de recalcular intervalo de datas em runtime.

Ordem de decisao:

1. se houver tecnico da partida em lineup/sumula, usar esse dado;
2. se houver exatamente um `head_coach` elegivel na data, usar ele;
3. se houver `interim_head_coach` explicito na data, usar interino;
4. se houver conflito, nao atribuir automaticamente;
5. conflito fica com `is_public_eligible = false` e `conflict_reason` preenchido.

`assignment_method` sugeridos:

```text
lineup_source
single_head_coach_tenure
interim_head_coach_tenure
manual_override
inferred_low_confidence
blocked_conflict
```

Publicacao:

- rankings usam apenas `is_public_eligible = true`;
- perfil pode exibir passagem sem jogos materializados;
- passagem sem assignment confiavel nao participa de ranking de desempenho.

## Bloco 6 - Trocar consumo do BFF/frontend

Objetivo: rankings, lista e perfil de tecnico passam a consumir `fact_coach_match_assignment`.

Mudancas:

- BFF nao calcula jogos por intervalo bruto;
- lista de tecnicos ordena por metricas derivadas de assignments confiaveis;
- perfil mostra passagens de `coach_tenure`, mas estatisticas por `fact_coach_match_assignment`;
- tecnico sem jogos confiaveis aparece como passagem/historico, nao como ranking;
- payload inclui coverage de atribuicao.

## Assets por ultimo

Foto de tecnico melhora experiencia, mas nao corrige confianca estatistica.

Regras:

- asset nao define identidade;
- foto real precisa estar vinculada ao `coach_identity_id`;
- placeholder e imagem generica devem ser marcados explicitamente;
- ausencia de foto usa avatar por iniciais;
- ingestao de asset nao bloqueia publicacao estatistica se identidade e assignment estiverem confiaveis.

## Gates de qualidade

Antes de publicar dados novos:

- 100% dos tecnicos exibidos com nome resolvido;
- 0 passagens com `start_date > end_date`;
- 0 partidas publicas com mais de um tecnico principal para o mesmo `match_id + team_id`;
- 0 partidas com auxiliar recebendo jogo quando existe tecnico principal elegivel;
- 0 respostas publicas com datas posteriores a `PRODUCT_DATA_CUTOFF`;
- `fact_coach_match_assignment` idempotente por `match_id + team_id`;
- coverage de atribuicao reportado por competicao/temporada/time;
- conflitos ficam bloqueados, nao inferidos silenciosamente.

## Contratos de UI

A UI deve diferenciar:

- `historico confirmado`;
- `ativo no corte`;
- `sem jogos materializados`;
- `pendente de ingestao`;
- `conflito de atribuicao`;
- `fora do horizonte publico`.

Dados pendentes podem aparecer como placeholder em areas de auditoria, mas nao devem participar de ranking de desempenho.

## Proximo passo seguro

Comecar pelo Bloco 0 e Bloco 1.

Entrega recomendada imediata:

```text
quality/coach_assignment_audit.sql
quality/coach_assignment_audit_sample.csv
quality/coach_assignment_audit_summary.md
```

O relatorio deve dizer onde ingerir, quanto falta, quais conflitos existem e qual parte da pagina atual esta estatisticamente insegura.
