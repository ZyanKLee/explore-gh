"""What the adapters contribute to reusing snapshots. See docs/datensammlung.md."""

import gzip
import json
from datetime import timedelta
from pathlib import Path

import httpx

from builders import NOW, TODAY, FixedClock, make_snapshot
from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.adapters.github_search import GitHubSearchCandidates
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.domain.model import Candidate, RepoId, StarHistory

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_RESULT = json.loads((FIXTURES / "search_repositories.json").read_text())
FULL = json.loads((FIXTURES / "graphql_repo_full.json").read_text())
STAR_HISTORY = json.loads((FIXTURES / "star_history.json").read_text())


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")


def test_search_hands_on_the_star_count_of_each_candidate():
    search = GitHubSearchCandidates(
        client(lambda request: httpx.Response(200, json=SEARCH_RESULT)),
        sleep=lambda seconds: None,
        clock=FixedClock(NOW),
        window_days=1,
        min_stars=50,
        pause_seconds=2.0,
    )

    assert search.discover(TODAY) == [
        Candidate(RepoId.parse("alice/tiny-editor"), stars=812),
        Candidate(RepoId.parse("bob/rustbox"), stars=95),
    ]


class GitHub:
    def __init__(self):
        self.history_requests = 0

    def __call__(self, request):
        if request.method == "GET":
            self.history_requests += 1
            return httpx.Response(200, json=STAR_HISTORY)
        return httpx.Response(200, json={"data": {"r0": FULL}})


def fetch(github, **options):
    source = GitHubRepoSource(client(github), sleep=lambda seconds: None, clock=FixedClock(NOW))
    return source.fetch([RepoId.parse("alice/tiny-editor")], NOW, **options)


def test_facts_can_be_fetched_without_the_star_history():
    github = GitHub()

    [snapshot] = fetch(github, with_star_history=False)

    assert github.history_requests == 0
    assert snapshot.star_history == StarHistory(daily=())
    assert snapshot.stars == 812
    assert snapshot.facts_at == NOW


def test_star_history_is_fetched_unless_told_otherwise():
    github = GitHub()

    [snapshot] = fetch(github)

    assert github.history_requests == 1
    assert snapshot.star_history.daily != ()


def test_age_of_the_facts_survives_storing(tmp_path):
    store = JsonSnapshotStore(tmp_path)
    carried = make_snapshot(taken_at=NOW, facts_at=NOW - timedelta(days=2))

    store.append(TODAY, [carried])

    assert store.load(TODAY) == [carried]
    assert store.load(TODAY)[0].facts_at == NOW - timedelta(days=2)


def test_snapshot_files_written_before_the_reuse_can_still_be_read(tmp_path):
    store = JsonSnapshotStore(tmp_path)
    store.append(TODAY, [make_snapshot()])
    path = tmp_path / "2026-11-12.jsonl.gz"
    old_format = json.loads(gzip.decompress(path.read_bytes()).decode())
    old_format.pop("facts_at", None)
    path.write_bytes(gzip.compress((json.dumps(old_format) + "\n").encode()))

    [snapshot] = store.load(TODAY)

    assert snapshot.facts_at == snapshot.taken_at
