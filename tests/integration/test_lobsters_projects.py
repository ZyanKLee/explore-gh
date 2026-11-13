import httpx

from builders import NOW
from github_anti_ai.adapters.lobsters_projects import LobstersProjectResolver
from github_anti_ai.domain.lobsters import LobstersStory


def test_project_resolver_maps_shared_forge_facts_to_a_lobsters_project():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/v4/projects/owner%2Fproject":
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "html_url": "https://codeberg.org/owner/project",
                "description": "A small open source tool",
                "license": ["MIT"],
                "fork": False,
                "archived": False,
                "size": 15,
                "language": "Rust",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = LobstersStory(
        id="abc",
        title="A project",
        url="https://codeberg.org/owner/project",
        discussion_url="https://lobste.rs/s/abc",
        score=42,
        comments=9,
        created_at=NOW,
    )

    project = LobstersProjectResolver(
        client, resolve_host=lambda host: True
    ).resolve(story)

    assert project is not None
    assert project.story is story
    assert project.repository_url == "https://codeberg.org/owner/project"
    assert project.license_id == "MIT"
    assert project.language == "Rust"
    assert project.is_open_source
    assert len(requests) == 2