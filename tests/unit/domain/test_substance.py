from datetime import timedelta

from builders import NOW, make_commit, make_snapshot
from github_anti_ai.domain.substance import SubstanceCheck


def signal(kind, **overrides):
    found = [s for s in SubstanceCheck().signals(make_snapshot(**overrides)) if s.kind == kind]
    assert len(found) <= 1
    return found[0] if found else None


def weight(kind, **overrides):
    found = signal(kind, **overrides)
    return found.weight if found else 0


def commits_by(*authors):
    return tuple(make_commit(author=author) for author in authors)


def commits_in_weeks(weeks, per_week=1, **commit_fields):
    return tuple(
        make_commit(committed_at=NOW - timedelta(weeks=week, hours=commit), **commit_fields)
        for week in range(weeks)
        for commit in range(per_week)
    )


def test_a_single_author_is_no_team():
    assert signal("team", recent_commits=commits_by("alice", "alice")) is None


def test_several_active_authors_count_as_a_team():
    team = signal("team", recent_commits=commits_by("alice", "bob"))

    assert team.weight > 0
    assert "2" in team.reason


def test_a_larger_team_counts_more():
    small = weight("team", recent_commits=commits_by("alice", "bob"))
    large = weight("team", recent_commits=commits_by("alice", "bob", "carol", "dave", "erin"))

    assert large > small


def test_work_spread_over_many_weeks_shows_continuity():
    steady = signal("continuity", recent_commits=commits_in_weeks(8))

    assert steady.weight > 0
    assert "8" in steady.reason


def test_longer_continuity_counts_more():
    some = weight("continuity", recent_commits=commits_in_weeks(4))
    much = weight("continuity", recent_commits=commits_in_weeks(8))

    assert much > some > 0


def test_a_burst_of_commits_within_a_few_weeks_is_no_continuity():
    assert signal("continuity", recent_commits=commits_in_weeks(3, per_week=20)) is None


def test_bots_do_not_show_continuity():
    bot_commits = commits_in_weeks(10, author="dependabot[bot]", is_bot=True)

    assert signal("continuity", recent_commits=bot_commits) is None


def test_continuity_is_unknown_when_the_commit_list_is_cut_off():
    # only the latest 100 commits are known, they may cover just a few days
    assert signal("continuity", recent_commits=commits_in_weeks(10, per_week=10)) is None


def test_issues_by_several_people_show_engagement():
    assert weight("engagement", recent_issue_authors=3) > 0
    assert signal("engagement", recent_issue_authors=2) is None


def test_a_young_repo_gets_a_small_bonus():
    young = weight("new_project", created_at=NOW - timedelta(days=30))
    old = signal("new_project", created_at=NOW - timedelta(days=31))

    assert young > 0
    assert old is None


def test_the_bonus_for_young_repos_is_smaller_than_any_other_merit():
    young = weight("new_project", created_at=NOW - timedelta(days=3))

    assert young < weight("team", recent_commits=commits_by("alice", "bob"))
    assert young < weight("continuity", recent_commits=commits_in_weeks(4))
    assert young < weight("engagement", recent_issue_authors=3)


def test_stars_without_any_echo_are_suspicious():
    silent = signal("no_echo", forks=0, recent_issue_authors=0, pull_requests=0)

    assert silent.weight < 0


def test_a_fork_issue_or_pull_request_is_an_echo_for_a_small_repo():
    assert signal("no_echo", stars=80, forks=1, recent_issue_authors=0, pull_requests=0) is None
    assert signal("no_echo", stars=80, forks=0, recent_issue_authors=1, pull_requests=0) is None
    assert signal("no_echo", stars=80, forks=0, recent_issue_authors=0, pull_requests=1) is None


def test_a_single_fork_among_a_thousand_stars_is_no_echo():
    # seen live: lure repos with 1100 stars and exactly one fork or issue
    lure = signal("no_echo", stars=1104, forks=1, recent_issue_authors=0, pull_requests=0)

    assert lure.weight < 0


def test_echo_is_measured_against_the_number_of_stars():
    # the threshold is one fork, issue author or pull request per 100 stars
    enough = dict(stars=1000, forks=6, recent_issue_authors=3, pull_requests=1)
    too_little = dict(stars=1000, forks=6, recent_issue_authors=3, pull_requests=0)

    assert signal("no_echo", **enough) is None
    assert signal("no_echo", **too_little).weight < 0


def test_almost_as_many_forks_as_stars_are_suspicious():
    assert signal("fork_farm", stars=119, forks=119).weight < 0
    assert signal("fork_farm", stars=100, forks=60).weight < 0


def test_a_popular_repo_with_many_forks_is_not_a_fork_farm():
    assert signal("fork_farm", stars=6849, forks=2524) is None
