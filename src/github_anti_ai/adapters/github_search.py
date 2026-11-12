"""Candidate source: recently created repos via the GitHub REST search."""

import logging
from datetime import date, timedelta

import httpx

from github_anti_ai.adapters.github_http import Sleep, send
from github_anti_ai.application.ports import Clock
from github_anti_ai.domain.model import RepoId

log = logging.getLogger(__name__)


def build_discovery_queries(today: date, window_days: int, min_stars: int) -> list[str]:
    """One query per creation day, to stay below the 1000 results limit of a search."""
    return [
        f"created:{today - timedelta(days=offset)} stars:>={min_stars} fork:false archived:false"
        for offset in range(window_days)
    ]


class GitHubSearchCandidates:
    name = "github-search"

    def __init__(
        self,
        client: httpx.Client,
        *,
        sleep: Sleep,
        clock: Clock,
        window_days: int = 30,
        min_stars: int = 50,
        pause_seconds: float = 2.0,
    ):
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._window_days = window_days
        self._min_stars = min_stars
        self._pause_seconds = pause_seconds

    def discover(self, today: date, limit: int | None = None) -> list[RepoId]:
        found: dict[RepoId, None] = {}
        queries = build_discovery_queries(today, self._window_days, self._min_stars)
        for index, query in enumerate(queries):
            if limit is not None and len(found) >= limit:
                break
            if index:
                self._sleep(self._pause_seconds)  # search allows 30 requests per minute
            response = send(
                self._client,
                "GET",
                "/search/repositories",
                sleep=self._sleep,
                clock=self._clock,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 100},
            )
            for item in response.json()["items"]:
                found.setdefault(RepoId.parse(item["full_name"]), None)
            log.info("Suche %d/%d: %d Kandidaten bisher", index + 1, len(queries), len(found))
        return list(found)[:limit]
