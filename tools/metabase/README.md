# Metabase Versionamento

Este diretório versiona metadados de dashboard do Metabase sem incluir credenciais.

## Estrutura
- `exports/`: artefatos versionados (`metabase_export.json`)
- `scripts/export_metabase.py`: exporta dashboards + cards + coleções
- `scripts/import_metabase.py`: importa/atualiza dashboards em ambiente limpo

## Variáveis de ambiente
- `METABASE_URL` (default: `http://localhost:3000`)
- `METABASE_USERNAME` (obrigatória)
- `METABASE_PASSWORD` (obrigatória)
- `METABASE_DATABASE_NAME` (default: `football_dw`, usada no import)
- `METABASE_DASHBOARD_NAMES` (opcional no export, CSV)

## Export
```powershell
$env:METABASE_URL='http://localhost:3000'
$env:METABASE_USERNAME='admin@local'
$env:METABASE_PASSWORD='admin123'
python tools/metabase/scripts/export_metabase.py --out tools/metabase/exports/metabase_export.json
```

Export default tenta os dashboards:
- `Ranking Mensal`
- `Forma Recente`
- `Desempenho Casa/Fora`
- `Gols por Minuto`

## Import / Restore
Pré-requisito:
1. Stack no ar (`docker compose up -d`)
2. Metabase inicializado e conectado ao banco `football_dw` (ou nome configurado em `METABASE_DATABASE_NAME`)

Comando:
```powershell
$env:METABASE_URL='http://localhost:3000'
$env:METABASE_USERNAME='admin@local'
$env:METABASE_PASSWORD='admin123'
$env:METABASE_DATABASE_NAME='football_dw'
python tools/metabase/scripts/import_metabase.py --in-file tools/metabase/exports/metabase_export.json
```

## Notas de idempotência
- Reexecutar import atualiza cards/dashboards por nome e recria layout do dashboard.
- Artefato muda somente quando metadado muda (ordenação determinística no export).

## Segurança
- Não comitar credenciais no repositório.
- O artefato não inclui senha/token de usuário.
