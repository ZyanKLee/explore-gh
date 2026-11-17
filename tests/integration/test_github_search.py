from datetime import date

import httpx
from builders import TODAY, FixedClock
from http_fakes import FakeWeb, Sleeps, fixture

from github_anti_ai.adapters.github_search import GitHubSearchCandidates, discovery_queries
from github_anti_ai.domain.model import Candidate, RepoId

SEARCH = "api.github.com/search/repositories"


def search(web, sleeps=None, limit=None, window_days=3):
    with web.github_client() as client:
        source = GitHubSearchCandidates(
            client,
            sleep=sleeps if sleeps is not None else Sleeps(),
            clock=FixedClock(),
            window_days=window_days,
        )
        return source.discover(TODAY, limit)


def test_one_query_per_creation_day_of_the_window():
    assert discovery_queries(date(2026, 11, 12), 2, 50) == [
        "created:2026-11-12 stars:>=50 fork:false archived:false",
        "created:2026-11-11 stars:>=50 fork:false archived:false",
    ]


def test_the_most_starred_repos_come_first():
    web = FakeWeb({SEARCH: httpx.Response(200, json=fixture("search_repositories.json"))})

    search(web, window_days=1)

    params = web.requests[0].url.params
    assert (params["sort"], params["order"], params["per_page"]) == ("stars", "desc", "100")


def test_candidates_come_with_their_star_count_and_each_once():
    web = FakeWeb({SEARCH: httpx.Response(200, json=fixture("search_repositories.json"))})

    found = search(web)

    assert found[0] == Candidate(RepoId.parse("alice/tiny-editor"), stars=812)
    assert [str(c.repo) for c in found] == ["alice/tiny-editor", "bob/rustbox"]
    assert len(web.requests) == 3


def test_the_search_stops_when_enough_are_found():
    web = FakeWeb({SEARCH: httpx.Response(200, json=fixture("search_repositories.json"))})

    found = search(web, limit=1)

    assert len(found) == 1
    assert len(web.requests) == 1


def test_searches_are_paced_for_the_limit_of_30_per_minute():
    sleeps = Sleeps()
    web = FakeWeb({SEARCH: httpx.Response(200, json={"items": []})})

    search(web, sleeps)

    assert sleeps == [2.0, 2.0]
