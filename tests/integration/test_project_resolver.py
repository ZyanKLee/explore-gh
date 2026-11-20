import httpx
import pytest
from builders import make_story
from http_fakes import FakeWeb

from explore_gh.adapters.project_resolver import ProjectResolver, repository_root
from explore_gh.application.ports import SourceUnavailable

GITHUB_REPO = {
    "full_name": "alice/tiny-editor", "description": "A tiny editor", "language": "Rust",
    "license": {"spdx_id": "MIT"}, "fork": False, "archived": False, "size": 120,
    "topics": ["editor", "tui"],
}  # fmt: skip


def html(*links):
    body = "".join(f'<a href="{href}">{text}</a>' for href, text in links)
    return httpx.Response(200, html=f"<html><body>{body}</body></html>")


def resolve(web, story):
    with web.client() as client:
        return ProjectResolver(
            client, is_public_host=lambda host: not host.endswith(".internal")
        ).resolve(story)


def github_routes(name="alice/tiny-editor", repo=GITHUB_REPO, readme="# Tiny\n"):
    return {
        f"api.github.com/repos/{name}": httpx.Response(200, json={**repo, "full_name": name}),
        f"api.github.com/repos/{name}/readme": httpx.Response(200, text=readme),
    }


def test_a_story_linking_a_github_repo_gives_its_project():
    web = FakeWeb(github_routes())

    project = resolve(web, make_story(url="https://github.com/alice/tiny-editor/tree/main/src"))

    assert project.repository_url == "https://github.com/alice/tiny-editor"
    assert project.linked_directly
    assert (project.language, project.license_id, project.has_code) == ("Rust", "MIT", True)
    assert project.topics == ("editor", "tui")
    assert project.readme == "# Tiny\n"


def test_a_github_repo_without_readme_has_an_empty_one():
    web = FakeWeb(github_routes())
    del web.routes["api.github.com/repos/alice/tiny-editor/readme"]

    assert resolve(web, make_story(url="https://github.com/alice/tiny-editor")).readme == ""


def test_a_readme_that_cannot_be_read_is_unknown():
    web = FakeWeb(
        {**github_routes(), "api.github.com/repos/alice/tiny-editor/readme": httpx.Response(500)}
    )

    assert resolve(web, make_story(url="https://github.com/alice/tiny-editor")).readme is None


def test_github_refusing_requests_makes_the_source_unavailable():
    web = FakeWeb({"api.github.com/repos/alice/tiny-editor": httpx.Response(403)})

    with pytest.raises(SourceUnavailable):
        resolve(web, make_story(url="https://github.com/alice/tiny-editor"))


def test_follows_a_website_to_a_related_repo():
    web = FakeWeb(
        {
            "tiny-editor.example.org/": html(("https://github.com/alice/tiny-editor", "Source")),
            **github_routes(),
        }
    )

    project = resolve(
        web, make_story(title="Tiny Editor 1.0", url="https://tiny-editor.example.org/")
    )

    assert project.repository_url == "https://github.com/alice/tiny-editor"
    assert not project.linked_directly
    assert project.project_url == "https://tiny-editor.example.org/"


def test_skips_repos_without_relation_and_never_asks_the_forge_for_them():
    web = FakeWeb(
        {
            "example.org/post": html(
                ("https://github.com/bitbrain/jekyll-dash", "Theme on GitHub"),
                ("https://github.com/alice/tiny-editor", "Source"),
            ),
            **github_routes(),
        }
    )

    project = resolve(web, make_story(title="Tiny Editor released", url="https://example.org/post"))

    assert project.repository_url == "https://github.com/alice/tiny-editor"
    assert not any("jekyll" in path for path in web.paths)


def test_finds_nothing_when_no_repo_relates_to_the_story():
    web = FakeWeb({"example.org/post": html(("https://github.com/bitbrain/jekyll-dash", "GitHub"))})

    assert resolve(web, make_story(title="A data center", url="https://example.org/post")) is None


def test_takes_the_repo_sharing_the_most_words_and_on_a_tie_the_first():
    web = FakeWeb(
        {
            "graphql.org/blog": html(
                ("https://github.com/graphql/graphql-spec", "GitHub"),
                ("https://github.com/graphql/graphql-over-http", "GitHub"),
                ("https://github.com/graphql/graphql-over-https", "GitHub"),
            ),
            **github_routes("graphql/graphql-spec"),
            **github_routes("graphql/graphql-over-http"),
            **github_routes("graphql/graphql-over-https"),
        }
    )

    project = resolve(web, make_story(title="GraphQL over HTTP", url="https://graphql.org/blog"))

    assert project.repository_url == "https://github.com/graphql/graphql-over-http"


def test_follows_a_gitlab_project_and_reads_its_facts():
    project_json = {
        "id": 7, "web_url": "https://gitlab.com/alice/tiny-editor", "description": "Editor",
        "license": {"key": "other"}, "archived": False, "topics": ["editor"],
        "readme_url": "https://gitlab.com/alice/tiny-editor/-/blob/main/README.md",
    }  # fmt: skip
    web = FakeWeb(
        {
            "gitlab.com/api/v4/projects/alice%2Ftiny-editor": httpx.Response(
                200, json=project_json
            ),
            "gitlab.com/api/v4/projects/7/languages": httpx.Response(
                200, json={"C": 20, "Rust": 80}
            ),
            "gitlab.com/alice/tiny-editor/-/raw/main/README.md": httpx.Response(200, text="Readme"),
        }
    )

    project = resolve(web, make_story(url="https://gitlab.com/alice/tiny-editor"))

    assert project.repository_url == "https://gitlab.com/alice/tiny-editor"
    assert (project.language, project.license_id, project.has_code) == ("Rust", "NOASSERTION", True)
    assert (project.topics, project.readme) == (("editor",), "Readme")


def test_follows_a_gitea_repo_whose_readme_may_have_another_name():
    repo = {
        "html_url": "https://codeberg.org/alice/tiny", "description": "Editor", "language": "Go",
        "license": ["GPL-3.0-or-later"], "size": 50, "topics": [],
    }  # fmt: skip
    web = FakeWeb({"codeberg.org/api/v1/repos/alice/tiny": httpx.Response(200, json=repo)})

    project = resolve(web, make_story(url="https://codeberg.org/alice/tiny/src/branch/main"))

    assert (project.repository_url, project.license_id) == (
        "https://codeberg.org/alice/tiny",
        "GPL-3.0-or-later",
    )
    assert project.readme is None


def test_a_project_without_license_has_none():
    web = FakeWeb(github_routes(repo={**GITHUB_REPO, "license": None}))

    assert resolve(web, make_story(url="https://github.com/alice/tiny-editor")).license_id is None


@pytest.mark.parametrize("answer", [httpx.Response(403), httpx.Response(500)])
def test_a_website_that_fails_on_forge_probes_is_read_as_a_page(answer):
    web = FakeWeb(
        {
            "news.example.org/api/v4/projects/a%2Ftiny-editor": answer,
            "news.example.org/api/v1/repos/a/tiny-editor": answer,
            "news.example.org/a/tiny-editor": html(
                ("https://github.com/alice/tiny-editor", "Source")
            ),
            **github_routes(),
        }
    )

    project = resolve(
        web, make_story(title="Tiny editor", url="https://news.example.org/a/tiny-editor")
    )

    assert project.repository_url == "https://github.com/alice/tiny-editor"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/x",
        "http://10.0.0.1/a/b",
        "https://host.internal/a/b",
        "https://x.org:8080/a/b",
    ],
)
def test_never_asks_private_addresses_or_odd_ports(url):
    web = FakeWeb()

    assert resolve(web, make_story(url=url)) is None
    assert web.requests == []


def test_does_not_follow_a_redirect_to_a_private_address():
    web = FakeWeb(
        {"tiny.example.org/": httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})}
    )

    assert resolve(web, make_story(url="https://tiny.example.org/")) is None
    assert web.paths[-1] == "tiny.example.org/"


@pytest.mark.parametrize(
    "url, root",
    [
        ("https://github.com/a/tool/blob/main/x.py", "https://github.com/a/tool"),
        (
            "https://gitlab.example/group/sub/tool/-/tree/main",
            "https://gitlab.example/group/sub/tool",
        ),
        ("https://codeberg.org/a/tool.git", "https://codeberg.org/a/tool"),
    ],
)
def test_links_into_a_repo_name_the_repo(url, root):
    assert repository_root(url) == root


# --- Links in the first post (forums list) ---


def test_a_related_repo_in_the_text_of_the_first_post_gives_its_project():
    web = FakeWeb(github_routes())
    story = make_story(
        title="Tiny Editor 2.0 is out",
        url="",
        links=("https://github.com/alice/tiny-editor/releases",),
    )

    project = resolve(web, story)

    assert project.repository_url == "https://github.com/alice/tiny-editor"
    assert project.found_in_post
    assert not project.linked_directly
    assert project.project_url == "https://github.com/alice/tiny-editor"


def test_a_repo_in_the_text_without_relation_to_the_story_is_never_asked():
    web = FakeWeb(github_routes("tokio-rs/tokio"))
    story = make_story(
        title="My week in review", url="", links=("https://github.com/tokio-rs/tokio",)
    )

    assert resolve(web, story) is None
    assert web.paths == []


def test_the_text_counts_when_the_linked_website_names_no_repo():
    web = FakeWeb({"example.org/post": html(), **github_routes()})
    story = make_story(
        title="Tiny Editor released",
        url="https://example.org/post",
        links=("https://github.com/alice/tiny-editor",),
    )

    project = resolve(web, story)

    assert project.found_in_post
    assert project.project_url == "https://example.org/post"


def test_links_in_the_text_to_hosts_that_are_no_forge_are_not_followed():
    web = FakeWeb()
    story = make_story(title="Tiny editor", url="", links=("https://tiny-editor.example.org/x/y",))

    assert resolve(web, story) is None
    assert web.paths == []
