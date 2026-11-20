"""Repo source: snapshots from GitHub. See docs/datensammlung.md, "Momentaufnahme".

Facts come from one GraphQL query per batch, the star history from one REST request per repo.
"""

import dataclasses
import logging
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import httpx

from explore_gh.adapters.github_http import GatewayTimeout, Sleep, send
from explore_gh.application.ports import Clock, SourceUnavailable
from explore_gh.domain.model import (
    COMMIT_LOOKBACK,
    README_MAX_CHARS,
    STAR_HISTORY_DAYS,
    Commit,
    RepoId,
    Snapshot,
    StarHistory,
)

# Repos per GraphQL query. With 20, GitHub often gave up after 10 seconds (HTTP 502/504).
BATCH_SIZE = 10
# A batch that times out is halved until the repo to blame is found: about 4 timeouts
# for each such repo. More than this many means GitHub itself is down. Must stay below
# 2 * BATCH_SIZE - 1, the timeouts of a batch in which every query fails.
MAX_TIMEOUTS_PER_BATCH = 10
# The history comes in weeks: the running week plus enough full weeks before it.
STAR_HISTORY_WEEKS = STAR_HISTORY_DAYS // 7 + 1

README_ALIASES = {
    "readmeMd": "README.md",
    "readmeMdLower": "readme.md",
    "readmeRst": "README.rst",
    "readmeTxt": "README.txt",
    "readmePlain": "README",
}

REPO_FIELDS = (
    """
fragment RepoFields on Repository {
  nameWithOwner
  owner {
    __typename
    ... on User {
      createdAt
      repositoriesContributedTo(
        includeUserRepositories: false, contributionTypes: [COMMIT, PULL_REQUEST]
      ) { totalCount }
    }
    ... on Organization { createdAt }
  }
  description
  homepageUrl
  repositoryTopics(first: 20) { nodes { topic { name } } }
  primaryLanguage { name }
  createdAt
  pushedAt
  stargazerCount
  forkCount
  pullRequests { totalCount }
  recentIssues: issues(last: 100) { nodes { author { __typename login } } }
  isFork
  isArchived
  isMirror
  licenseInfo { spdxId }
  rootTree: object(expression: "HEAD:") { ... on Tree { entries { name } } }
"""
    + "".join(
        f'  {alias}: object(expression: "HEAD:{path}") {{ ... on Blob {{ text }} }}\n'
        for alias, path in README_ALIASES.items()
    )
    + """
  defaultBranchRef {
    target {
      ... on Commit {
        history(first: 100, since: $since) {
          nodes { committedDate messageHeadline message author { name user { login } } }
        }
      }
    }
  }
}
"""
)

_CO_AUTHOR = re.compile(r"^co-authored-by:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

log = logging.getLogger(__name__)


class _TooExpensive(SourceUnavailable):
    """GitHub refused the query: "Resource limits for this query exceeded"."""


def batch_query(size: int) -> str:
    """Repo i of a batch is asked for with $owner{i}/$name{i} under the alias r{i}."""
    variables = "".join(f", $owner{i}: String!, $name{i}: String!" for i in range(size))
    repos = "".join(
        f"  r{i}: repository(owner: $owner{i}, name: $name{i}) {{ ...RepoFields }}\n"
        for i in range(size)
    )
    return f"query($since: GitTimestamp!{variables}) {{\n{repos}}}\n{REPO_FIELDS}"


class GitHubRepoSource:
    def __init__(
        self,
        client: httpx.Client,
        *,
        sleep: Sleep,
        clock: Clock,
        batch_size: int = BATCH_SIZE,
        max_timeouts_per_batch: int = MAX_TIMEOUTS_PER_BATCH,
    ):
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._batch_size = batch_size
        self._max_timeouts_per_batch = max_timeouts_per_batch
        self._timeouts = 0

    def fetch(
        self, repos: Sequence[RepoId], now: datetime, with_star_history: bool = True
    ) -> list[Snapshot]:
        snapshots = []
        for start in range(0, len(repos), self._batch_size):
            self._timeouts = 0
            for node in self._nodes(repos[start : start + self._batch_size], now):
                snapshot = _snapshot(node, now)
                if with_star_history and not snapshot.can_never_be_shown:
                    # a repo that can never be shown saves the request
                    history = self._star_history(snapshot.repo, now.date())
                    snapshot = dataclasses.replace(snapshot, star_history=history)
                snapshots.append(snapshot)
        return snapshots

    def _nodes(self, batch: Sequence[RepoId], now: datetime) -> list[dict]:
        """The GraphQL answers for a batch. Repos that do not exist (any more) are left out."""
        variables = {"since": (now - COMMIT_LOOKBACK).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for i, repo in enumerate(batch):
            variables[f"owner{i}"] = repo.owner
            variables[f"name{i}"] = repo.name
        try:
            # a batch that timed out is not asked again as it is, only a single repo is
            data = self._query(batch_query(len(batch)), variables, retry_timeouts=len(batch) == 1)
        except (_TooExpensive, GatewayTimeout) as error:
            if isinstance(error, GatewayTimeout):
                self._timeouts += 1
                if self._timeouts > self._max_timeouts_per_batch:
                    raise
            if len(batch) == 1:
                log.warning("%s ist GitHub zu aufwendig und wird ausgelassen", batch[0])
                return []
            # GitHub refuses some batches as a whole, halves of them usually pass
            log.info("Gruppe von %d Repos wird geteilt: %s", len(batch), error)
            half = len(batch) // 2
            return self._nodes(batch[:half], now) + self._nodes(batch[half:], now)
        nodes = (data.get(f"r{i}") for i in range(len(batch)))
        return [node for node in nodes if node is not None]

    def _query(self, query: str, variables: dict, *, retry_timeouts: bool) -> dict:
        response = send(
            self._client,
            "POST",
            "/graphql",
            sleep=self._sleep,
            clock=self._clock,
            retry_timeouts=retry_timeouts,
            json={"query": query, "variables": variables},
        )
        payload = response.json()
        # NOT_FOUND only says that a repo does not exist (any more). Any other error must
        # not pass as a missing repo, even if data comes along.
        errors = [e for e in payload.get("errors") or [] if e.get("type") != "NOT_FOUND"]
        if any(
            e.get("type") == "RESOURCE_LIMITS_EXCEEDED"
            or "resource limits" in e.get("message", "").lower()
            for e in errors
        ):
            raise _TooExpensive("GraphQL: Resource limits for this query exceeded.")
        if errors or payload.get("data") is None:
            messages = sorted({e.get("message", "?") for e in errors})
            raise SourceUnavailable(f"GraphQL: {'; '.join(messages) or 'keine Daten'}")
        return payload["data"]

    def _star_history(self, repo: RepoId, today: date) -> StarHistory:
        """New stars of the last 35 days. Weeks come newest first, each from its Sunday."""
        response = send(
            self._client,
            "GET",
            f"/repos/{repo}/stargazers/history",
            sleep=self._sleep,
            clock=self._clock,
            params={"per_page": STAR_HISTORY_WEEKS},
        )
        stars_on: dict[date, int] = {}
        for week in response.json():
            sunday = datetime.fromtimestamp(week["week"], UTC).date()
            for offset, stars in enumerate(week["days"]):
                stars_on[sunday + timedelta(days=offset)] = stars
        days = (today - timedelta(days=back) for back in reversed(range(STAR_HISTORY_DAYS)))
        return StarHistory(tuple(stars_on.get(day, 0) for day in days))


def _snapshot(node: dict, now: datetime) -> Snapshot:
    """The facts of a GraphQL node, with an empty star history."""
    branch = node.get("defaultBranchRef") or {}
    history = (branch.get("target") or {}).get("history") or {}
    tree = node.get("rootTree") or {}
    owner = node.get("owner") or {}
    return Snapshot(
        repo=RepoId.parse(node["nameWithOwner"]),
        taken_at=now,
        description=node.get("description") or "",
        homepage=node.get("homepageUrl") or None,
        topics=tuple(n["topic"]["name"] for n in node["repositoryTopics"]["nodes"]),
        primary_language=(node.get("primaryLanguage") or {}).get("name"),
        created_at=_time(node["createdAt"]),
        pushed_at=_time(node["pushedAt"]) if node.get("pushedAt") else None,
        stars=node["stargazerCount"],
        forks=node["forkCount"],
        pull_requests=node["pullRequests"]["totalCount"],
        recent_issue_authors=_issue_authors(node["recentIssues"]["nodes"]),
        is_fork=node["isFork"],
        is_archived=node["isArchived"],
        is_mirror=node["isMirror"],
        license=(node.get("licenseInfo") or {}).get("spdxId"),
        root_files=tuple(entry["name"] for entry in tree.get("entries", [])),
        readme=_readme(node)[:README_MAX_CHARS],
        recent_commits=tuple(_commit(c) for c in history.get("nodes", [])),
        star_history=StarHistory(()),
        owner_created_at=_time(owner["createdAt"]) if owner.get("createdAt") else None,
        owner_contributed_to=(owner.get("repositoriesContributedTo") or {}).get("totalCount"),
    )


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _readme(node: dict) -> str:
    for alias in README_ALIASES:
        blob = node.get(alias)
        if blob and blob.get("text") is not None:
            return blob["text"]
    return ""


def _issue_authors(issues: list[dict]) -> int:
    """Distinct people (no bots, no deleted accounts) among the authors."""
    authors = (issue.get("author") for issue in issues)
    return len({a["login"] for a in authors if a and a.get("__typename") != "Bot"})


def _commit(node: dict) -> Commit:
    author = node.get("author") or {}
    name = (author.get("user") or {}).get("login") or author.get("name") or ""
    return Commit(
        committed_at=_time(node["committedDate"]),
        author=name,
        is_bot=name.endswith("[bot]"),
        co_authors=tuple(_CO_AUTHOR.findall(node.get("message") or "")),
        headline=node["messageHeadline"],
    )
