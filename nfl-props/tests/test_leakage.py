from nflprops import leakage


def test_no_leakage_current_features():
    assert leakage.run(cutoffs=("2021-10-17",))


def test_leakage_test_catches_v1_lookahead():
    # v1 used closing spread/total, observed weather and the actual starting QB: the scramble must catch it
    assert not leakage.run(cutoffs=("2021-10-17",), legacy=True)
