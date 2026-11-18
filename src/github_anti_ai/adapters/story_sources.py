"""Where the HN stories come from: the Algolia HN API.

The forums list has its own sources (forum_sources.py). See docs/community.md, "Storys".
"""

from datetime import UTC, datetime

import httpx

from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.community import (
    HN,
    HN_MIN_STORY_POINTS,
    HN_STORY_WINDOW,
    Story,
)

HN_API_URL = "https://hn.algolia.com/api/v1"
MAX_HN_HITS = 1000  # the most Algolia returns for one query


def _is_web_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


class HackerNewsSearch:
    def __init__(self, client: httpx.Client):
        """`client` has HN_API_URL as its base."""
        self._client = client

    def discover(self, now: datetime, limit: int | None = None) -> list[Story]:
        """All stories of the last 48 hours with at least 50 points, newest first.

        Ask HN and other stories without a link are left out.
        """
        since = int((now - HN_STORY_WINDOW).timestamp())
        params = {
            "tags": "story",
            "numericFilters": f"created_at_i>{since},points>={HN_MIN_STORY_POINTS}",
            "hitsPerPage": MAX_HN_HITS,
        }
        try:
            response = self._client.get("/search_by_date", params=params)
            response.raise_for_status()
            hits = response.json()["hits"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SourceUnavailable(f"Hacker News: {error}") from error

        stories = []
        for hit in hits:
            if not _is_web_url(hit.get("url")):
                continue
            try:
                story_id = str(hit["objectID"])
                stories.append(
                    Story(
                        id=story_id,
                        title=hit["title"],
                        url=hit["url"],
                        discussion_url=HN.discussion_url(story_id),
                        points=int(hit.get("points") or 0),
                        comments=int(hit.get("num_comments") or 0),
                        created_at=datetime.fromtimestamp(int(hit["created_at_i"]), UTC),
                    )
                )
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                raise SourceUnavailable(f"Hacker News: ungültiger Treffer: {error}") from error
            if limit is not None and len(stories) >= limit:
                break
        return stories
