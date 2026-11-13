"""Search Lobsters' hottest and show stories through its public JSON endpoints."""

from datetime import datetime

import httpx

from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.lobsters import HOTTEST_PAGES, SHOW_WINDOW, LobstersStory


class LobstersSearch:
    name = "lobsters"

    def __init__(self, client: httpx.Client):
        self._client = client

    def discover(self, now: datetime, limit: int | None = None) -> list[LobstersStory]:
        """The first hottest pages, then the show stories of the last 7 days. Each story once."""
        hottest = ["/hottest.json"] + [f"/page/{page}.json" for page in range(2, HOTTEST_PAGES + 1)]
        stories: dict[str, LobstersStory] = {}
        for path in hottest:
            for story in self._stories(path):
                stories.setdefault(story.id, story)
        for story in self._stories("/t/show.json"):
            if story.created_at >= now - SHOW_WINDOW:
                stories.setdefault(story.id, story)
        found = list(stories.values())
        return found if limit is None else found[:limit]

    def _stories(self, path: str) -> list[LobstersStory]:
        try:
            response = self._client.get(path)
            response.raise_for_status()
            records = response.json()
            if not isinstance(records, list):
                raise ValueError("JSON-Antwort ist keine Liste")
        except (httpx.HTTPError, ValueError) as error:
            raise SourceUnavailable(f"Lobsters {path}: {error}") from error

        stories = []
        for record in records:
            url = record.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            try:
                stories.append(
                    LobstersStory(
                        id=str(record["short_id"]),
                        title=record["title"],
                        url=url,
                        discussion_url=record.get(
                            "short_id_url", f"https://lobste.rs/s/{record['short_id']}"
                        ),
                        score=int(record.get("score") or 0),
                        comments=int(record.get("comment_count") or 0),
                        created_at=datetime.fromisoformat(record["created_at"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise SourceUnavailable(f"Lobsters: ungültiger Story-Treffer: {error}") from error
        return stories
