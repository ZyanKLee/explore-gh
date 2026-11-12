import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from builders import NOW, FixedClock
from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.model import (
    COMMIT_LOOKBACK,
    README_MAX_CHARS,
    STAR_HISTORY_DAYS,
    Commit,
    RepoId,
)

FIXTURES = Path(__file__).parent / "fixtures"
FULL = json.loads((FIXTURES / "graphql_repo_full.json").read_text())
EMPTY = json.loads((FIXTURES / "graphql_repo_empty.json").read_text())
STAR_HISTORY = json.loads((FIXTURES / "star_history.json").read_text())

# Wire contract of the adapter: repo i of a batch is requested with the variables
# owner{i}/name{i} under the alias r{i}. The star history of each repo found comes
# from GET /repos/{owner}/{name}/stargazers/history.


def node(template=FULL, name_with_owner=None, **changes):
    result = copy.deepcopy(template)
    if name_with_owner:
        result["nameWithOwner"] = name_with_owner
    result.update(changes)
    return result


class FakeGitHub:
    def __init__(self, nodes=(), histories=None, graphql_responses=None, history_status=200):
        self.nodes = {n["nameWithOwner"].lower(): n for n in nodes}
        self.histories = {k.lower(): v for k, v in (histories or {}).items()}
        self.graphql_responses = iter(graphql_responses) if graphql_responses else None
        self.history_status = history_status
        self.bodies = []
        self.history_requests = []

    def __call__(self, request):
        if request.method == "GET":
            return self._history(request)
        assert request.url.path == "/graphql"
        body = json.loads(request.content)
        self.bodies.append(body)
        if self.graphql_responses:
            return next(self.graphql_responses)
        variables = body["variables"]
        data, errors, i = {}, [], 0
        while f"owner{i}" in variables:
            key = f"{variables[f'owner{i}']}/{variables[f'name{i}']}".lower()
            data[f"r{i}"] = self.nodes.get(key)
            if data[f"r{i}"] is None:
                errors.append({"type": "NOT_FOUND", "path": [f"r{i}"], "message": "Could not resolve"})
            i += 1
        payload = {"data": data}
        if errors:
            payload["errors"] = errors
        return httpx.Response(200, json=payload)

    def _history(self, request):
        self.history_requests.append(request)
        _, repos, owner, name, stargazers, history = request.url.path.split("/")
        assert (repos, stargazers, history) == ("repos", "stargazers", "history")
        if self.history_status != 200:
            return httpx.Response(self.history_status)
        return httpx.Response(200, json=self.histories.get(f"{owner}/{name}".lower(), []))


def fetch(fake, repos=("alice/tiny-editor",), **options):
    client = httpx.Client(transport=httpx.MockTransport(fake), base_url="https://api.github.com")
    source = GitHubRepoSource(client, sleep=lambda seconds: None, clock=FixedClock(NOW), **options)
    return source.fetch([RepoId.parse(r) for r in repos], NOW)


def test_snapshot_carries_the_facts_of_the_repository():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.repo == RepoId.parse("alice/tiny-editor")
    assert snapshot.taken_at == NOW
    assert snapshot.description == "A tiny terminal text editor"
    assert snapshot.homepage == "https://tiny-editor.example.org"
    assert snapshot.primary_language == "Rust"
    assert snapshot.created_at == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    assert snapshot.pushed_at == datetime(2026, 11, 10, 19, 2, 11, tzinfo=UTC)
    assert (snapshot.stars, snapshot.forks, snapshot.open_issues) == (812, 31, 12)
    assert not any(
        [snapshot.is_fork, snapshot.is_archived, snapshot.is_mirror, snapshot.is_template]
    )
    assert snapshot.license == "MIT"


def test_snapshot_carries_cross_checks_for_the_star_count():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.watchers == 9
    assert snapshot.pull_requests == 27
    # alice twice, bob, a deleted account and a bot: two distinct people
    assert snapshot.recent_issue_authors == 2


def test_topics_and_root_files_are_listed():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.topics == ("editor", "terminal")
    assert snapshot.root_files == (".github", "CLAUDE.md", "Cargo.toml", "README.md", "src")


def test_structural_flags_are_taken_over():
    [snapshot] = fetch(FakeGitHub([node(isFork=True, isArchived=True, isMirror=True)]))

    assert snapshot.is_fork and snapshot.is_archived and snapshot.is_mirror


def test_readme_is_read():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.readme == "# tiny-editor\n\nA tiny terminal text editor.\n"


def test_readme_is_taken_from_another_variant_if_there_is_no_readme_md():
    variant = node()
    del variant["readmeMd"]
    variant["readmeRst"] = {"text": "tiny-editor\n===========\n"}

    [snapshot] = fetch(FakeGitHub([variant]))

    assert snapshot.readme == "tiny-editor\n===========\n"


def test_long_readme_is_truncated():
    long_readme = node(readmeMd={"text": "x" * (README_MAX_CHARS + 500)})

    [snapshot] = fetch(FakeGitHub([long_readme]))

    assert len(snapshot.readme) == README_MAX_CHARS


def test_empty_repository_has_no_readme_files_commits_or_optional_facts():
    [snapshot] = fetch(FakeGitHub([EMPTY]), repos=["carol/empty-thing"])

    assert snapshot.readme == ""
    assert snapshot.root_files == ()
    assert snapshot.recent_commits == ()
    assert snapshot.description == ""
    assert snapshot.homepage is None
    assert snapshot.primary_language is None
    assert snapshot.pushed_at is None
    assert snapshot.license is None
    assert snapshot.topics == ()
    assert (snapshot.watchers, snapshot.pull_requests, snapshot.recent_issue_authors) == (0, 0, 0)


def test_recent_commits_are_listed_newest_first():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert [c.headline for c in snapshot.recent_commits] == [
        "Add syntax highlighting for TOML",
        "Bump crossterm from 0.28.1 to 0.29.0",
        "Fix cursor jump on wrapped lines",
        "Initial commit",
    ]
    assert snapshot.recent_commits[0] == Commit(
        committed_at=datetime(2026, 11, 10, 19, 2, 11, tzinfo=UTC),
        author="alice",
        is_bot=False,
        co_authors=("Claude <noreply@anthropic.com>",),
        headline="Add syntax highlighting for TOML",
    )


def test_co_authors_are_read_from_trailers_regardless_of_case():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.recent_commits[2].co_authors == (
        "Carol <carol@example.org>",
        "Dave <dave@example.org>",
    )


def test_commits_by_bots_are_marked():
    [snapshot] = fetch(FakeGitHub([FULL]))

    bump = snapshot.recent_commits[1]
    assert bump.is_bot
    assert bump.author == "dependabot[bot]"


def test_commit_author_without_github_account_is_named_by_git_name():
    [snapshot] = fetch(FakeGitHub([FULL]))

    initial = snapshot.recent_commits[3]
    assert initial.author == "Erin"
    assert not initial.is_bot


def test_commits_of_the_lookback_period_are_requested():
    fake = FakeGitHub([FULL])

    fetch(fake)

    since = (NOW - COMMIT_LOOKBACK).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert fake.bodies[0]["variables"]["since"] == since


def test_stargazers_are_no_longer_requested_via_graphql():
    # since July 2026 GitHub hands out stargazer lists to admins and collaborators only
    fake = FakeGitHub([FULL])

    fetch(fake)

    assert "stargazers" not in fake.bodies[0]["query"]


def test_star_history_lists_the_stars_of_each_day_up_to_today():
    fake = FakeGitHub([FULL], histories={"alice/tiny-editor": STAR_HISTORY})

    [snapshot] = fetch(fake)

    daily = snapshot.star_history.daily
    assert len(daily) == STAR_HISTORY_DAYS
    # NOW is Thursday 2026-11-12, the week in the fixture starts on Sunday 2026-11-08
    assert daily[-5:] == (36, 59, 77, 127, 15)
    assert daily[-7:-5] == (40, 35)
    assert daily[0] == 54  # 34 days ago: Friday 2026-10-09
    assert snapshot.star_history.gained() == 40 + 35 + 36 + 59 + 77 + 127 + 15


def test_star_history_is_requested_for_just_the_weeks_needed():
    fake = FakeGitHub([FULL], histories={"alice/tiny-editor": STAR_HISTORY})

    fetch(fake)

    [request] = fake.history_requests
    assert request.url.path == "/repos/alice/tiny-editor/stargazers/history"
    assert request.url.params["per_page"] == "6"


def test_days_without_data_count_as_days_without_stars():
    young = [{"week": 1794096000, "total": 76, "days": [0, 0, 0, 0, 76, 0, 0]}]
    fake = FakeGitHub([FULL], histories={"alice/tiny-editor": young})

    [snapshot] = fetch(fake)

    assert snapshot.star_history.daily == (0,) * (STAR_HISTORY_DAYS - 1) + (76,)


def test_star_history_is_not_requested_for_a_repo_that_does_not_exist():
    fake = FakeGitHub([FULL])

    fetch(fake, repos=["alice/tiny-editor", "gone/deleted-repo"])

    assert [r.url.path for r in fake.history_requests] == [
        "/repos/alice/tiny-editor/stargazers/history"
    ]


@pytest.mark.parametrize(
    "changes",
    [{"isFork": True}, {"isArchived": True}, {"isMirror": True}, {"primaryLanguage": None}],
)
def test_star_history_is_not_requested_for_a_repo_that_can_never_be_shown(changes):
    # saves one request per such repo, about 12 % of all candidates
    fake = FakeGitHub([node(**changes)], histories={"alice/tiny-editor": STAR_HISTORY})

    [snapshot] = fetch(fake)

    assert fake.history_requests == []
    assert snapshot.star_history.daily == ()
    assert snapshot.stars == 812


def test_unavailable_star_history_makes_the_source_unavailable():
    with pytest.raises(SourceUnavailable):
        fetch(FakeGitHub([FULL], history_status=500))


def test_repos_are_fetched_in_batches():
    names = [f"user{i}/project{i}" for i in range(45)]
    fake = FakeGitHub([node(name_with_owner=n) for n in names])

    snapshots = fetch(fake, repos=names, batch_size=20)

    assert len(snapshots) == 45
    batch_sizes = [sum(1 for key in body["variables"] if key.startswith("owner")) for body in fake.bodies]
    assert batch_sizes == [20, 20, 5]


def test_repo_that_does_not_exist_is_left_out():
    snapshots = fetch(FakeGitHub([FULL]), repos=["alice/tiny-editor", "gone/deleted-repo"])

    assert [str(s.repo) for s in snapshots] == ["alice/tiny-editor"]


def test_server_error_is_retried():
    fake = FakeGitHub(
        graphql_responses=[
            httpx.Response(502),
            httpx.Response(200, json={"data": {"r0": FULL}}),
        ]
    )

    snapshots = fetch(fake)

    assert len(snapshots) == 1


def test_graphql_error_without_data_makes_the_source_unavailable():
    fake = FakeGitHub(
        graphql_responses=[
            httpx.Response(
                200, json={"data": None, "errors": [{"type": "INTERNAL", "message": "Something went wrong"}]}
            )
        ]
    )

    with pytest.raises(SourceUnavailable):
        fetch(fake)


def test_refused_access_is_an_error_and_not_a_missing_repo():
    # seen live: a token without access to a field makes the whole repo null
    forbidden = {
        "data": {"r0": None},
        "errors": [
            {
                "type": "FORBIDDEN",
                "path": ["r0", "stargazers"],
                "message": "Resource not accessible by personal access token",
            }
        ],
    }
    fake = FakeGitHub(graphql_responses=[httpx.Response(200, json=forbidden)])

    with pytest.raises(SourceUnavailable, match="Resource not accessible by personal access token"):
        fetch(fake)


def test_timestamps_are_in_utc():
    [snapshot] = fetch(FakeGitHub([FULL]))

    assert snapshot.created_at.utcoffset() == timedelta(0)
    assert snapshot.recent_commits[0].committed_at == datetime(2026, 11, 10, 19, 2, 11, tzinfo=UTC)
