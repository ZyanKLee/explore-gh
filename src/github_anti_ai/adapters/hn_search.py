"""Search recent Hacker News stories through the Algolia HN API."""

from datetime import UTC, datetime

import httpx

from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.hn import MIN_STORY_POINTS, STORY_WINDOW, HnStory

MAX_HITS = 1000  # the most Algolia returns for one query


class HackerNewsSearch:
    name = "hacker-news"

    def __init__(self, client: httpx.Client):
        self._client = client

    def discover(self, now: datetime, limit: int | None = None) -> list[HnStory]:
        """All stories of the last 48 hours with at least 50 points, newest first."""
        since = int((now - STORY_WINDOW).timestamp())
        params = {
            "tags": "story",
            "numericFilters": f"created_at_i>{since},points>={MIN_STORY_POINTS}",
            "hitsPerPage": MAX_HITS,
        }
        try:
            response = self._client.get("/search_by_date", params=params)
            response.raise_for_status()
            hits = response.json()["hits"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SourceUnavailable(f"Hacker News: {error}") from error

        stories = []
        for hit in hits:
            url = hit.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            try:
                story = HnStory(
                    id=str(hit["objectID"]),
                    title=hit["title"],
                    url=url,
                    points=int(hit.get("points") or 0),
                    comments=int(hit.get("num_comments") or 0),
                    created_at=datetime.fromtimestamp(int(hit["created_at_i"]), UTC),
                )
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                raise SourceUnavailable(f"Hacker News: ungültiger Story-Treffer: {error}") from error
            stories.append(story)
            if limit is not None and len(stories) >= limit:
                break
        return stories