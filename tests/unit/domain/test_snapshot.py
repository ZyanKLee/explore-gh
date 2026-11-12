import pytest

from builders import make_commit, make_snapshot


def test_active_authors_are_the_distinct_people_behind_the_recent_commits():
    snapshot = make_snapshot(
        recent_commits=(
            make_commit(author="alice"),
            make_commit(author="bob"),
            make_commit(author="alice"),
        )
    )

    assert snapshot.active_authors == 2


def test_bots_are_not_active_authors():
    snapshot = make_snapshot(
        recent_commits=(
            make_commit(author="alice"),
            make_commit(author="dependabot[bot]", is_bot=True),
        )
    )

    assert snapshot.active_authors == 1


def test_co_authors_are_not_counted_as_active_authors():
    snapshot = make_snapshot(
        recent_commits=(make_commit(author="alice", co_authors=("Claude <noreply@anthropic.com>",)),)
    )

    assert snapshot.active_authors == 1


def test_repo_without_recent_commits_has_no_active_authors():
    assert make_snapshot(recent_commits=()).active_authors == 0


def test_ordinary_repo_can_be_shown():
    assert not make_snapshot().can_never_be_shown


@pytest.mark.parametrize(
    "facts",
    [{"is_fork": True}, {"is_archived": True}, {"is_mirror": True}, {"primary_language": None}],
)
def test_forks_archived_repos_mirrors_and_repos_without_code_can_never_be_shown(facts):
    assert make_snapshot(**facts).can_never_be_shown
