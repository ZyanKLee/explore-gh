"""Carrying a Snapshot over to the next day instead of fetching it again."""

from datetime import timedelta

import pytest

from builders import NOW, make_snapshot
from github_anti_ai.domain.model import STAR_HISTORY_DAYS, Candidate, RepoId, StarHistory

YESTERDAY = NOW - timedelta(days=1)


def history(*last_days):
    """A full history that ends with the given days."""
    return StarHistory(daily=(0,) * (STAR_HISTORY_DAYS - len(last_days)) + last_days)


def test_candidate_carries_the_star_count_its_source_saw():
    candidate = Candidate(RepoId.parse("alice/tiny-editor"), stars=812)

    assert candidate.repo == RepoId.parse("Alice/Tiny-Editor")
    assert candidate.stars == 812


def test_candidate_of_a_source_without_star_counts_has_none():
    assert Candidate(RepoId.parse("alice/tiny-editor")).stars is None


def test_star_history_continued_by_a_day_appends_the_gain_and_drops_the_oldest_day():
    continued = history(7, 8, 9).continued(days_passed=1, gained=5)

    assert continued == history(7, 8, 9, 5)
    assert len(continued.daily) == STAR_HISTORY_DAYS


def test_days_without_a_snapshot_count_as_days_without_new_stars():
    # the gain of the whole gap is booked on the last day, the window of 7 days stays right
    assert history(7, 8, 9).continued(days_passed=3, gained=5) == history(7, 8, 9, 0, 0, 5)


def test_star_history_continued_on_the_same_day_adds_to_today():
    assert history(7, 8, 9).continued(days_passed=0, gained=5) == history(7, 8, 14)


def test_star_history_continued_past_its_length_keeps_only_the_gain():
    continued = history(7, 8, 9).continued(days_passed=STAR_HISTORY_DAYS + 5, gained=5)

    assert continued == history(5)


def test_star_history_that_was_never_collected_stays_empty():
    assert StarHistory(daily=()).continued(days_passed=1, gained=5) == StarHistory(daily=())


def test_star_history_cannot_be_continued_with_a_loss():
    with pytest.raises(ValueError):
        history(7).continued(days_passed=1, gained=-1)


def test_facts_of_a_fresh_snapshot_are_as_old_as_the_snapshot():
    assert make_snapshot(taken_at=NOW).facts_at == NOW


def test_snapshot_carried_over_takes_todays_star_count_and_keeps_the_facts():
    old = make_snapshot(taken_at=YESTERDAY, stars=812, star_history=history(7, 8, 9))

    carried = old.carried_over(NOW, stars=900)

    assert carried.taken_at == NOW
    assert carried.facts_at == YESTERDAY
    assert carried.stars == 900
    assert carried.star_history == history(7, 8, 9, 88)
    assert (carried.repo, carried.readme, carried.forks) == (old.repo, old.readme, old.forks)


def test_snapshot_carried_over_twice_still_knows_the_age_of_its_facts():
    old = make_snapshot(taken_at=YESTERDAY - timedelta(days=1), stars=800)

    carried = old.carried_over(YESTERDAY, stars=812).carried_over(NOW, stars=900)

    assert carried.facts_at == YESTERDAY - timedelta(days=1)


def test_stars_lost_since_the_last_snapshot_count_as_no_gain():
    old = make_snapshot(taken_at=YESTERDAY, stars=812, star_history=history(7, 8, 9))

    carried = old.carried_over(NOW, stars=800)

    assert carried.stars == 800
    assert carried.star_history == history(7, 8, 9, 0)
