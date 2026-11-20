"""Candidate source: recently created repos via the GitHub REST search."""

import logging
from datetime import date, timedelta

import httpx

from explore_gh.adapters.github_http import Sleep, send
from explore_gh.application.ports import Clock
from explore_gh.domain.model import Candidate, RepoId

WINDOW_DAYS = 30
MIN_STARS = 50
PAUSE_SECONDS = 2.0  # the search allows 30 requests per minute
PAGE_SIZE = 100  # the most one search page returns

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
                params={"q": query, "sort": "stars", "order": "desc", "per_page": PAGE_SIZE},
            )
            result = response.json()
            report_losses(query, result)
            for item in result["items"]:
                repo = RepoId.parse(item["full_name"])
                found.setdefault(repo, Candidate(repo, stars=item.get("stargazers_count")))
            log.info("Suche %d/%d: %d Kandidaten bisher", index + 1, len(queries), len(found))
        return list(found.values())[:limit]


def report_losses(query: str, result: dict) -> None:
    """Warn when a search returned less than GitHub found: a full page is cut off."""
    day = query.split()[0]
    shown, total = len(result["items"]), result.get("total_count", 0)
    if total > shown:
        log.warning("%s: %d von %d Treffern, %d abgeschnitten", day, shown, total, total - shown)
    if result.get("incomplete_results"):
        log.warning("%s: unvollständig, GitHub brach die Suche ab", day)
