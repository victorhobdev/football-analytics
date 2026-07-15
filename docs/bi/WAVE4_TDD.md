# Wave 4 — evidência TDD

## Origem e garantias

Os cenários foram derivados do pedido da Wave 4. O escopo validado é o contrato de snapshots, a resolução do diretório, a parametrização M e a reconciliação estrutural do relatório.

| Garantia | Teste | Resultado |
| --- | --- | --- |
| CLI vence o ambiente e caminhos relativos partem da raiz do repositório | `bi/tests/test_wave4_contract.py` | PASS |
| Ambiente, `.env`, default técnico e caminho vazio têm comportamento definido | `bi/tests/test_wave4_contract.py` | PASS |
| Manifesto mantém sete tabelas de snapshot | `bi/tests/test_wave4_contract.py` | PASS |
| PBIR mantém oito páginas, seis públicas, duas de drill-through e 94 visuais | `bi/tests/test_wave4_contract.py` | PASS |
| As cinco imagens existentes são tratadas como evidência parcial | `bi/tests/test_wave4_contract.py` | PASS |
| As sete fontes M/TMDL usam `SnapshotRoot` em vez de caminho embutido | `bi/tests/test_wave4_contract.py` | PASS |

## RED/GREEN

- RED: `python -m pytest bi/tests/test_wave4_contract.py -q` falhou na coleta porque `DEFAULT_SNAPSHOT_DIR` ainda não existia (`285344e`).
- GREEN: `python -m pytest bi/tests -q` passou com 10 testes.
- Sintaxe e CLI: `python -m py_compile bi/scripts/export_powerbi_snapshots.py` e `python bi/scripts/export_powerbi_snapshots.py --help` passaram.

## Limites

Não há `pytest-cov` ou `coverage.py` disponível neste ambiente. A suíte não abre Power BI Desktop, não consulta banco real e não refaz os sete Parquets. A execução conjunta com `tests/test_http_client.py` permanece bloqueada por um import preexistente de `common`; o alvo BI isolado está verde.
