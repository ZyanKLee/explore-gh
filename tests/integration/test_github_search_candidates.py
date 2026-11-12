import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from builders import NOW, TODAY, FixedClock
from github_anti_ai.adapters.github_search import (
    GitHubSearchCandidates,
    build_discovery_queries,
)
from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.model import RepoId

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_RESULT = json.loads((FIXTURES / "search_repositories.json").read_text())
EMPTY_RESULT = {"total_count": 0, "incomplete_results": False, "items": []}


class RecordingSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


def search_candidates(handler, *, window_days=1, sleep=None):
    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    return GitHubSearchCandidates(
        client,
        sleep=sleep or RecordingSleep(),
        clock=FixedClock(NOW),
        window_days=window_days,
        min_stars=50,
        pause_seconds=2.0,
    )


def test_discovery_covers_each_creation_day_of_the_window():
    queries = build_discovery_queries(TODAY, window_days=30, min_stars=50)

    assert len(queries) == 30
    assert queries[0] == "created:2026-11-12 stars:>=50 fork:false archived:false"
    assert queries[-1] == "created:2026-10-14 stars:>=50 fork:false archived:false"


def test_search_asks_for_the_most_starred_repos_first():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=SEARCH_RESULT)

    search_candidates(handler).discover(TODAY)

    params = requests[0].url.params
    assert requests[0].url.path == "/search/repositories"
    assert params["q"] == "created:2026-11-12 stars:>=50 fork:false archived:false"
    assert params["sort"] == "stars"
    assert params["order"] == "desc"
    assert params["per_page"] == "100"


def test_discovered_repos_are_taken_from_the_search_results():
    found = search_candidates(lambda request: httpx.Response(200, json=SEARCH_RESULT)).discover(
        TODAY
    )

    assert found == [RepoId.parse("alice/tiny-editor"), RepoId.parse("bob/rustbox")]


def test_repo_found_by_several_queries_is_returned_once():
    found = search_candidates(
        lambda request: httpx.Response(200, json=SEARCH_RESULT), window_days=3
    ).discover(TODAY)

    assert len(found) == 2


def test_search_stops_as_soon_as_enough_candidates_are_found():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=SEARCH_RESULT)

    found = search_candidates(handler, window_days=30).discover(TODAY, limit=2)

    assert len(requests) == 1
    assert len(found) == 2


def test_search_returns_no_more_candidates_than_the_limit():
    found = search_candidates(lambda request: httpx.Response(200, json=SEARCH_RESULT)).discover(
        TODAY, limit=1
    )

    assert found == [RepoId.parse("alice/tiny-editor")]


def test_search_reports_its_progress(caplog):
    caplog.set_level("INFO", logger="github_anti_ai")

    search_candidates(
        lambda request: httpx.Response(200, json=SEARCH_RESULT), window_days=3
    ).discover(TODAY)

    assert [r.getMessage() for r in caplog.records] == [
        "Suche 1/3: 2 Kandidaten bisher",
        "Suche 2/3: 2 Kandidaten bisher",
        "Suche 3/3: 2 Kandidaten bisher",
    ]


def test_searches_are_paced_to_respect_the_search_limit():
    sleep = RecordingSleep()

    search_candidates(
        lambda request: httpx.Response(200, json=EMPTY_RESULT), window_days=3, sleep=sleep
    ).discover(TODAY)

    assert sleep.calls == [2.0, 2.0]


def test_rate_limited_search_waits_as_told_and_retries():
    responses = iter(
        [
            httpx.Response(403, headers={"retry-after": "7"}, json={"message": "secondary rate limit"}),
            httpx.Response(200, json=SEARCH_RESULT),
        ]
    )
    sleep = RecordingSleep()

    found = search_candidates(lambda request: next(responses), sleep=sleep).discover(TODAY)

    assert sleep.calls == [7]
    assert len(found) == 2


def test_exhausted_rate_limit_waits_until_the_reset():
    reset = int((NOW + timedelta(seconds=60)).timestamp())
    responses = iter(
        [
            httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
                json={"message": "API rate limit exceeded"},
            ),
            httpx.Response(200, json=SEARCH_RESULT),
        ]
    )
    sleep = RecordingSleep()

    search_candidates(lambda request: next(responses), sleep=sleep).discover(TODAY)

    assert len(sleep.calls) == 1
    assert 60 <= sleep.calls[0] <= 65


def test_persistent_server_errors_make_the_source_unavailable():
    attempts = []

    def handler(request):
        attempts.append(request)
        return httpx.Response(502)

    with pytest.raises(SourceUnavailable):
        search_candidates(handler).discover(TODAY)

    assert len(attempts) == 3
