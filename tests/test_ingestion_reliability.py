from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
DAGS_DIR = ROOT / "infra" / "airflow" / "dags"
sys.path.insert(0, str(DAGS_DIR))


def _install_airflow_import_stub() -> None:
    airflow = ModuleType("airflow")
    operators = ModuleType("airflow.operators")
    python_operator = ModuleType("airflow.operators.python")
    python_operator.get_current_context = lambda: {}
    airflow.operators = operators
    operators.python = python_operator
    sys.modules.setdefault("airflow", airflow)
    sys.modules.setdefault("airflow.operators", operators)
    sys.modules.setdefault("airflow.operators.python", python_operator)


def _install_runtime_import_stubs() -> None:
    boto3 = ModuleType("boto3")
    boto3.client = lambda *args, **kwargs: None
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.create_engine = lambda *args, **kwargs: None
    sqlalchemy.text = lambda statement: statement
    sys.modules.setdefault("boto3", boto3)
    sys.modules.setdefault("sqlalchemy", sqlalchemy)


_install_airflow_import_stub()
_install_runtime_import_stubs()

from common.services import ingestion_service


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Connection:
    def __init__(self, engine):
        self.engine = engine

    def execute(self, statement, params):
        sql = str(statement).lstrip().upper()
        if sql.startswith("SELECT"):
            if self.engine.fail_on_read:
                raise RuntimeError("sync state read unavailable")
            cursor = None if self.engine.state is None else self.engine.state["cursor"]
            return _Result(None if cursor is None else (cursor,))
        if self.engine.fail_on_write:
            raise RuntimeError("sync state write unavailable")
        self.engine.state = {
            "cursor": params["cursor"],
            "status": params["status"],
        }
        return _Result(None)


class _Transaction:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return _Connection(self.engine)

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def __init__(self, *, state=None, fail_on_read=False, fail_on_write=False):
        self.state = state
        self.fail_on_read = fail_on_read
        self.fail_on_write = fail_on_write

    def begin(self):
        return _Transaction(self)


class _S3:
    def __init__(self, keys=None):
        self.keys = list(keys or [])
        self.uploads = []

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys, **kwargs):
        return {
            "Contents": [{"Key": key} for key in self.keys if key.startswith(Prefix)],
            "IsTruncated": False,
        }

    def upload_fileobj(self, fileobj, bucket, key):
        self.uploads.append(key)
        self.keys.append(key)


class _Provider:
    name = "test-provider"


def _run_entity(*, engine, s3, fetch_fn, target_ids=(1, 2), fail_on_partial=True):
    return ingestion_service._ingest_entity_by_numeric_ids(
        context={"dag_id": "test", "task_id": "ingest", "run_id": "test-run"},
        provider_name="test-provider",
        provider=_Provider(),
        engine=engine,
        s3_client=s3,
        league_id=1,
        season=2024,
        entity_type="test_entity",
        endpoint="test/entity",
        target_ids=list(target_ids),
        key_prefix="test_entity/league=1/season=2024",
        id_name="item_id",
        fetch_fn=fetch_fn,
        source_params_fn=lambda item_id: {"item_id": item_id},
        scope_key="league=1/season=2024/entity=test_entity",
        fail_on_partial=fail_on_partial,
        max_consecutive_failures=5,
    )


def test_checkpoint_write_failure_fails_the_ingestion_task():
    engine = _Engine(fail_on_write=True)
    s3 = _S3()

    with pytest.raises(RuntimeError, match="sync state write unavailable"):
        _run_entity(
            engine=engine,
            s3=s3,
            fetch_fn=lambda item_id: ({"response": [{"id": item_id}]}, {}),
            target_ids=(1,),
        )


def test_second_execution_uses_bronze_when_cursor_is_missing():
    engine = _Engine()
    s3 = _S3()
    fetch = Mock(side_effect=lambda item_id: ({"response": [{"id": item_id}]}, {}))

    _run_entity(engine=engine, s3=s3, fetch_fn=fetch, target_ids=(1,))
    first_upload_count = len(s3.uploads)
    engine.state = None

    _run_entity(engine=engine, s3=s3, fetch_fn=fetch, target_ids=(1,))

    assert fetch.call_count == 1
    assert len(s3.uploads) == first_upload_count


def test_partial_run_is_logged_as_partial_and_retry_reprocesses_only_pending_ids():
    engine = _Engine()
    s3 = _S3()
    calls = []

    def first_attempt(item_id):
        calls.append(item_id)
        if item_id == 2:
            raise RuntimeError("temporary provider failure")
        return {"response": [{"id": item_id}]}, {}

    with patch.object(ingestion_service, "log_event") as log_event:
        with pytest.raises(RuntimeError, match="parcial"):
            _run_entity(engine=engine, s3=s3, fetch_fn=first_attempt)

        summary = [call.kwargs for call in log_event.call_args_list if call.kwargs.get("step") == "summary"]
        assert summary[-1]["status"] == "partial"

    def retry_attempt(item_id):
        calls.append(item_id)
        return {"response": [{"id": item_id}]}, {}

    _run_entity(engine=engine, s3=s3, fetch_fn=retry_attempt)

    assert calls == [1, 2, 2]
    assert engine.state == {"cursor": "2", "status": "success"}


def test_raw_ingestion_dags_serialize_same_scope_runs():
    dag_files = sorted(DAGS_DIR.glob("ingest_*_bronze.py"))
    assert dag_files
    assert all("max_active_runs=1" in path.read_text(encoding="utf-8") for path in dag_files)


def test_provider_control_keys_are_scoped():
    migration = (ROOT / "db" / "migrations" / "20260218190000_provider_foundation.sql").read_text(
        encoding="utf-8"
    )

    assert "PRIMARY KEY (provider, entity_type, source_id)" in migration
    assert "PRIMARY KEY (provider, entity_type, scope_key)" in migration
