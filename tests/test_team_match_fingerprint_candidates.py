from build_team_match_fingerprint_candidates import normalize_name, opponent_match


def test_normalize_known_provider_variants():
    assert normalize_name("América Mineiro") == normalize_name("America-MG")


def test_opponent_match_requires_same_contextual_name():
    assert opponent_match("América Mineiro", "America-MG")
    assert not opponent_match("Palmeiras", "Vasco")
