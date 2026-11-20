import copy
import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from builders import NOW, FixedClock
from http_fakes import FakeWeb, Sleeps, fixture

from explore_gh.adapters.github_repo_source import GitHubRepoSource
from explore_gh.application.ports import SourceUnavailable
from explore_gh.domain.model import README_MAX_CHARS, RepoId

GRAPHQL = "POST api.github.com/graphql"
FULL = fixture("graphql_repo_full.json")
EMPTY = fixture("graphql_repo_empty.json")


def node(name="alice/tiny-editor", **changes):
    data = copy.deepcopy(FULL)
    data["nameWithOwner"] = name
    data.update(changes)
    return data


def history_route(name="alice/tiny-editor"):
    return {
        f"api.github.com/repos/{name}/stargazers/history": httpx.Response(
            200, json=fixture("star_history.json")
        )
    }


def answer_with(*nodes):
    """Answers each GraphQL query with the nodes of the asked repos, by name."""
    by_name = {n["nameWithOwner"].lower(): n for n in nodes}

    def answer(request):
        variables = json.loads(request.content)["variables"]
        data = {}
        for key, owner in variables.items():
            if key.startswith("owner"):
                i = key.removeprefix("owner")
                data[f"r{i}"] = by_name.get(f"{owner}/{variables['name' + i]}".lower())
        return httpx.Response(200, json={"data": data})

    return answer


def fetch(web, *names, with_star_history=True, **options):
    with web.github_client() as client:
        source = GitHubRepoSource(client, sleep=Sleeps(), clock=FixedClock(), **options)
        return source.fetch([RepoId.parse(n) for n in names], NOW, with_star_history)


def graphql_queries(web):
    return [json.loads(r.content) for r in web.requests if r.url.path == "/graphql"]


def test_a_snapshot_carries_the_facts_of_the_repo():
    web = FakeWeb({GRAPHQL: answer_with(node()), **history_route()})

    (snapshot,) = fetch(web, "alice/tiny-editor")

    assert snapshot.taken_at == NOW
    assert snapshot.description == "A tiny terminal text editor"
    assert snapshot.homepage == "https://tiny-editor.example.org"
    assert snapshot.topics[0] == "editor"
    assert snapshot.primary_language == "Rust"
    assert snapshot.created_at == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    assert (snapshot.stars, snapshot.forks, snapshot.pull_requests) == (812, 31, 27)
    assert snapshot.license == "MIT"
    assert ".github" in snapshot.root_files
    assert snapshot.readme == "# tiny-editor\n\nA tiny terminal text editor.\n"
    assert not (snapshot.is_fork or snapshot.is_archived or snapshot.is_mirror)


def test_commits_carry_author_bot_mark_and_co_authors():
    web = FakeWeb({GRAPHQL: answer_with(node()), **history_route()})

    (snapshot,) = fetch(web, "alice/tiny-editor")

    first = snapshot.recent_commits[0]
    assert first.author == "alice"
    assert first.headline == "Add syntax highlighting for TOML"
    assert first.co_authors[0].startswith("Claude <")
    assert any(c.is_bot for c in snapshot.recent_commits) == any(
        c.author.endswith("[bot]") for c in snapshot.recent_commits
    )


def test_commits_of_the_last_90_days_are_asked_for():
    web = FakeWeb({GRAPHQL: answer_with(node()), **history_route()})

    fetch(web, "alice/tiny-editor")

    assert graphql_queries(web)[0]["variables"]["since"] == "2026-08-14T06:00:00Z"


def test_issue_authors_are_distinct_people_without_bots():
    issues = [
        {"author": {"__typename": "User", "login": "a"}},
        {"author": {"__typename": "User", "login": "a"}},
        {"author": {"__typename": "Bot", "login": "renovate"}},
        {"author": None},
        {"author": {"__typename": "User", "login": "b"}},
    ]
    web = FakeWeb({GRAPHQL: answer_with(node(recentIssues={"nodes": issues})), **history_route()})

    assert fetch(web, "alice/tiny-editor")[0].recent_issue_authors == 2


def test_the_history_of_an_owner_who_is_a_person():
    owner = {
        "__typename": "User",
        "createdAt": "2019-03-01T00:00:00Z",
        "repositoriesContributedTo": {"totalCount": 7},
    }
    web = FakeWeb({GRAPHQL: answer_with(node(owner=owner)), **history_route()})

    (snapshot,) = fetch(web, "alice/tiny-editor")

    assert snapshot.owner_created_at == datetime(2019, 3, 1, tzinfo=UTC)
    assert snapshot.owner_contributed_to == 7


def test_an_organization_has_an_age_but_no_contributions():
    owner = {"__typename": "Organization", "createdAt": "2019-03-01T00:00:00Z"}
    web = FakeWeb({GRAPHQL: answer_with(node(owner=owner)), **history_route()})

    (snapshot,) = fetch(web, "alice/tiny-editor")

    assert snapshot.owner_contributed_to is None
    assert snapshot.owner_created_at is not None


def test_another_readme_variant_is_taken_if_there_is_no_readme_md():
    data = node(readmeMd=None, readmeRst={"text": "Tiny\n===="})
    web = FakeWeb({GRAPHQL: answer_with(data), **history_route()})

    assert fetch(web, "alice/tiny-editor")[0].readme == "Tiny\n===="


def test_a_long_readme_is_cut():
    web = FakeWeb({GRAPHQL: answer_with(node(readmeMd={"text": "x" * 30_000})), **history_route()})

    assert len(fetch(web, "alice/tiny-editor")[0].readme) == README_MAX_CHARS


def test_an_empty_repo_has_no_readme_files_commits_or_optional_facts():
    web = FakeWeb({GRAPHQL: answer_with(EMPTY)})

    (snapshot,) = fetch(web, "carol/empty-thing")

    assert (snapshot.readme, snapshot.root_files, snapshot.recent_commits) == ("", (), ())
    assert (snapshot.description, snapshot.homepage, snapshot.license, snapshot.pushed_at) == (
        "",
        None,
        None,
        None,
    )


def test_the_star_history_lists_the_new_stars_of_each_day_up_to_today():
    web = FakeWeb({GRAPHQL: answer_with(node()), **history_route()})

    (snapshot,) = fetch(web, "alice/tiny-editor")

    assert len(snapshot.star_history.daily) == 35
    assert snapshot.star_history.daily[-5:] == (36, 59, 77, 127, 15)  # Sunday to Thursday
    history_request = next(r for r in web.requests if "stargazers" in r.url.path)
    assert history_request.url.params["per_page"] == "6"


def test_no_star_history_for_a_repo_that_can_never_be_shown_or_when_not_wanted():
    web = FakeWeb({GRAPHQL: answer_with(node("a/fork", isFork=True), node())})

    fetch(web, "a/fork")
    fetch(web, "alice/tiny-editor", with_star_history=False)

    assert not any("stargazers" in path for path in web.paths)


def test_an_unavailable_star_history_makes_the_source_unavailable():
    web = FakeWeb(
        {GRAPHQL: answer_with(node()), **{k: httpx.Response(500) for k in history_route()}}
    )

    with pytest.raises(SourceUnavailable):
        fetch(web, "alice/tiny-editor")


def test_a_repo_that_does_not_exist_is_left_out():
    web = FakeWeb({GRAPHQL: answer_with(node()), **history_route()})

    assert [str(s.repo) for s in fetch(web, "gone/repo", "alice/tiny-editor")] == [
        "alice/tiny-editor"
    ]


def test_repos_are_fetched_in_batches_of_ten():
    nodes = [node(f"o{i}/r", primaryLanguage=None) for i in range(12)]
    web = FakeWeb({GRAPHQL: answer_with(*nodes)})

    assert len(fetch(web, *(f"o{i}/r" for i in range(12)))) == 12
    assert len(graphql_queries(web)) == 2


def test_a_graphql_error_makes_the_source_unavailable_even_with_data():
    refused = httpx.Response(
        200, json={"data": {"r0": None}, "errors": [{"type": "FORBIDDEN", "message": "Nope"}]}
    )
    web = FakeWeb({GRAPHQL: refused})

    with pytest.raises(SourceUnavailable, match="Nope"):
        fetch(web, "alice/tiny-editor")


def test_a_batch_too_expensive_is_split_and_a_single_repo_too_expensive_is_left_out(caplog):
    expensive = {"errors": [{"type": "RESOURCE_LIMITS_EXCEEDED", "message": "Resource limits"}]}
    cheap = answer_with(*(node(f"o{i}/r", primaryLanguage=None) for i in range(4)))

    def answer(request):
        variables = json.loads(request.content)["variables"]
        if "o0" in variables.values():  # every batch with o0 in it
            return httpx.Response(200, json=expensive)
        return cheap(request)

    web = FakeWeb({GRAPHQL: answer})
    with caplog.at_level(logging.INFO):
        found = fetch(web, *(f"o{i}/r" for i in range(4)))

    assert sorted(str(s.repo) for s in found) == ["o1/r", "o2/r", "o3/r"]
    assert "Gruppe von 4 Repos wird geteilt" in caplog.text
    assert "o0/r ist GitHub zu aufwendig" in caplog.text


def test_a_batch_that_times_out_is_split_at_once_and_only_a_single_repo_is_retried():
    nodes = [node(f"o{i}/r", primaryLanguage=None) for i in range(2)]
    good = answer_with(*nodes)

    def answer(request):
        variables = json.loads(request.content)["variables"]
        return httpx.Response(504) if variables.get("owner0") == "o0" else good(request)

    web = FakeWeb({GRAPHQL: answer})

    found = fetch(web, "o0/r", "o1/r")

    assert [str(s.repo) for s in found] == ["o1/r"]
    sizes = [sum(k.startswith("owner") for k in q["variables"]) for q in graphql_queries(web)]
    assert sizes == [2, 1, 1, 1, 1]  # the pair once, the guilty repo three times, the other once


def test_when_everything_times_out_the_source_gives_up():
    web = FakeWeb({GRAPHQL: httpx.Response(502)})

    with pytest.raises(SourceUnavailable):
        fetch(web, *(f"o{i}/r" for i in range(10)))
    assert len(web.requests) < 40
