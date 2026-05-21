#!/usr/bin/env bash
set -euo pipefail

read_secret() {
  local name="$1"
  local path="/run/secrets/${name}"

  if [[ ! -f "${path}" ]]; then
    printf ''
    return 0
  fi

  cat "${path}"
}

required_secret() {
  local name="$1"
  local value
  value="$(read_secret "${name}")"

  if [[ -z "${value}" ]]; then
    echo "Required secret '${name}' is empty or missing." >&2
    exit 1
  fi

  printf '%s' "${value}"
}

postgres_password="$(required_secret postgres_password)"

export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="$(required_secret airflow_database_sql_alchemy_conn)"
export AIRFLOW__CORE__FERNET_KEY="$(required_secret airflow_fernet_key)"
export AIRFLOW__WEBSERVER__SECRET_KEY="$(required_secret airflow_webserver_secret_key)"
export AIRFLOW_ADMIN_PASSWORD="$(read_secret airflow_admin_password)"
export APIFOOTBALL_API_KEY="$(read_secret apifootball_api_key)"
export API_KEY_SPORTMONKS="$(read_secret sportmonks_api_key)"
export MINIO_ACCESS_KEY="$(required_secret minio_access_key)"
export MINIO_SECRET_KEY="$(required_secret minio_secret_key)"
export FOOTBALL_PG_DSN="postgresql://${POSTGRES_USER}:${postgres_password}@postgres:5432/${POSTGRES_DB}"

exec "$@"
