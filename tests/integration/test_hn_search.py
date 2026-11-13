import httpx

from builders import TODAY


def test_search_returns_ranked_hn_stories_with_project_links():
    from github_anti_ai.adapters.hn_search import HackerNewsSearch

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "objectID": "story-2",
                        "title": "A project",
                        "url": "https://project.example",
                        "points": 42,
                        "num_comments": 9,
                        "created_at_i": 1794528000,
                    },
                    {
                        "objectID": "story-1",
                        "title": "Ask HN",
                        "url": None,
                        "points": 100,
                        "num_comments": 20,
                        "created_at_i": 1794527000,
                    },
                ]
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://hn.algolia.com/api/v1"
    )

    stories = HackerNewsSearch(client).discover(TODAY)

    assert requests[0].url.path == "/api/v1/search"
    assert requests[0].url.params["tags"] == "front_page"
    assert [story.id for story in stories] == ["story-2"]
    assert stories[0].points == 42
    assert stories[0].url == "https://project.example"