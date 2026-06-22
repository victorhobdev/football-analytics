# Data Viewer (Provisorio)

Objetivo: validar cobertura e qualidade dos dados no Postgres sem usar `gold`.
Escopo: somente `raw.*` e `mart.*`.

## Layout (pagina unica, estilo GE)

### 1) Coluna esquerda: Tabela (standings da rodada)
Fonte principal:
- `mart.standings_evolution`

Colunas usadas:
- `season`
- `round`
- `team_id`
- `position`
- `points_accumulated`
- `goals_for_accumulated`
- `goal_diff_accumulated`

Enriquecimento de nome do time (fallback):
- `raw.fixtures.home_team_id`, `raw.fixtures.home_team_name`
- `raw.fixtures.away_team_id`, `raw.fixtures.away_team_name`

### 2) Coluna direita: Jogos da rodada selecionada
Fonte principal:
- `raw.fixtures`

Colunas usadas:
- `fixture_id`
- `date_utc`
- `league_id`
- `season`
- `round`
- `status_short`
- `home_team_id`, `home_team_name`
- `away_team_id`, `away_team_name`
- `home_goals`, `away_goals`

Stats por time (join com `raw.match_statistics`):
- `total_shots`
- `shots_on_goal`
- `ball_possession`
- `corner_kicks`
- `fouls`

### 3) Bloco inferior: Checks
Fontes:
- `raw.fixtures`
- `raw.match_events`
- `raw.match_statistics`
- `mart.standings_evolution`
- `mart.league_summary` (quando existente)

Checks incluidos:
- Duplicidade de chave natural:
  - fixtures por `fixture_id`
  - events por `event_id`
  - statistics por `(fixture_id, team_id)`
- Cobertura de stats:
  - fixtures com 2 linhas em `raw.match_statistics`
  - fixtures sem stats
  - cobertura por rodada
- Contagens de tabelas

## Parametros recomendados
- `:league_id` (ex.: `71`)
- `:season` (ex.: `2024`)
- `:round_number` (inteiro da rodada)

## Arquivo de SQL
Todos os SQLs prontos estao em:
- `tools/data_viewer/sql_catalog.md`

## Execucao local (Streamlit)
1. Instalar dependencias:
```powershell
python -m pip install -r tools/data_viewer/requirements.txt
```

2. Configurar conexao Postgres:
- Preferencial: `FOOTBALL_PG_DSN`
- Fallback automatico no app: `POSTGRES_HOST/PORT/USER/PASSWORD/DB`

3. Subir app:
```powershell
streamlit run tools/data_viewer/app.py
```

4. Abrir no navegador:
- `http://localhost:8501`

## Comando unico (recomendado)

### Windows (PowerShell)
1. Definir DSN:
```powershell
$env:FOOTBALL_PG_DSN="postgresql+psycopg2://football:football@localhost:5432/football_dw"
```
2. Rodar:
```powershell
.\tools\data_viewer\run_viewer.ps1
```

### Linux/macOS
1. Definir DSN:
```bash
export FOOTBALL_PG_DSN="postgresql+psycopg2://football:football@localhost:5432/football_dw"
```
2. Dar permissao e rodar:
```bash
chmod +x tools/data_viewer/run_viewer.sh
./tools/data_viewer/run_viewer.sh
```

Os scripts:
- validam `FOOTBALL_PG_DSN`
- instalam dependencias se faltarem
- iniciam `streamlit run tools/data_viewer/app.py`
- tentam abrir `http://localhost:8501` automaticamente
