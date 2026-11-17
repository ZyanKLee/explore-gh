"""Candidate source: recently created repos via the GitHub REST search."""

import logging
from datetime import date, timedelta

import httpx

from github_anti_ai.adapters.github_http import Sleep, send
from github_anti_ai.application.ports import Clock
from github_anti_ai.domain.model import Candidate, RepoId

WINDOW_DAYS = 30
MIN_STARS = 50
PAUSE_SECONDS = 2.0  # the search allows 30 requests per minute

log = logging.getLogger(__name__)


def discovery_queries(today: date, window_days: int, min_stars: int) -> list[str]:
    """One query per creation day, to stay below the limit of 1000 results per search."""
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
        window_days: int = WINDOW_DAYS,
        min_stars: int = MIN_STARS,
        pause_seconds: float = PAUSE_SECONDS,
    ):
        self._client = client
        self._sleep = sleep
        self._clock = clock
        self._window_days = window_days
        self._min_stars = min_stars
        self._pause_seconds = pause_seconds

    def discover(self, today: date, limit: int | None = None) -> list[Candidate]:
        """Each hit comes with its star count: the collection needs no request for it."""
        found: dict[RepoId, Candidate] = {}
        queries = discovery_queries(today, self._window_days, self._min_stars)
        for index, query in enumerate(queries):
            if limit is not None and len(found) >= limit:
                break
            if index:
                self._sleep(self._pause_seconds)
            response = send(
                self._client,
                "GET",
                "/search/repositories",
                sleep=self._sleep,
                clock=self._clock,
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 100},
            )
            for item in response.json()["items"]:
                repo = RepoId.parse(item["full_name"])
                found.setdefault(repo, Candidate(repo, stars=item.get("stargazers_count")))
            log.info("Suche %d/%d: %d Kandidaten bisher", index + 1, len(queries), len(found))
        return list(found.values())[:limit]
