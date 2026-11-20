from datetime import timedelta

import pytest
from builders import NOW, make_commit, make_snapshot, star_history

from explore_gh.domain.model import RepoId, StarHistory


class TestRepoId:
    def test_compares_without_case_like_github(self):
        assert RepoId.parse("Alice/Tiny-Editor") == RepoId.parse("alice/tiny-editor")
        assert len({RepoId.parse("Alice/X"), RepoId.parse("alice/x")}) == 1

    def test_keeps_its_spelling(self):
        assert str(RepoId.parse("Alice/Tiny-Editor")) == "Alice/Tiny-Editor"

    def test_knows_its_url(self):
        assert RepoId.parse("alice/tiny").url == "https://github.com/alice/tiny"

    @pytest.mark.parametrize("text", ["alice", "alice/", "/tiny", "alice/tiny/x", "a b/c"])
    def test_rejects_what_is_no_repo_id(self, text):
        with pytest.raises(ValueError):
            RepoId.parse(text)


class TestStarHistory:
    def test_gained_counts_the_growth_window_of_14_days(self):
        history = StarHistory((100,) + (1,) * 14)

        assert history.gained() == 14
        assert history.gained(30) == 114

    def test_rejects_negative_days(self):
        with pytest.raises(ValueError):
            StarHistory((1, -1))

    def test_continued_books_the_gain_on_the_last_day_and_keeps_its_length(self):
        assert StarHistory((1, 2, 3)).continued(2, 9) == StarHistory((3, 0, 9))

    def test_continued_on_the_same_day_adds_to_today(self):
        assert StarHistory((1, 2, 3)).continued(0, 4) == StarHistory((1, 2, 7))

    def test_a_history_never_collected_stays_empty(self):
        assert StarHistory(()).continued(1, 5) == StarHistory(())

    def test_cannot_go_back_or_lose_stars(self):
        with pytest.raises(ValueError):
            StarHistory((1,)).continued(-1, 0)
        with pytest.raises(ValueError):
            StarHistory((1,)).continued(1, -1)


class TestSnapshot:
    def test_facts_are_as_old_as_the_snapshot_unless_said_otherwise(self):
        assert make_snapshot().facts_at == NOW

    def test_carried_over_takes_the_new_star_count_and_continues_the_history(self):
        old = make_snapshot(stars=100, star_history=StarHistory((0, 0, 5)))
        later = NOW + timedelta(days=1)

        carried = old.carried_over(later, stars=130)

        assert carried.taken_at == later
        assert carried.facts_at == NOW
        assert carried.stars == 130
        assert carried.star_history == StarHistory((0, 5, 30))

    def test_carried_over_counts_lost_stars_as_no_gain(self):
        carried = make_snapshot(stars=100, star_history=StarHistory((0, 5))).carried_over(
            NOW + timedelta(days=1), stars=90
        )

        assert carried.star_history == StarHistory((5, 0))

    def test_with_facts_of_keeps_the_own_history_and_adds_the_gain(self):
        old = make_snapshot(stars=100, star_history=StarHistory((0, 0, 5)))
        fresh = make_snapshot(
            stars=110, taken_at=NOW + timedelta(days=2), star_history=StarHistory(())
        )

        updated = old.with_facts_of(fresh)

        assert updated.taken_at == fresh.taken_at
        assert updated.star_history == StarHistory((5, 0, 10))

    @pytest.mark.parametrize(
        "overrides",
        [{"is_fork": True}, {"is_archived": True}, {"is_mirror": True}, {"primary_language": None}],
    )
    def test_can_never_be_shown_without_code_or_as_fork_archive_or_mirror(self, overrides):
        assert make_snapshot(**overrides).can_never_be_shown

    def test_an_ordinary_repo_can_be_shown(self):
        assert not make_snapshot().can_never_be_shown

    def test_active_authors_are_distinct_people_without_bots(self):
        commits = (
            make_commit(author="alice"),
            make_commit(author="alice"),
            make_commit(author="bob"),
            make_commit(author="dependabot[bot]", is_bot=True),
        )

        assert make_snapshot(recent_commits=commits).active_authors == 2


def test_star_history_builder_puts_all_stars_on_today():
    assert star_history(7).gained(1) == 7
