import httpx

from builders import NOW
from github_anti_ai.adapters.hn_projects import HnProjectResolver
from github_anti_ai.domain.hn import HnStory


def test_resolver_follows_project_site_to_a_public_licensed_gitlab_repository():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "project.example":
            return httpx.Response(302, headers={"location": "https://www.project.example/"})
        if request.url.host == "www.project.example":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    '<a href="https://gitlab.example/group/tool" '
                    'rel="codeRepository">Source</a>'
                ),
            )
        if request.url.path == "/api/v4/projects/1/languages":
            return httpx.Response(200, json={"Rust": 100.0})
        assert request.url.raw_path == b"/api/v4/projects/group%2Ftool"
        return httpx.Response(
            200,
            json={
                "web_url": "https://gitlab.example/group/tool",
                "id": 1,
                "description": "A useful open source project",
                "license": {"key": "mit"},
                "forked_from_project": None,
                "archived": False,
                "empty_repo": False,
                "star_count": 20,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory(
        id="123",
        title="A project",
        url="https://project.example",
        points=42,
        comments=9,
        created_at=NOW,
    )

    project = HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)

    assert project is not None
    assert project.repository_url == "https://gitlab.example/group/tool"
    assert project.license_id == "MIT"
    assert project.is_open_source
    assert project.has_code
    assert project.language == "Rust"
    assert len(requests) == 4


def test_resolver_does_not_call_a_project_open_source_without_an_approved_license():
    def handler(request):
        if request.url.host == "project.example":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<a rel="codeRepository" href="https://gitlab.example/group/tool">Source</a>',
            )
        return httpx.Response(
            200,
            json={
                "web_url": "https://gitlab.example/group/tool",
                "license": {"key": "other"},
                "forked_from_project": None,
                "archived": False,
                "empty_repo": False,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("123", "A project", "https://project.example", 42, 9, NOW)

    project = HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)

    assert project is not None
    assert project.is_open_source is False


def test_resolver_does_not_follow_a_project_redirect_to_a_private_address():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("123", "A project", "https://project.example", 42, 9, NOW)

    project = HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)

    assert project is None
    assert len(requests) == 1