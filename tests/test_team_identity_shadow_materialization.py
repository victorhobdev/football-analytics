from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shadow_allocator_is_internal_and_contextual_for_belenenses():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert "SHADOW_ID_START = 3_000_000_000_000" in source
    assert "legacy_dim_team:{legacy_id}:pre_2018" in source
    assert "legacy_dim_team:{legacy_id}:post_2018" in source
    assert "if len(canonical_members) != 1930" in source


def test_shadow_crosswalk_does_not_rewrite_raw_tables():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert "shadow_team_identity_20260715" in source
    assert "update raw." not in source.lower()
    assert "insert into raw." not in source.lower()


def test_shadow_rebuild_prunes_canonical_components_removed_by_new_merges():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert "delete from {SCHEMA}.canonical_team where not (canonical_key = any(%s))" in source


def test_belenenses_split_manifest_uses_the_pre_2018_cutoff():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert 'period == "pre_2018"' in source
    assert "period == \"pre_2018\'\"" not in source
