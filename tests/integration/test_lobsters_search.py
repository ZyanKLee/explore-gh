import httpx

from builders import TODAY


def test_search_returns_ranked_lobsters_stories_with_project_links():
    from github_anti_ai.adapters.lobsters_search import LobstersSearch

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "short_id": "high",
                    "title": "A trending project",
                    "url": "https://project.example",
                    "score": 81,
                    "comment_count": 14,
                    "created_at": "2026-11-13T10:00:00.000-06:00",
                    "short_id_url": "https://lobste.rs/s/high",
                },
                {
                    "short_id": "ask",
                    "title": "A text post",
                    "url": "",
                    "score": 100,
                    "comment_count": 20,
                    "created_at": "2026-11-13T09:00:00.000-06:00",
                    "short_id_url": "https://lobste.rs/s/ask",
                },
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://lobste.rs")

    stories = LobstersSearch(client).discover(TODAY)

    assert requests[0].url.path == "/hottest.json"
    assert [story.id for story in stories] == ["high"]
    assert stories[0].score == 81
    assert stories[0].discussion_url == "https://lobste.rs/s/high"