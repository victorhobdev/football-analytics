# Contrato editorial de qualidade dos dados

Este contrato define regras minimas para a camada publica do produto. Ele nao altera IDs,
chaves tecnicas ou storage bruto; serve como criterio para BFFs, publication layer, testes
semanticos e revisao humana.

## Idioma e taxonomia

- O idioma padrao da camada publica e PT-BR.
- Paises, continentes, fases e tipos de competicao devem ser publicados com rotulo em PT-BR.
- Termos do provider em ingles podem existir em `raw`/staging, mas nao devem aparecer na UI ou em payloads publicos quando houver rotulo editorial.
- Exemplos obrigatorios:
  - `South America` -> `America do Sul`.
  - `quarter-finals` -> `Quartas de final`.
  - `semi-finals` -> `Semifinais`.

## Nomes canonicos

- Entidades publicas devem preservar o ID canonico atual e publicar um nome de exibicao separado.
- O nome de exibicao deve vir da melhor fonte editorial disponivel: catalogo/control, mart curado ou alias auditado.
- O provider pode fornecer insumo de nome e locale, mas nao e a verdade final do produto.
- World Cup deve ser tratada como competicao canonica publica, mesmo que continue usando routers e crosswalks proprios no curto prazo.

## Fallbacks permitidos

- Fallback tecnico nao deve ser exposto como identidade publica.
- Sao proibidos como rotulo publico final:
  - `Team #<id>`.
  - `Unknown Team #<id>`.
  - `Unknown Player #<id>`.
  - `Unknown Venue #<id>`.
  - ID puro como nome.
- Quando nao houver nome confiavel, usar estado neutro:
  - jogador: `Nome indisponivel`;
  - time: `Clube indisponivel`;
  - estadio: `Estadio indisponivel`;
  - origem/destino de transferencia: `Origem indisponivel` / `Destino indisponivel`.
- IDs tecnicos podem continuar no payload como identificadores, nunca como nome final.

## Mercado e transferencias

- `provider_type_id` deve ser preservado para rastreabilidade.
- A narrativa publica deve usar uma classificacao interna de movimento:
  - `permanent_transfer`;
  - `loan_out`;
  - `loan_return`;
  - `free_transfer`;
  - `contract_end`;
  - `career_end`;
  - `unknown`.
- `type_id = 9688` representa retorno de emprestimo e nao deve ser agregado como transferencia definitiva.
- Moeda so pode aparecer quando `currency` vier de fonte confiavel. Se `currency = null`, a UI deve mostrar valor sem simbolo monetario.

## Confianca, cobertura e revisao humana

- Payloads publicos devem caminhar para um envelope simples com:
  - `dataStatus`;
  - `confidence`;
  - `fallbackSource`;
  - `editorialStatus`;
  - `isProviderPlaceholder`.
- Dados provaveis, inferidos, parciais ou bloqueados nao devem ser exibidos com a mesma semantica de dados confirmados.
- Janelas conhecidas de baixa cobertura devem ser marcadas como `partial`, nao publicadas como ausencia silenciosa.

## Midia

- Imagens devem ser classificadas como:
  - `real`;
  - `editorial_fallback`;
  - `provider_placeholder`.
- Placeholder do provider nao deve ser tratado como foto real na camada publica.

## Criterios para quality gates

Um gate semantico critico deve falhar quando a camada publica contiver:

- sentinels tecnicos (`Unknown`, `Team #`, ID puro como nome);
- termos em ingles proibidos em campos de rotulo PT-BR;
- `type_id = 9688` tratado como transferencia definitiva;
- moeda exibida sem `currency` confiavel;
- placeholder do provider publicado como imagem real;
- entidade com status provavel/inferido sem metadado de confianca.
