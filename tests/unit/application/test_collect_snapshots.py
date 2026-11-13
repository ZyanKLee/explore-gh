from datetime import timedelta

from builders import NOW, TODAY, FixedClock, make_snapshot
from fakes import InMemorySnapshotStore
from github_anti_ai.application.collect_snapshots import (
    FETCH_CHUNK_SIZE,
    MAX_CONSECUTIVE_FAILURES,
    SNAPSHOT_RETENTION_DAYS,
    CollectSnapshots,
)
from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.model import Candidate, RepoId


class FakeCandidateSource:
    def __init__(self, name, repos=(), error=None):
        self.name = name
        self.repos = [RepoId.parse(r) for r in repos]
        self.error = error
        self.asked_for = None
        self.asked_limit = None

    def discover(self, today, limit=None):
        self.asked_for = today
        self.asked_limit = limit
        if self.error:
            raise self.error
        return [Candidate(repo) for repo in self.repos[:limit]]


class FakeRepoSource:
    def __init__(self, unknown=(), failing=()):
        self.unknown = {RepoId.parse(r) for r in unknown}
        self.failing = {RepoId.parse(r) for r in failing}
        self.requests = []

    def fetch(self, repos, now, with_star_history=True):
        self.requests.append((list(repos), now))
        if any(r in self.failing for r in repos):
            raise SourceUnavailable("HTTP 502")
        return [make_snapshot(str(r), taken_at=now) for r in repos if r not in self.unknown]

    @property
    def requested(self):
        return [str(repo) for repos, _ in self.requests for repo in repos]


def collect(sources, repo_source=None, store=None, limit=None):
    use_case = CollectSnapshots(
        candidate_sources=sources,
        repo_source=repo_source or FakeRepoSource(),
        snapshot_store=store if store is not None else InMemorySnapshotStore(),
        clock=FixedClock(NOW),
        limit=limit,
    )
    return use_case.run()


def repos_in(snapshots):
    return {str(s.repo) for s in snapshots}


def many(count):
    return [f"user{i}/project{i}" for i in range(count)]


def chunk(names, index):
    return names[index * FETCH_CHUNK_SIZE : (index + 1) * FETCH_CHUNK_SIZE]


def test_snapshots_of_all_discovered_repos_are_saved_under_todays_date():
    store = InMemorySnapshotStore()

    collect([FakeCandidateSource("search", ["alice/tiny-editor", "bob/rustbox"])], store=store)

    assert repos_in(store.load(TODAY)) == {"alice/tiny-editor", "bob/rustbox"}


def test_sources_are_asked_for_candidates_of_today():
    source = FakeCandidateSource("search", ["alice/tiny-editor"])

    collect([source])

    assert source.asked_for == TODAY


def test_snapshots_are_taken_at_the_current_time():
    repo_source = FakeRepoSource()

    collect([FakeCandidateSource("search", ["alice/tiny-editor"])], repo_source=repo_source)

    assert repo_source.requests[0][1] == NOW


def test_candidates_found_by_several_sources_are_fetched_only_once():
    repo_source = FakeRepoSource()
    sources = [
        FakeCandidateSource("search", ["alice/tiny-editor", "bob/rustbox"]),
        FakeCandidateSource("trending", ["Alice/Tiny-Editor", "carol/plotter"]),
    ]

    collect(sources, repo_source=repo_source)

    assert len(repo_source.requested) == 3
    assert {name.lower() for name in repo_source.requested} == {
        "alice/tiny-editor",
        "bob/rustbox",
        "carol/plotter",
    }


def test_unavailable_candidate_source_is_reported_and_the_others_still_collected():
    store = InMemorySnapshotStore()
    sources = [
        FakeCandidateSource("trending", error=SourceUnavailable("HTTP 502")),
        FakeCandidateSource("search", ["alice/tiny-editor"]),
    ]

    report = collect(sources, store=store)

    assert repos_in(store.load(TODAY)) == {"alice/tiny-editor"}
    assert len(report.source_errors) == 1
    assert "trending" in report.source_errors[0]
    assert "HTTP 502" in report.source_errors[0]


def test_repos_the_source_cannot_deliver_are_reported_as_missing():
    report = collect(
        [FakeCandidateSource("search", ["alice/tiny-editor", "gone/deleted-repo"])],
        repo_source=FakeRepoSource(unknown=["gone/deleted-repo"]),
    )

    assert report.missing == (RepoId.parse("gone/deleted-repo"),)


def test_report_counts_discovered_and_collected_repos():
    report = collect(
        [
            FakeCandidateSource("search", ["alice/tiny-editor", "gone/deleted-repo"]),
            FakeCandidateSource("trending", ["alice/tiny-editor"]),
        ],
        repo_source=FakeRepoSource(unknown=["gone/deleted-repo"]),
    )

    assert report.day == TODAY
    assert report.discovered == 2
    assert report.collected == 1
    assert report.failed == ()


def test_repos_are_fetched_in_chunks():
    repo_source = FakeRepoSource()

    collect([FakeCandidateSource("search", many(2 * FETCH_CHUNK_SIZE + 5))], repo_source=repo_source)

    assert [len(repos) for repos, _ in repo_source.requests] == [
        FETCH_CHUNK_SIZE,
        FETCH_CHUNK_SIZE,
        5,
    ]


def test_rerun_on_the_same_day_fetches_only_what_is_still_missing():
    store = InMemorySnapshotStore({TODAY: [make_snapshot("alice/tiny-editor")]})
    repo_source = FakeRepoSource()

    report = collect(
        [FakeCandidateSource("search", ["alice/tiny-editor", "bob/rustbox"])],
        repo_source=repo_source,
        store=store,
    )

    assert repo_source.requested == ["bob/rustbox"]
    assert repos_in(store.load(TODAY)) == {"alice/tiny-editor", "bob/rustbox"}
    assert report.collected == 2


def test_failed_chunk_is_reported_and_the_other_chunks_are_still_saved():
    names = many(3 * FETCH_CHUNK_SIZE)
    store = InMemorySnapshotStore()

    report = collect(
        [FakeCandidateSource("search", names)],
        repo_source=FakeRepoSource(failing=[chunk(names, 1)[0]]),
        store=store,
    )

    assert repos_in(store.load(TODAY)) == set(chunk(names, 0) + chunk(names, 2))
    assert [str(r) for r in report.failed] == chunk(names, 1)
    assert report.collected == 2 * FETCH_CHUNK_SIZE
    assert report.fetch_errors == ("HTTP 502",)


def test_run_gives_up_after_several_failed_chunks_in_a_row_but_keeps_what_it_has():
    chunks = MAX_CONSECUTIVE_FAILURES + 2
    names = many(chunks * FETCH_CHUNK_SIZE)
    failing = [chunk(names, i)[0] for i in range(1, MAX_CONSECUTIVE_FAILURES + 1)]
    repo_source = FakeRepoSource(failing=failing)
    store = InMemorySnapshotStore()

    report = collect([FakeCandidateSource("search", names)], repo_source=repo_source, store=store)

    assert len(repo_source.requests) == 1 + MAX_CONSECUTIVE_FAILURES
    assert repos_in(store.load(TODAY)) == set(chunk(names, 0))
    assert [str(r) for r in report.failed] == names[FETCH_CHUNK_SIZE:]


def test_failures_that_are_not_in_a_row_do_not_stop_the_run():
    chunks = 2 * MAX_CONSECUTIVE_FAILURES
    names = many(chunks * FETCH_CHUNK_SIZE)
    failing = [chunk(names, i)[0] for i in range(0, chunks, 2)]
    repo_source = FakeRepoSource(failing=failing)

    collect([FakeCandidateSource("search", names)], repo_source=repo_source)

    assert len(repo_source.requests) == chunks


def test_limit_caps_the_number_of_candidates():
    first = FakeCandidateSource("search", ["a/one", "b/two", "c/three"])
    second = FakeCandidateSource("trending", ["d/four", "e/five", "f/six"])
    repo_source = FakeRepoSource()

    report = collect([first, second], repo_source=repo_source, limit=4)

    assert repo_source.requested == ["a/one", "b/two", "c/three", "d/four"]
    assert second.asked_limit == 1
    assert report.discovered == 4


def test_sources_are_not_asked_once_the_limit_is_reached():
    first = FakeCandidateSource("search", ["a/one", "b/two", "c/three"])
    second = FakeCandidateSource("trending", ["d/four"])

    collect([first, second], limit=3)

    assert second.asked_for is None


def test_progress_is_reported_for_each_chunk(caplog):
    caplog.set_level("INFO", logger="github_anti_ai")

    collect([FakeCandidateSource("search", many(2 * FETCH_CHUNK_SIZE + 5))])

    messages = [r.getMessage() for r in caplog.records]
    assert messages == [
        "45 Kandidaten: 45 neu holen, 0 auffrischen, 0 übernehmen, 0 schon da",
        "Neu holen 1/3: 20 von 45 Repos",
        "Neu holen 2/3: 40 von 45 Repos",
        "Neu holen 3/3: 45 von 45 Repos",
    ]


def test_snapshots_older_than_the_retention_period_are_pruned():
    oldest_kept = TODAY - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    too_old = oldest_kept - timedelta(days=1)
    store = InMemorySnapshotStore(
        {too_old: [make_snapshot()], oldest_kept: [make_snapshot()]}
    )

    collect([FakeCandidateSource("search", ["alice/tiny-editor"])], store=store)

    assert store.load(too_old) == []
    assert store.load(oldest_kept) != []
