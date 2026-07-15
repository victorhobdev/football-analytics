# Wave 2 pipeline reliability — TDD evidence

## Source and journeys

The guarantees were derived from the Wave 2 execution request.

- A persistent checkpoint failure must fail the ingestion task.
- A second execution must not duplicate an artifact when the cursor is absent.
- A partial run must expose partial state and retry only pending IDs.
- Raw ingestion DAGs must not overlap runs of the same DAG.
- Provider control keys must remain provider-scoped.

## RED

Command: `python -m pytest tests/test_ingestion_reliability.py -q`

Result before production changes: `4 failed, 1 passed`. The failures covered swallowed checkpoint writes, duplicate work without a cursor, partial state logged as success, and missing DAG run serialization. Checkpoint commit: `93adec0`.

## GREEN

Command: `python -m pytest tests/test_ingestion_reliability.py -q`

Result after production changes: `5 passed`.

Adjacent operational suite: `8 passed` for `tests/test_http_client.py` and `tests/test_ingestion_reliability.py`. Python compilation of `infra/airflow/dags` completed without errors.

## Guarantees

| Guarantee | Test | Result |
|---|---|---|
| Checkpoint persistence errors fail the task | `test_checkpoint_write_failure_fails_the_ingestion_task` | PASS |
| Bronze artifacts prevent duplicate work when a cursor row is absent | `test_second_execution_uses_bronze_when_cursor_is_missing` | PASS |
| Partial state is logged accurately and retry resumes from the pending ID | `test_partial_run_is_logged_as_partial_and_retry_reprocesses_only_pending_ids` | PASS |
| Raw ingestion DAGs serialize overlapping runs | `test_raw_ingestion_dags_serialize_same_scope_runs` | PASS |
| Provider control tables use provider-scoped primary keys | `test_provider_control_keys_are_scoped` | PASS |

## Coverage and limits

The tests execute the shared ingestion worker with deterministic in-memory fakes; no external API, object store, Postgres, or Airflow service is required. Full Airflow integration was not run locally because Airflow is not installed in this environment. Existing `datetime.utcnow()` warnings are unchanged.

Schema review confirmed provider-scoped primary keys in `raw.provider_entity_map` and `raw.provider_sync_state`. No schema migration was added because the repository contains no persisted evidence of a dual-provider ID collision in the current load. The canonical `raw.fixtures` key remains a residual model-level risk if dual-provider fixture loading becomes active.
