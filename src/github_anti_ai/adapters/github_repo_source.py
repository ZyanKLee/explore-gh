"""Repo source: snapshots from GitHub. Facts come from one GraphQL query per batch,
the star history from one REST request per repo. See docs/datensammlung.md."""

import dataclasses
import logging
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import httpx

from github_anti_ai.adapters.github_http import Sleep, send
from github_anti_ai.application.ports import Clock, SourceUnavailable
from github_anti_ai.domain.model import (
    COMMIT_LOOKBACK,
    README_MAX_CHARS,
    STAR_HISTORY_DAYS,
    Commit,
    RepoId,
    Snapshot,
    StarHistory,
)

# the history comes in weeks: the running week plus enough full weeks before it
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
  description
  homepageUrl
  repositoryTopics(first: 20) { nodes { topic { name } } }
  primaryLanguage { name }
  createdAt
  pushedAt
  stargazerCount
  forkCount
  issues(states: OPEN) { totalCount }
  watchers { totalCount }
  pullRequests { totalCount }
  recentIssues: issues(last: 100) { nodes { author { __typename login } } }
  isFork
  isArchived
  isMirror
  isTemplate
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


def _batch_query(size: int) -> str:
    """Repo i of a batch is requested with $owner{i}/$name{i} under the alias r{i}."""
    variables = "".join(f", $owner{i}: String!, $name{i}: String!" for i in range(size))
    repos = "".join(
        f"  r{i}: repository(owner: $owner{i}, name: $name{i}) {{ ...RepoFields }}\n"
        for i in range(size)
    )
    return f"query($since: GitTimestamp!{variables}) {{\n{repos}}}\n{REPO_FIELDS}"


def _timestamp(text: str) -> datetime:
    return datetime.fromisoformat(text)


log = logging.getLogger(__name__)


class _TooExpensive(SourceUnavailable):
    """GitHub refused the query: "Resource limits for this query exceeded"."""


class GitHubRepoSource:
    def __init__(
        self,
        client: httpx.Client,
        *,
        sleep: Sleep,
        clock: Clock,
        batch_size: int = 20,
    ):
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._batch_size = batch_size

    def fetch(
        self, repos: Sequence[RepoId], now: datetime, with_star_history: bool = True
    ) -> list[Snapshot]:
        snapshots = []
        for start in range(0, len(repos), self._batch_size):
            batch = repos[start : start + self._batch_size]
            for node in self._nodes(batch, now):
                snapshots.append(self._snapshot(node, now, with_star_history))
        return snapshots

    def _nodes(self, batch: Sequence[RepoId], now: datetime) -> list[dict]:
        """The GraphQL answers for a group. Repos that do not exist (any more) are left out."""
        variables = {"since": (now - COMMIT_LOOKBACK).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for i, repo in enumerate(batch):
            variables[f"owner{i}"] = repo.owner
            variables[f"name{i}"] = repo.name
        try:
            data = self._query(_batch_query(len(batch)), variables)
        except _TooExpensive:
            if len(batch) == 1:
                log.warning("%s ist GitHub zu aufwendig und wird ausgelassen", batch[0])
                return []
            # GitHub refuses some groups as a whole, halves of them usually pass
            half = len(batch) // 2
            return self._nodes(batch[:half], now) + self._nodes(batch[half:], now)
        nodes = (data.get(f"r{i}") for i in range(len(batch)))
        return [node for node in nodes if node is not None]

    def _query(self, query: str, variables: dict) -> dict:
        response = send(
            self._client,
            "POST",
            "/graphql",
            sleep=self._sleep,
            clock=self._clock,
            json={"query": query, "variables": variables},
        )
        payload = response.json()
        # NOT_FOUND only says that a repo does not exist (any more). Everything else
        # must not pass as a missing repo.
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

    def _snapshot(self, node: dict, now: datetime, with_star_history: bool) -> Snapshot:
        repo = RepoId.parse(node["nameWithOwner"])
        branch = node.get("defaultBranchRef") or {}
        history = (branch.get("target") or {}).get("history") or {}
        tree = node.get("rootTree") or {}
        snapshot = Snapshot(
            repo=repo,
            taken_at=now,
            description=node.get("description") or "",
            homepage=node.get("homepageUrl") or None,
            topics=tuple(n["topic"]["name"] for n in node["repositoryTopics"]["nodes"]),
            primary_language=(node.get("primaryLanguage") or {}).get("name"),
            created_at=_timestamp(node["createdAt"]),
            pushed_at=_timestamp(node["pushedAt"]) if node.get("pushedAt") else None,
            stars=node["stargazerCount"],
            forks=node["forkCount"],
            open_issues=node["issues"]["totalCount"],
            watchers=node["watchers"]["totalCount"],
            pull_requests=node["pullRequests"]["totalCount"],
            recent_issue_authors=_issue_authors(node["recentIssues"]["nodes"]),
            is_fork=node["isFork"],
            is_archived=node["isArchived"],
            is_mirror=node["isMirror"],
            is_template=node["isTemplate"],
            license=(node.get("licenseInfo") or {}).get("spdxId"),
            root_files=tuple(entry["name"] for entry in tree.get("entries", [])),
            readme=_readme(node)[:README_MAX_CHARS],
            recent_commits=tuple(_commit(c) for c in history.get("nodes", [])),
            star_history=StarHistory(daily=()),
        )
        if not with_star_history or snapshot.can_never_be_shown:
            return snapshot  # saves a request, the history could not change its fate
        return dataclasses.replace(snapshot, star_history=self._star_history(repo, now.date()))

    def _star_history(self, repo: RepoId, today: date) -> StarHistory:
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
        return StarHistory(daily=tuple(stars_on.get(day, 0) for day in days))


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
        committed_at=_timestamp(node["committedDate"]),
        author=name,
        is_bot=name.endswith("[bot]"),
        co_authors=tuple(_CO_AUTHOR.findall(node.get("message") or "")),
        headline=node["messageHeadline"],
    )
