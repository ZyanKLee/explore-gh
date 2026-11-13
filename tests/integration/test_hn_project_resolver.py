import httpx
import pytest

from builders import NOW
from github_anti_ai.adapters.hn_projects import HnProjectResolver
from github_anti_ai.application.ports import SourceUnavailable
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
        title="Tool: a project",
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


def gitlab_project_with_license(license):
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
                "license": license,
                "forked_from_project": None,
                "archived": False,
                "empty_repo": False,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("123", "Tool: a project", "https://project.example", 42, 9, NOW)
    return HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)


def test_resolver_does_not_call_a_project_open_source_without_a_license():
    project = gitlab_project_with_license(None)

    assert project is not None
    assert project.license_id is None
    assert project.is_open_source is False


def test_resolver_reports_an_unidentified_gitlab_license_file_like_github_does():
    project = gitlab_project_with_license({"key": "other"})

    assert project is not None
    assert project.license_id == "NOASSERTION"
    assert project.is_open_source


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

def github_repo(full_name):
    return httpx.Response(
        200,
        json={
            "full_name": full_name,
            "description": "A repo",
            "language": "Rust",
            "license": {"spdx_id": "MIT"},
            "fork": False,
            "archived": False,
            "size": 10,
        },
    )


def test_resolver_skips_a_repo_without_relation_to_the_story_and_takes_the_next():
    page = (
        '<header><a href="https://github.com/bitbrain/jekyll-dash">Theme on GitHub</a></header>'
        '<a href="https://github.com/alice/tv-ads">Source on GitHub</a>'
    )

    def handler(request):
        if request.url.host == "blog.example":
            return httpx.Response(200, headers={"content-type": "text/html"}, text=page)
        return github_repo(request.url.path.removeprefix("/repos/"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", "Hijacking smart TV ads", "https://blog.example/post", 42, 9, NOW)

    project = HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)

    assert project is not None
    assert project.repository_url == "https://github.com/alice/tv-ads"


def test_resolver_finds_nothing_when_no_repo_on_the_website_relates_to_the_story():
    page = '<footer><a href="https://github.com/bitbrain/jekyll-dash">Theme on GitHub</a></footer>'

    def handler(request):
        if request.url.host == "blog.example":
            return httpx.Response(200, headers={"content-type": "text/html"}, text=page)
        return github_repo(request.url.path.removeprefix("/repos/"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", "How a smoke alarm almost drowned a datacenter",
                    "https://blog.example/post", 42, 9, NOW)

    assert HnProjectResolver(client, resolve_host=lambda host: True).resolve(story) is None


def test_resolver_keeps_a_directly_linked_repo_without_relation_to_the_title():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: github_repo("hyperionaidev/smolmaxxing")
    ))
    story = HnStory("1", "I'm making LLMs work on small and old devices",
                    "https://github.com/hyperionaidev/smolmaxxing/", 42, 9, NOW)

    project = HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)

    assert project is not None
    assert project.repository_url == "https://github.com/hyperionaidev/smolmaxxing"


def blog_with_links(*repos, title="A post"):
    """A blog page linking the given GitHub repos, and a log of every request made."""
    requests = []
    page = "".join(f'<a href="https://github.com/{repo}">Source on GitHub</a>' for repo in repos)

    def handler(request):
        requests.append(request)
        if request.url.host == "blog.example" and not request.url.path.startswith("/api/"):
            return httpx.Response(200, headers={"content-type": "text/html"}, text=page)
        if request.url.host == "api.github.com":
            return github_repo("/".join(request.url.path.split("/")[2:4]))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", title, "https://blog.example/post", 42, 9, NOW)
    resolver = HnProjectResolver(client, resolve_host=lambda host: True)
    return resolver.resolve(story), requests


def test_resolver_takes_the_repo_sharing_the_most_words_with_the_story():
    project, _ = blog_with_links(
        "graphql/graphql-spec",
        "graphql/graphql-over-http",
        title="Announcing the GraphQL over HTTP specification",
    )

    assert project.repository_url == "https://github.com/graphql/graphql-over-http"


def test_resolver_takes_the_first_repo_on_the_page_when_repos_share_as_many_words():
    project, _ = blog_with_links("rust-lang/rust", "rust-lang/cargo", title="Rust 1.100")

    assert project.repository_url == "https://github.com/rust-lang/rust"


def test_resolver_asks_the_forge_only_once_per_repo_and_never_for_unrelated_repos():
    _, requests = blog_with_links(
        "alice/tv-ads/tree/main",
        "alice/tv-ads",
        "alice/tv-ads/blob/main/README.md",
        "bitbrain/jekyll-dash",
        title="Hijacking TV ads",
    )

    github = [request.url.path for request in requests if request.url.host == "api.github.com"]
    assert github == ["/repos/alice/tv-ads", "/repos/alice/tv-ads/readme"]


def news_site_answering_forge_probes_with(answer):
    def handler(request):
        if request.url.host == "news.example" and request.url.path.startswith("/api/"):
            return answer(request)
        if request.url.host == "news.example":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<a href="https://github.com/alice/tv-ads">Source on GitHub</a>',
            )
        return github_repo("alice/tv-ads")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", "Hijacking TV ads", "https://news.example/article/x", 42, 9, NOW)
    return HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)


def test_resolver_reads_the_page_of_a_website_that_refuses_forge_probes():
    project = news_site_answering_forge_probes_with(lambda request: httpx.Response(403))

    assert project.repository_url == "https://github.com/alice/tv-ads"


def test_resolver_reads_the_page_of_a_website_that_fails_on_forge_probes():
    project = news_site_answering_forge_probes_with(lambda request: httpx.Response(503))

    assert project.repository_url == "https://github.com/alice/tv-ads"


def test_resolver_reads_the_page_of_a_website_whose_forge_probes_time_out():
    def time_out(request):
        raise httpx.ReadTimeout("too slow", request=request)

    project = news_site_answering_forge_probes_with(time_out)

    assert project.repository_url == "https://github.com/alice/tv-ads"


def test_resolver_reports_github_refusing_requests_as_source_unavailable():
    def handler(request):
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", "Tool", "https://github.com/alice/tool", 42, 9, NOW)

    with pytest.raises(SourceUnavailable):
        HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)


def resolve_direct(url, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    story = HnStory("1", "Tool", url, 42, 9, NOW)
    return HnProjectResolver(client, resolve_host=lambda host: True).resolve(story)


def test_resolver_reads_topics_and_readme_of_a_github_repo():
    def handler(request):
        if request.url.path == "/repos/alice/tool/readme":
            assert request.headers["accept"] == "application/vnd.github.raw+json"
            return httpx.Response(200, text="# Tool\n\nAn LLM agent.")
        response = github_repo("alice/tool")
        data = response.json() | {"topics": ["llm", "mcp"]}
        return httpx.Response(200, json=data)

    project = resolve_direct("https://github.com/alice/tool", handler)

    assert project.topics == ("llm", "mcp")
    assert project.readme == "# Tool\n\nAn LLM agent."


def test_resolver_keeps_a_github_repo_without_readme():
    def handler(request):
        if request.url.path.endswith("/readme"):
            return httpx.Response(404)
        return github_repo("alice/tool")

    project = resolve_direct("https://github.com/alice/tool", handler)

    assert project.readme == ""
    assert project.topics == ()


def test_resolver_reads_topics_and_readme_of_a_gitlab_project():
    def handler(request):
        if request.url.path == "/group/tool/-/raw/main/README.md":
            return httpx.Response(200, text="# Tool")
        if request.url.path == "/api/v4/projects/1/languages":
            return httpx.Response(200, json={"Rust": 100.0})
        return httpx.Response(200, json={
            "id": 1,
            "web_url": "https://gitlab.example/group/tool",
            "readme_url": "https://gitlab.example/group/tool/-/blob/main/README.md",
            "topics": ["editor"],
            "license": {"key": "mit"},
            "archived": False,
            "empty_repo": False,
        })

    project = resolve_direct("https://gitlab.example/group/tool", handler)

    assert project.topics == ("editor",)
    assert project.readme == "# Tool"


def test_resolver_reads_topics_and_readme_of_a_gitea_repo():
    def handler(request):
        if request.url.path == "/api/v4/projects/owner%2Ftool":
            return httpx.Response(404)
        if request.url.path == "/api/v1/repos/owner/tool/raw/README.md":
            return httpx.Response(200, text="# Tool")
        return httpx.Response(200, json={
            "html_url": "https://codeberg.org/owner/tool",
            "topics": ["editor"],
            "license": ["MIT"],
            "language": "Rust",
            "size": 10,
        })

    project = resolve_direct("https://codeberg.org/owner/tool", handler)

    assert project.topics == ("editor",)
    assert project.readme == "# Tool"


def test_resolver_marks_a_readme_it_could_not_read_as_unknown():
    def handler(request):
        if request.url.path.endswith("/readme"):
            return httpx.Response(503)
        return github_repo("alice/tool")

    project = resolve_direct("https://github.com/alice/tool", handler)

    assert project.readme is None


def test_resolver_marks_a_missing_gitea_readme_md_as_unknown():
    """Gitea is only asked for README.md; the repo may have a README of another name."""
    def handler(request):
        if request.url.path == "/api/v4/projects/owner%2Ftool":
            return httpx.Response(404)
        if request.url.path.endswith("/raw/README.md"):
            return httpx.Response(404)
        return httpx.Response(200, json={
            "html_url": "https://codeberg.org/owner/tool", "license": ["MIT"],
            "language": "Rust", "size": 10,
        })

    project = resolve_direct("https://codeberg.org/owner/tool", handler)

    assert project.readme is None


def test_resolver_notes_whether_the_story_links_the_repo_directly():
    direct = resolve_direct("https://github.com/alice/tool", lambda request: (
        httpx.Response(404) if request.url.path.endswith("/readme") else github_repo("alice/tool")
    ))
    found, _ = blog_with_links("alice/tv-ads", title="Hijacking TV ads")

    assert direct.linked_directly is True
    assert found.linked_directly is False
