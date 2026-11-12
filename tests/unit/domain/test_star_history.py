import pytest

from github_anti_ai.domain.model import GROWTH_WINDOW_DAYS, StarHistory


def test_stars_gained_are_those_of_the_growth_window_by_default():
    history = StarHistory(daily=(100, 1, 2, 3, 4, 5, 6, 7))

    assert GROWTH_WINDOW_DAYS == 7
    assert history.gained() == 28


def test_stars_gained_can_be_asked_for_any_number_of_recent_days():
    history = StarHistory(daily=(100, 1, 2, 3, 4, 5, 6, 7))

    assert history.gained(2) == 13
    assert history.gained(8) == 128


def test_history_shorter_than_the_window_counts_what_is_there():
    assert StarHistory(daily=(4, 5)).gained() == 9
    assert StarHistory(daily=()).gained() == 0


def test_star_history_cannot_contain_negative_days():
    with pytest.raises(ValueError):
        StarHistory(daily=(3, -1, 2))
