from datetime import UTC, timedelta

import httpx
import pytest
from builders import NOW
from http_fakes import FakeWeb

from github_anti_ai.adapters.story_sources import (
    HN_API_URL,
    LOBSTERS_URL,
    HackerNewsSearch,
    LobstersSearch,
)
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


def record(id, created_at=NOW - timedelta(hours=3), url="https://example.org/tool"):
    return {
        "short_id": id, "short_id_url": f"https://lobste.rs/s/{id}", "title": f"Story {id}",
        "url": url, "score": 20, "comment_count": 4, "created_at": created_at.isoformat(),
    }  # fmt: skip


def lobsters(web, limit=None):
    with web.client(base_url=LOBSTERS_URL) as client:
        return LobstersSearch(client).discover(NOW, limit)


class TestLobsters:
    def routes(self, hottest=(), page2=(), show=()):
        return {
            "lobste.rs/hottest.json": httpx.Response(200, json=list(hottest)),
            "lobste.rs/page/2.json": httpx.Response(200, json=list(page2)),
            "lobste.rs/t/show.json": httpx.Response(200, json=list(show)),
        }

    def test_reads_two_hottest_pages_and_the_show_tag(self):
        web = FakeWeb(self.routes([record("a")], [record("b")], [record("c")]))

        stories = lobsters(web)

        assert [s.id for s in stories] == ["a", "b", "c"]
        assert web.paths == [
            "lobste.rs/hottest.json",
            "lobste.rs/page/2.json",
            "lobste.rs/t/show.json",
        ]
        assert stories[0].discussion_url == "https://lobste.rs/s/a"
        assert (stories[0].points, stories[0].comments) == (20, 4)

    def test_a_story_on_several_pages_counts_once(self):
        assert [
            s.id
            for s in lobsters(FakeWeb(self.routes([record("a")], [record("a")], [record("a")])))
        ] == ["a"]

    def test_show_stories_count_for_7_days(self):
        web = FakeWeb(
            self.routes(
                show=[
                    record("new", NOW - timedelta(days=6)),
                    record("old", NOW - timedelta(days=8)),
                ]
            )
        )

        assert [s.id for s in lobsters(web)] == ["new"]

    def test_stories_without_link_are_left_out(self):
        assert lobsters(FakeWeb(self.routes([record("a", url="")]))) == []
