# Backup and restore runbook

This runbook covers the local Compose stack and the minimum production checklist. Replace placeholder paths and bucket names with the real environment values before use.

## Scope

Persisted state:
- Postgres warehouse and serving schemas in the `postgres_data` volume.
- MinIO object data in the `minio_data` volume.
- Metabase local application data in the `metabase_data` volume.

Minimum target:
- Daily Postgres logical dump.
- Daily MinIO object mirror.
- Daily Metabase data backup.
- Monthly restore test in an isolated environment.

## Postgres backup

Local Compose:

```bash
mkdir -p artifacts/backups/postgres
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > artifacts/backups/postgres/football_$(date +%Y%m%d_%H%M%S).dump
```

Production:
- Store dumps outside the application host when possible.
- Encrypt at rest.
- Keep retention explicit, for example 7 daily, 4 weekly, 6 monthly.
- Monitor backup job success and dump size drift.

## Postgres restore test

Use an isolated database, never the live target:

```bash
createdb football_restore_test
pg_restore -d football_restore_test artifacts/backups/postgres/football_YYYYMMDD_HHMMSS.dump
psql -d football_restore_test -c "select count(*) from information_schema.tables;"
```

Pass condition:
- Restore exits successfully.
- Core marts and public API tables exist.
- BFF smoke tests can point to the restored DSN.

## MinIO backup

Use `mc mirror` from a machine that can reach the MinIO endpoint:

```bash
mkdir -p artifacts/backups/minio
mc alias set football "$MINIO_ENDPOINT_URL" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
mc mirror --overwrite football/football-bronze artifacts/backups/minio/football-bronze
mc mirror --overwrite football/football-silver artifacts/backups/minio/football-silver
```

Production:
- Mirror to a separate storage account or bucket.
- Enable bucket/object retention if available.
- Keep provider API raw payloads immutable once published.

## MinIO restore test

Use isolated buckets:

```bash
mc mb football/restore-test-bronze
mc mirror --overwrite artifacts/backups/minio/football-bronze football/restore-test-bronze
mc ls football/restore-test-bronze
```

Pass condition:
- Mirror exits successfully.
- Expected partitions and sample objects are readable.

## Metabase backup

The local stack stores Metabase data in the `metabase_data` volume. Stop Metabase before copying the file to avoid a partial H2 snapshot:

```bash
docker compose stop metabase
docker run --rm -v football-analytics_metabase_data:/source -v "$PWD/artifacts/backups/metabase:/backup" alpine sh -c "cp -a /source/. /backup/"
docker compose start metabase
```

Production should prefer a real external database for Metabase instead of H2. Back up that database with the same retention discipline as Postgres.

## Restore validation checklist

Run after every restore test:

```bash
docker compose ps
curl -f http://127.0.0.1:8000/health
docker compose logs --tail=100 airflow-scheduler
```

Application checks:
- Home API responds.
- Competition hub API responds for a known competition.
- Search API returns expected known entities.
- Airflow webserver starts and DAG list is visible through the private local/admin path.
- Metabase starts from the restored data.

## Production edge checklist

Document these values per deployment:
- Public frontend domain.
- Public BFF domain.
- TLS terminator.
- Reverse proxy or edge rate limit policy.
- SSH access policy.
- Backup storage location.
- Restore owner.
- RPO and RTO targets.

Do not expose Postgres, MinIO, Airflow or Metabase directly to the public internet. The local Compose file binds their host ports to `127.0.0.1` only; production should keep them on private networks or behind a controlled admin path.
