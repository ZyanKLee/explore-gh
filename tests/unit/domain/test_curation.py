from datetime import date, timedelta

import pytest

from explore_gh.domain.curation import check_section, check_unique, in_cooldown, varied

DAY = date(2026, 11, 12)


@pytest.mark.parametrize("days_before, blocked", [(0, True), (29, True), (30, False), (-29, True)])
def test_cooldown_blocks_a_repo_for_30_days(days_before, blocked):
    assert in_cooldown(DAY - timedelta(days=days_before), DAY) is blocked


def pick(items):
    """items are (language, owner) pairs."""
    return varied(items, language_of=lambda i: i[0], owner_of=lambda i: i[1])


def test_varied_takes_at_most_4_of_a_language():
    items = [("Rust", f"o{i}") for i in range(6)] + [("Go", "x")]

    assert pick(items) == items[:4] + [("Go", "x")]


def test_varied_takes_at_most_2_of_an_owner():
    items = [("Rust", "alice"), ("Go", "alice"), ("C", "alice"), ("C", "bob")]

    assert pick(items) == [("Rust", "alice"), ("Go", "alice"), ("C", "bob")]


def test_repos_without_language_form_a_group_of_their_own():
    items = [(None, f"o{i}") for i in range(5)]

    assert len(pick(items)) == 4


def test_varied_stops_at_20_and_never_fills_up():
    items = [(f"L{i % 10}", f"o{i}") for i in range(30)]

    assert len(pick(items)) == 20
    assert pick(items[:3]) == items[:3]


def test_check_section_refuses_more_than_20():
    with pytest.raises(ValueError, match="mehr als 20"):
        check_section(range(21), lambda i: str(i), lambda i: i, "Test")


def test_check_section_refuses_a_fifth_of_a_language():
    with pytest.raises(ValueError, match="Sprache"):
        check_section(range(5), lambda i: "Rust", lambda i: i, "Test")


def test_check_section_refuses_a_third_of_an_owner():
    with pytest.raises(ValueError, match="Besitzers"):
        check_section(range(3), lambda i: str(i), lambda i: "alice", "Test")


def test_check_unique_refuses_duplicates():
    check_unique(["a", "b"], "Test")
    with pytest.raises(ValueError, match="mehrfach"):
        check_unique(["a", "a"], "Test")
