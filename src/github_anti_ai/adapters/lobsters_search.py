"""Search Lobsters' hottest stories through its public JSON endpoint."""

from datetime import date, datetime

import httpx

from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.lobsters import LobstersStory


class LobstersSearch:
    name = "lobsters"

    def __init__(self, client: httpx.Client):
        self._client = client

    def discover(self, today: date, limit: int | None = None) -> list[LobstersStory]:
        del today  # hottest.json is a live ranking, not a date query
        try:
            response = self._client.get("/hottest.json")
            response.raise_for_status()
            records = response.json()
            if not isinstance(records, list):
                raise ValueError("JSON-Antwort ist keine Liste")
        except (httpx.HTTPError, ValueError) as error:
            raise SourceUnavailable(f"Lobsters: {error}") from error

        stories = []
        for record in records:
            url = record.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            try:
                created_at = datetime.fromisoformat(record["created_at"])
                story = LobstersStory(
                    id=str(record["short_id"]),
                    title=record["title"],
                    url=url,
                    discussion_url=record.get(
                        "short_id_url", f"https://lobste.rs/s/{record['short_id']}"
                    ),
                    score=int(record.get("score") or 0),
                    comments=int(record.get("comment_count") or 0),
                    created_at=created_at,
                )
            except (KeyError, TypeError, ValueError) as error:
                raise SourceUnavailable(f"Lobsters: ungültiger Story-Treffer: {error}") from error
            stories.append(story)
            if limit is not None and len(stories) >= limit:
                break
        return stories