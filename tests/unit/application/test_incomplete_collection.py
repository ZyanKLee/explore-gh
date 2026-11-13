"""An Edition is never replaced, so it must not be built from a collection with holes."""

import pytest

from builders import NOW, TODAY, FixedClock, make_snapshot
from fakes import InMemoryCollectionStatusStore, InMemoryEditionStore, InMemorySnapshotStore
from github_anti_ai.application.collect_snapshots import FETCH_CHUNK_SIZE, CollectSnapshots
from github_anti_ai.application.ports import (
    CollectionStatus,
    IncompleteCollection,
    SourceUnavailable,
)
from github_anti_ai.application.publish_edition import PublishEdition
from github_anti_ai.domain.model import Assessment, Candidate, RepoId, Section


def status(failed=0, discovered=100):
    return CollectionStatus(
        day=TODAY, discovered=discovered, collected=discovered - failed, failed=failed
    )


def publish(statuses, allow_incomplete=False):
    editions = InMemoryEditionStore()
    use_case = PublishEdition(
        snapshot_store=InMemorySnapshotStore({TODAY: [make_snapshot()]}),
        edition_store=editions,
        collection_status_store=InMemoryCollectionStatusStore(statuses),
        assess=lambda s: Assessment(snapshot=s, section=Section.MAIN, score=1.0, signals=()),
        clock=FixedClock(NOW),
        allow_incomplete=allow_incomplete,
    )
    return use_case, editions


def test_complete_collection_is_published():
    use_case, editions = publish([status()])

    use_case.run()

    assert editions.load(TODAY) is not None


def test_collection_with_failed_repos_is_not_published():
    use_case, editions = publish([status(failed=20, discovered=2846)])

    with pytest.raises(IncompleteCollection) as refused:
        use_case.run()

    assert "20" in str(refused.value)
    assert "2846" in str(refused.value)
    assert editions.load(TODAY) is None


def test_collection_that_never_finished_is_not_published():
    # the run was aborted, or the snapshots stem from a time before the status existed
    use_case, editions = publish([])

    with pytest.raises(IncompleteCollection) as refused:
        use_case.run()

    assert "nicht abgeschlossen" in str(refused.value)
    assert editions.load(TODAY) is None


@pytest.mark.parametrize("statuses", [[], [status(failed=20)]])
def test_incomplete_collection_can_be_published_on_purpose(statuses):
    use_case, editions = publish(statuses, allow_incomplete=True)

    use_case.run()

    assert editions.load(TODAY) is not None


def test_repos_that_no_longer_exist_do_not_make_a_collection_incomplete():
    gone = CollectionStatus(day=TODAY, discovered=100, collected=97, failed=0)

    assert gone.is_complete


# --- the collection records how it ended ----------------------------------------------


class Search:
    name = "search"

    def __init__(self, count):
        self.candidates = [Candidate(RepoId.parse(f"user{i}/project{i}")) for i in range(count)]

    def discover(self, today, limit=None):
        return self.candidates


class RepoSource:
    def __init__(self, failing=False):
        self.failing = failing

    def fetch(self, repos, now, with_star_history=True):
        if self.failing:
            raise SourceUnavailable("HTTP 502")
        return [make_snapshot(str(r), taken_at=now) for r in repos]


def collect(repo_source, snapshots, statuses, count=FETCH_CHUNK_SIZE + 5):
    return CollectSnapshots(
        candidate_sources=[Search(count)],
        repo_source=repo_source,
        snapshot_store=snapshots,
        clock=FixedClock(NOW),
        status_store=statuses,
    ).run()


def test_collection_records_that_it_is_complete():
    statuses = InMemoryCollectionStatusStore()

    collect(RepoSource(), InMemorySnapshotStore(), statuses)

    recorded = statuses.load(TODAY)
    assert recorded == CollectionStatus(day=TODAY, discovered=25, collected=25, failed=0)
    assert recorded.is_complete


def test_collection_records_how_many_repos_failed():
    statuses = InMemoryCollectionStatusStore()

    collect(RepoSource(failing=True), InMemorySnapshotStore(), statuses)

    recorded = statuses.load(TODAY)
    assert (recorded.discovered, recorded.collected, recorded.failed) == (25, 0, 25)
    assert not recorded.is_complete


def test_second_run_that_fetches_the_rest_makes_the_collection_complete():
    snapshots, statuses = InMemorySnapshotStore(), InMemoryCollectionStatusStore()
    collect(RepoSource(failing=True), snapshots, statuses)

    collect(RepoSource(), snapshots, statuses)

    assert statuses.load(TODAY).is_complete
