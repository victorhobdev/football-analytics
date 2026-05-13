$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReqFile = Join-Path $ScriptDir "requirements.txt"
$AppFile = Join-Path $ScriptDir "app.py"
$Url = "http://localhost:8501"

if (-not $env:FOOTBALL_PG_DSN) {
  Write-Error "Variavel FOOTBALL_PG_DSN nao definida. Exemplo: `$env:FOOTBALL_PG_DSN='postgresql+psycopg2://user:pass@localhost:5432/football_dw'"
  exit 1
}

try {
  python --version | Out-Null
} catch {
  Write-Error "Python nao encontrado no PATH. Instale Python 3.10+ e tente novamente."
  exit 1
}

if (-not (Test-Path $ReqFile)) {
  Write-Error "Arquivo de dependencias nao encontrado: $ReqFile"
  exit 1
}

if (-not (Test-Path $AppFile)) {
  Write-Error "Arquivo da app nao encontrado: $AppFile"
  exit 1
}

$depsOk = $true
try {
  python -c "import streamlit, pandas, sqlalchemy, psycopg2" 2>$null | Out-Null
} catch {
  $depsOk = $false
}

if (-not $depsOk) {
  Write-Host "Instalando dependencias do Data Viewer..."
  python -m pip install --disable-pip-version-check -r $ReqFile
}

try {
  python -c "import streamlit" 2>$null | Out-Null
} catch {
  Write-Error "Falha ao instalar/carregar Streamlit no Python atual. Verifique o ambiente virtual ativo."
  exit 1
}

Start-Job -ScriptBlock {
  Start-Sleep -Seconds 2
  python -m webbrowser "http://localhost:8501"
} | Out-Null

Write-Host "Iniciando Data Viewer em $Url ..."
python -m streamlit run $AppFile
