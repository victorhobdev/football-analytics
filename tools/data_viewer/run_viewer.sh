#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
APP_FILE="$SCRIPT_DIR/app.py"
URL="http://localhost:8501"

if [[ -z "${FOOTBALL_PG_DSN:-}" ]]; then
  echo "Erro: variavel FOOTBALL_PG_DSN nao definida."
  echo "Exemplo:"
  echo "  export FOOTBALL_PG_DSN='postgresql+psycopg2://user:pass@localhost:5432/football_dw'"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erro: python3 nao encontrado no PATH. Instale Python 3.10+."
  exit 1
fi

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Erro: arquivo de dependencias nao encontrado: $REQ_FILE"
  exit 1
fi

if [[ ! -f "$APP_FILE" ]]; then
  echo "Erro: arquivo da app nao encontrado: $APP_FILE"
  exit 1
fi

if ! python3 -c "import streamlit, pandas, sqlalchemy, psycopg2" >/dev/null 2>&1; then
  echo "Instalando dependencias do Data Viewer..."
  python3 -m pip install --disable-pip-version-check -r "$REQ_FILE"
fi

if ! python3 -c "import streamlit" >/dev/null 2>&1; then
  echo "Erro: falha ao instalar/carregar Streamlit no Python atual."
  exit 1
fi

(
  sleep 2
  python3 -m webbrowser "$URL" >/dev/null 2>&1 || true
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
) &

echo "Iniciando Data Viewer em $URL ..."
exec python3 -m streamlit run "$APP_FILE"
