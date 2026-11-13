from datetime import timedelta

import httpx

from builders import NOW
from github_anti_ai.adapters.lobsters_search import LobstersSearch
from github_anti_ai.domain.lobsters import HOTTEST_PAGES, SHOW_WINDOW


def record(short_id, url="https://project.example", age=timedelta(hours=3), score=81):
    return {
        "short_id": short_id,
        "title": f"Story {short_id}",
        "url": url,
        "score": score,
        "comment_count": 14,
        "created_at": (NOW - age).isoformat(),
        "short_id_url": f"https://lobste.rs/s/{short_id}",
    }


def search(pages):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=pages.get(request.url.path, []))

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://lobste.rs")
    return LobstersSearch(client).discover(NOW), requests


def test_search_reads_two_hottest_pages_and_the_show_tag():
    _, requests = search({})

    assert HOTTEST_PAGES == 2
    assert requests == ["/hottest.json", "/page/2.json", "/t/show.json"]


def test_search_returns_lobsters_stories_with_project_links():
    stories, _ = search({"/hottest.json": [record("high"), record("ask", url="")]})

    assert [story.id for story in stories] == ["high"]
    assert stories[0].score == 81
    assert stories[0].discussion_url == "https://lobste.rs/s/high"


def test_search_returns_a_story_on_several_pages_once():
    stories, _ = search({
        "/hottest.json": [record("a")],
        "/page/2.json": [record("a"), record("b")],
        "/t/show.json": [record("b")],
    })

    assert [story.id for story in stories] == ["a", "b"]


def test_search_takes_show_stories_of_the_last_7_days_only():
    assert SHOW_WINDOW == timedelta(days=7)

    stories, _ = search({
        "/t/show.json": [
            record("recent", age=timedelta(days=6)),
            record("old", age=timedelta(days=8)),
        ],
    })

    assert [story.id for story in stories] == ["recent"]
