from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "platform" / "scripts" / "build_external_match_publication_xref.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))


def _load_publication_builder():
    spec = importlib.util.spec_from_file_location("publication_builder", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pending_external_coverage_never_becomes_publishable():
    builder = _load_publication_builder()

    assert builder.is_publishable_new_coverage(
        identity_status="new_coverage",
        review_status="auto_approved",
        publication_status="publishable",
    )
    for review_status in ("pending", "manual_review", "blocked", "rejected"):
        assert not builder.is_publishable_new_coverage(
            identity_status="new_coverage",
            review_status=review_status,
            publication_status="publishable",
        )


def test_external_staging_requires_the_reconciliation_decision():
    for relative_path in (
        "platform/dbt/models/staging/stg_elo_matches.sql",
        "platform/dbt/models/staging/stg_tm_match_identity.sql",
    ):
        sql = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "review_status = 'auto_approved'" in sql


def test_statsbomb_linked_teams_use_the_approved_local_team_id():
    for relative_path in (
        "platform/dbt/models/staging/stg_matches.sql",
        "platform/dbt/models/staging/stg_fixture_lineups.sql",
    ):
        sql = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "stg_statsbomb_team_identity" in sql
        assert "identity_status = 'linked_to_sportmonks'" in sql
        assert "local_team_id" in sql


def test_external_match_staging_has_no_name_hash_team_identity_fallback():
    sql = (ROOT / "platform/dbt/models/staging/stg_external_matches.sql").read_text(encoding="utf-8")
    assert "raw.provider_entity_map" in sql
    assert "source_team_key" in sql
    assert "960200000000" not in sql


def test_canonical_team_registry_allocates_internal_ids_without_name_uniqueness():
    sql = (ROOT / "db/migrations/20260715120000_team_identity_registry.sql").read_text(encoding="utf-8")
    assert "control.team_identity" in sql
    assert "nextval('control.team_identity_id_seq')" in sql
    assert "merged_into_team_id" in sql
    assert "UNIQUE (team_name)" not in sql.upper()
