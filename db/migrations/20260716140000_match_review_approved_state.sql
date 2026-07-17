-- migrate:up

ALTER TABLE control.brasileirao_fixture_xref
  DROP CONSTRAINT chk_brasileirao_fixture_xref_review_status,
  ADD CONSTRAINT chk_brasileirao_fixture_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'approved', 'manual_review', 'blocked', 'rejected'));

ALTER TABLE control.tm_game_fixture_xref
  DROP CONSTRAINT chk_tm_game_fixture_xref_review_status,
  ADD CONSTRAINT chk_tm_game_fixture_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'approved', 'manual_review', 'blocked', 'rejected'));

ALTER TABLE control.elo_match_xref
  DROP CONSTRAINT chk_elo_match_xref_review_status,
  ADD CONSTRAINT chk_elo_match_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'approved', 'manual_review', 'blocked', 'rejected'));

-- migrate:down

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM control.brasileirao_fixture_xref WHERE review_status = 'approved'
    UNION ALL
    SELECT 1 FROM control.tm_game_fixture_xref WHERE review_status = 'approved'
    UNION ALL
    SELECT 1 FROM control.elo_match_xref WHERE review_status = 'approved'
  ) THEN
    RAISE EXCEPTION 'cannot remove approved review state while approved decisions exist';
  END IF;
END $$;

ALTER TABLE control.brasileirao_fixture_xref
  DROP CONSTRAINT chk_brasileirao_fixture_xref_review_status,
  ADD CONSTRAINT chk_brasileirao_fixture_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));

ALTER TABLE control.tm_game_fixture_xref
  DROP CONSTRAINT chk_tm_game_fixture_xref_review_status,
  ADD CONSTRAINT chk_tm_game_fixture_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));

ALTER TABLE control.elo_match_xref
  DROP CONSTRAINT chk_elo_match_xref_review_status,
  ADD CONSTRAINT chk_elo_match_xref_review_status
    CHECK (review_status IN ('pending', 'auto_approved', 'manual_review', 'blocked', 'rejected'));
