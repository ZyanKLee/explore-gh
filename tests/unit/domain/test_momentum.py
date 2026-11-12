import pytest

from builders import make_snapshot, star_history
from github_anti_ai.domain.momentum import MomentumCalculator


def momentum(gained, stars):
    return MomentumCalculator().signal(make_snapshot(stars=stars, star_history=star_history(gained)))


def points(gained, stars):
    return momentum(gained, stars).weight


def test_momentum_is_a_positive_signal_that_names_gain_and_size():
    signal = momentum(gained=389, stars=91943)

    assert signal.kind == "momentum"
    assert signal.weight > 0
    assert "389" in signal.reason
    assert "91.943" in signal.reason


def test_more_stars_gained_mean_more_momentum():
    assert points(gained=500, stars=5000) > points(gained=100, stars=5000)


def test_the_same_gain_counts_more_for_a_smaller_repo():
    assert points(gained=500, stars=1000) > points(gained=500, stars=50000)


def test_a_new_repo_outranks_a_giant_with_several_times_its_gain():
    assert points(gained=300, stars=300) > points(gained=1094, stars=255489)


@pytest.mark.parametrize(
    ("gained", "stars", "expected"),
    [(100, 100, 40.0), (1000, 1000, 60.0), (500, 5000, 35.5), (389, 91943, 27.6)],
)
def test_momentum_follows_the_formula_of_the_concept(gained, stars, expected):
    assert points(gained, stars) == pytest.approx(expected, abs=0.05)


def test_repo_without_new_stars_has_no_momentum():
    assert points(gained=0, stars=5000) == 0


def test_more_stars_gained_than_left_does_not_break_the_calculation():
    # people can remove their star again
    assert points(gained=120, stars=100) == points(gained=120, stars=120)
