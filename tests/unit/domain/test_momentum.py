import pytest
from builders import make_snapshot, star_history

from github_anti_ai.domain.momentum import MomentumCalculator

calculator = MomentumCalculator()


@pytest.mark.parametrize(
    "gained, stars, points",
    [
        (100, 100, 40.0),  # new repo
        (1000, 1000, 60.0),  # new repo, much attention
        (500, 5000, 35.5),  # medium repo on the rise
        (389, 91_943, 27.6),  # astral-sh/uv
        (1094, 255_489, 32.4),  # torvalds/linux
    ],
)
def test_momentum_mixes_absolute_and_relative_growth(gained, stars, points):
    signal = calculator.signal(make_snapshot(stars=stars, star_history=star_history(gained)))

    assert signal.kind == "momentum"
    assert signal.weight == pytest.approx(points, abs=0.05)


def test_the_reason_names_gain_window_and_size():
    signal = calculator.signal(make_snapshot(stars=91_943, star_history=star_history(389)))

    assert signal.reason == "+389 Sterne in 14 Tagen bei 91.943 insgesamt"


def test_no_gain_gives_no_points():
    assert calculator.signal(make_snapshot(star_history=star_history(0))).weight == 0


def test_more_gain_than_stars_counts_as_all_new():
    signal = calculator.signal(make_snapshot(stars=90, star_history=star_history(100)))

    assert signal.weight == pytest.approx(40.0)
