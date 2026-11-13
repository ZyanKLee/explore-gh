from datetime import timedelta

import httpx

from builders import NOW
from github_anti_ai.adapters.hn_search import HackerNewsSearch
from github_anti_ai.domain.hn import MIN_STORY_POINTS, STORY_WINDOW


def hit(story_id, url, points=60):
    return {
        "objectID": story_id,
        "title": f"Story {story_id}",
        "url": url,
        "points": points,
        "num_comments": 9,
        "created_at_i": int(NOW.timestamp()) - 3600,
    }


def search(hits):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"hits": hits})

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://hn.algolia.com/api/v1"
    )
    return HackerNewsSearch(client).discover(NOW), requests


def test_search_asks_for_all_stories_of_the_last_48_hours_with_at_least_50_points():
    _, requests = search([])

    assert STORY_WINDOW == timedelta(hours=48)
    assert MIN_STORY_POINTS == 50
    since = int((NOW - STORY_WINDOW).timestamp())
    assert requests[0].url.path == "/api/v1/search_by_date"
    assert requests[0].url.params["tags"] == "story"
    assert requests[0].url.params["numericFilters"] == f"created_at_i>{since},points>=50"
    assert requests[0].url.params["hitsPerPage"] == "1000"


def test_search_returns_hn_stories_with_project_links():
    stories, _ = search([hit("story-2", "https://project.example", 42), hit("ask", None, 100)])

    assert [story.id for story in stories] == ["story-2"]
    assert stories[0].points == 42
    assert stories[0].url == "https://project.example"
