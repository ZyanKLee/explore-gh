from datetime import UTC, timedelta

import httpx
import pytest
from builders import NOW
from http_fakes import FakeWeb

from github_anti_ai.adapters.story_sources import HN_API_URL, HackerNewsSearch
from github_anti_ai.application.ports import SourceUnavailable


def hit(id, url="https://example.org/tool", points=120, comments=30):
    return {
        "objectID": id, "title": f"Story {id}", "url": url, "points": points,
        "num_comments": comments, "created_at_i": int((NOW - timedelta(hours=3)).timestamp()),
    }  # fmt: skip


def hn(web, limit=None):
    with web.client(base_url=HN_API_URL) as client:
        return HackerNewsSearch(client).discover(NOW, limit)


class TestHackerNews:
    def test_asks_for_the_stories_of_48_hours_with_at_least_50_points(self):
        web = FakeWeb(
            {"hn.algolia.com/api/v1/search_by_date": httpx.Response(200, json={"hits": []})}
        )

        hn(web)

        params = web.requests[0].url.params
        since = int((NOW - timedelta(hours=48)).timestamp())
        assert params["tags"] == "story"
        assert params["numericFilters"] == f"created_at_i>{since},points>=50"

    def test_returns_stories_with_links_and_their_discussion(self):
        hits = [hit("1"), hit("2", url=None), hit("3", url="ftp://x")]
        web = FakeWeb(
            {"hn.algolia.com/api/v1/search_by_date": httpx.Response(200, json={"hits": hits})}
        )

        (story,) = hn(web)

        assert (story.id, story.points, story.comments) == ("1", 120, 30)
        assert story.discussion_url == "https://news.ycombinator.com/item?id=1"
        assert story.created_at.tzinfo is UTC

    def test_a_failing_api_makes_the_source_unavailable(self):
        with pytest.raises(SourceUnavailable):
            hn(FakeWeb({"hn.algolia.com/api/v1/search_by_date": httpx.Response(500)}))
