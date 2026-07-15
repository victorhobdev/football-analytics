from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shadow_allocator_is_internal_and_contextual_for_belenenses():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert "SHADOW_ID_START = 3_000_000_000_000" in source
    assert "legacy_dim_team:{legacy_id}:pre_2018" in source
    assert "legacy_dim_team:{legacy_id}:post_2018" in source
    assert "if len(canonical_members) != 1931" in source


def test_shadow_crosswalk_does_not_rewrite_raw_tables():
    source = (ROOT / "platform/scripts/materialize_team_identity_shadow.py").read_text(encoding="utf-8")
    assert "shadow_team_identity_20260715" in source
    assert "update raw." not in source.lower()
    assert "insert into raw." not in source.lower()
