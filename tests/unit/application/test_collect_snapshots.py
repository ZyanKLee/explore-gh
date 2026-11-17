from datetime import timedelta

import pytest
from builders import NOW, TODAY, FixedClock, make_snapshot, star_history
from fakes import FakeCandidateSource, FakeRepoSource, InMemorySnapshotStore, InMemoryStatusStore

from github_anti_ai.application.collect_snapshots import CollectSnapshots
from github_anti_ai.application.ports import CollectionStatus
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.model import StarHistory

YESTERDAY = TODAY - timedelta(days=1)


def collect(*sources, repo_source, store=None, status=None, assess=None, limit=None):
    store = store if store is not None else InMemorySnapshotStore()
    status = status if status is not None else InMemoryStatusStore()
    report = CollectSnapshots(
        candidate_sources=sources,
        repo_source=repo_source,
        snapshot_store=store,
        status_store=status,
        clock=FixedClock(),
        assess=assess,
        limit=limit,
    ).run()
    return report, store, status


def names(snapshots):
    return sorted(str(snapshot.repo) for snapshot in snapshots)


def old_snapshot(repo, days_ago=1, stars=100, **overrides):
    overrides.setdefault("star_history", StarHistory((0, 0, 5)))
    return make_snapshot(repo, taken_at=NOW - timedelta(days=days_ago), stars=stars, **overrides)


class TestFirstRun:
    def test_saves_a_snapshot_of_each_candidate_under_today(self):
        github = FakeRepoSource(make_snapshot("a/x"), make_snapshot("b/y"))

        report, store, _ = collect(FakeCandidateSource("a/x", "b/y"), repo_source=github)

        assert names(store.load(TODAY)) == ["a/x", "b/y"]
        assert (report.discovered, report.collected, report.fetched) == (2, 2, 2)
        assert github.calls == [(["a/x", "b/y"], True)]

    def test_merges_the_sources_and_fetches_each_repo_once(self):
        github = FakeRepoSource(make_snapshot("a/x"), make_snapshot("b/y"))

        report, _, _ = collect(
            FakeCandidateSource("a/x"), FakeCandidateSource("A/X", "b/y"), repo_source=github
        )

        assert report.discovered == 2
        assert github.fetched == ["a/x", "b/y"]

    def test_a_failing_source_is_reported_and_the_others_are_used(self):
        report, store, _ = collect(
            FakeCandidateSource(name="kaputt", unavailable=True),
            FakeCandidateSource("a/x"),
            repo_source=FakeRepoSource(make_snapshot("a/x")),
        )

        assert report.source_errors == ("kaputt: Suche nicht erreichbar",)
        assert names(store.load(TODAY)) == ["a/x"]

    def test_the_limit_caps_the_candidates(self):
        github = FakeRepoSource(*(make_snapshot(f"o{i}/r") for i in range(5)))

        report, _, _ = collect(
            FakeCandidateSource(*(f"o{i}/r" for i in range(5))), repo_source=github, limit=3
        )

        assert report.discovered == 3

    def test_repos_that_do_not_exist_are_reported_as_missing(self):
        report, _, status = collect(
            FakeCandidateSource("a/x", "gone/repo"),
            repo_source=FakeRepoSource(make_snapshot("a/x")),
        )

        assert [str(repo) for repo in report.missing] == ["gone/repo"]
        assert status.load(TODAY) == CollectionStatus(TODAY, discovered=2, collected=1, failed=0)

    def test_a_failed_chunk_is_reported_and_the_run_goes_on(self):
        repos = [f"o{i}/r" for i in range(45)]
        github = FakeRepoSource(*(make_snapshot(r) for r in repos), failing=["o0/r"])

        report, store, status = collect(FakeCandidateSource(*repos), repo_source=github)

        assert len(report.failed) == 20
        assert len(store.load(TODAY)) == 25
        assert report.fetch_errors == ("HTTP 502",)
        assert not status.load(TODAY).is_complete

    def test_stops_asking_after_three_failures_in_a_row(self):
        repos = [f"o{i}/r" for i in range(100)]
        failing = ["o0/r", "o20/r", "o40/r"]
        github = FakeRepoSource(*(make_snapshot(r) for r in repos), failing=failing)

        report, _, _ = collect(FakeCandidateSource(*repos), repo_source=github)

        assert len(github.calls) == 3
        assert len(report.failed) == 100

    def test_drops_snapshots_older_than_14_days(self):
        store = InMemorySnapshotStore(
            {
                TODAY - timedelta(days=15): [old_snapshot("o/old", 15)],
                TODAY - timedelta(days=14): [],
            }
        )

        collect(FakeCandidateSource(), repo_source=FakeRepoSource(), store=store)

        assert min(store.days) == TODAY - timedelta(days=14)


class TestRerunOfTheSameDay:
    def test_fetches_only_what_is_missing(self):
        store = InMemorySnapshotStore({TODAY: [make_snapshot("a/x")]})
        github = FakeRepoSource(make_snapshot("a/x"), make_snapshot("b/y"))

        report, _, _ = collect(FakeCandidateSource("a/x", "b/y"), repo_source=github, store=store)

        assert github.fetched == ["b/y"]
        assert report.collected == 2


class TestReuse:
    def test_young_facts_are_carried_over_with_the_stars_of_today(self):
        store = InMemorySnapshotStore({YESTERDAY: [old_snapshot("a/x", stars=100)]})
        github = FakeRepoSource()

        report, store, _ = collect(
            FakeCandidateSource(("a/x", 130)), repo_source=github, store=store
        )

        (snapshot,) = store.load(TODAY)
        assert github.calls == []
        assert snapshot.taken_at == NOW
        assert snapshot.facts_at == NOW - timedelta(days=1)
        assert snapshot.stars == 130
        assert snapshot.star_history == StarHistory((0, 5, 30))
        assert report.carried_over == 1

    def test_facts_of_three_days_are_refreshed_without_star_history(self):
        store = InMemorySnapshotStore(
            {TODAY - timedelta(days=3): [old_snapshot("a/x", days_ago=3, stars=100)]}
        )
        github = FakeRepoSource(make_snapshot("a/x", stars=112, description="Neu"))

        report, store, _ = collect(
            FakeCandidateSource(("a/x", 112)), repo_source=github, store=store
        )

        (snapshot,) = store.load(TODAY)
        assert github.calls == [(["a/x"], False)]
        assert snapshot.description == "Neu"
        assert snapshot.star_history == StarHistory((0, 0, 12))  # three days on
        assert report.refreshed == 1

    def test_a_candidate_without_star_count_is_refreshed(self):
        store = InMemorySnapshotStore({YESTERDAY: [old_snapshot("a/x")]})
        github = FakeRepoSource(make_snapshot("a/x"))

        collect(FakeCandidateSource(("a/x", None)), repo_source=github, store=store)

        assert github.calls == [(["a/x"], False)]

    def test_a_snapshot_without_star_history_is_fetched_anew(self):
        store = InMemorySnapshotStore(
            {YESTERDAY: [old_snapshot("a/x", star_history=StarHistory(()))]}
        )
        github = FakeRepoSource(make_snapshot("a/x"))

        collect(FakeCandidateSource("a/x"), repo_source=github, store=store)

        assert github.calls == [(["a/x"], True)]

    def test_a_repo_not_seen_for_more_than_three_days_is_fetched_anew(self):
        store = InMemorySnapshotStore(
            {TODAY - timedelta(days=4): [old_snapshot("a/x", days_ago=4)]}
        )
        github = FakeRepoSource(make_snapshot("a/x"))

        collect(FakeCandidateSource("a/x"), repo_source=github, store=store)

        assert github.calls == [(["a/x"], True)]

    def test_when_refreshing_fails_the_older_facts_are_carried_over(self):
        store = InMemorySnapshotStore(
            {
                TODAY - timedelta(days=3): [
                    old_snapshot("a/x", days_ago=3),
                    old_snapshot("b/y", days_ago=3),
                ]
            }
        )
        github = FakeRepoSource(failing=["a/x"])

        report, store, status = collect(
            FakeCandidateSource(("a/x", 120), ("b/y", None)), repo_source=github, store=store
        )

        assert names(store.load(TODAY)) == ["a/x"]
        assert [str(repo) for repo in report.failed] == ["b/y"]
        assert status.load(TODAY).failed == 1


class TestFreshLeaders:
    def test_the_best_repos_get_fresh_facts_before_publishing(self):
        store = InMemorySnapshotStore(
            {YESTERDAY: [old_snapshot("a/x", star_history=star_history(500))]}
        )
        github = FakeRepoSource(make_snapshot("a/x", stars=101))

        report, store, _ = collect(
            FakeCandidateSource(("a/x", 101)),
            repo_source=github,
            store=store,
            assess=Assessor().assess,
        )

        (snapshot,) = store.load(TODAY)
        assert github.calls == [(["a/x"], False)]
        assert snapshot.facts_at == NOW
        assert (report.refreshed, report.carried_over) == (1, 0)

    def test_excluded_repos_are_not_refreshed(self):
        store = InMemorySnapshotStore({YESTERDAY: [old_snapshot("a/x", is_fork=True)]})
        github = FakeRepoSource()

        collect(
            FakeCandidateSource("a/x"), repo_source=github, store=store, assess=Assessor().assess
        )

        assert github.calls == []

    def test_without_assessment_nothing_is_refreshed(self):
        store = InMemorySnapshotStore(
            {YESTERDAY: [old_snapshot("a/x", star_history=star_history(500))]}
        )
        github = FakeRepoSource()

        collect(FakeCandidateSource("a/x"), repo_source=github, store=store)

        assert github.calls == []


@pytest.mark.parametrize("failed, complete", [(0, True), (1, False)])
def test_collection_status_is_complete_without_failures(failed, complete):
    assert CollectionStatus(TODAY, 3, 3 - failed, failed).is_complete is complete
