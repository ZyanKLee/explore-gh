from datetime import timedelta

import pytest
from builders import NOW, make_commit, make_snapshot

from explore_gh.domain.substance import SubstanceCheck

check = SubstanceCheck()


def signals_of(**overrides):
    return {s.kind: s for s in check.signals(make_snapshot(**overrides))}


def authors(count):
    return tuple(make_commit(author=f"person-{i}") for i in range(count))


def weekly(weeks, author="alice"):
    return tuple(
        make_commit(author=author, committed_at=NOW - timedelta(weeks=week))
        for week in range(weeks)
    )


@pytest.mark.parametrize("count, points", [(2, 5), (4, 5), (5, 8)])
def test_a_team_counts(count, points):
    signal = signals_of(recent_commits=authors(count))["team"]

    assert signal.weight == points
    assert signal.reason == f"{count} aktive Autoren in 90 Tagen"


def test_a_single_author_is_no_team():
    assert "team" not in signals_of(recent_commits=authors(1))


@pytest.mark.parametrize("weeks, points", [(4, 5), (7, 5), (8, 10)])
def test_continuity_counts_weeks_with_commits(weeks, points):
    signal = signals_of(recent_commits=weekly(weeks))["continuity"]

    assert signal.weight == points
    assert signal.reason == f"Commits in {weeks} verschiedenen Wochen"


def test_three_weeks_are_no_continuity():
    assert "continuity" not in signals_of(recent_commits=weekly(3))


def test_a_cut_off_list_of_100_commits_gives_no_continuity():
    many = weekly(10) * 10

    assert "continuity" not in signals_of(recent_commits=many)


def test_issues_of_3_people_show_engagement():
    signal = signals_of(recent_issue_authors=3)["engagement"]

    assert (signal.weight, signal.reason) == (5, "Issues von 3 verschiedenen Personen")
    assert "engagement" not in signals_of(recent_issue_authors=2)


def test_a_repo_of_up_to_30_days_is_a_new_project():
    signal = signals_of(created_at=NOW - timedelta(days=30))["new_project"]

    assert (signal.weight, signal.reason) == (3, "Neues Projekt, 30 Tage alt")
    assert "new_project" not in signals_of(created_at=NOW - timedelta(days=31))


def test_stars_without_echo_cost_40_points():
    signal = signals_of(stars=1100, forks=1, recent_issue_authors=0, pull_requests=0)["no_echo"]

    assert signal.weight == -40
    assert (
        signal.reason == "1.100 Sterne, aber kaum Echo: 1 Forks, 0 Issue-Autoren, 0 Pull Requests"
    )


def test_one_echo_per_100_stars_is_enough():
    assert "no_echo" not in signals_of(stars=300, forks=1, recent_issue_authors=1, pull_requests=1)


def test_many_forks_for_the_stars_make_a_fork_farm():
    signal = signals_of(stars=100, forks=60)["fork_farm"]

    assert signal.weight == -40
    assert signal.reason == "Auffällig viele Forks: 60 bei 100 Sternen"
    assert "fork_farm" not in signals_of(stars=100, forks=59)
