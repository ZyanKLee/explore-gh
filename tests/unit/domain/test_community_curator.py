from datetime import timedelta

import pytest
from builders import NOW, TODAY, make_project, make_story

from github_anti_ai.domain.community import (
    HN,
    LOBSTERS,
    CommunityCurator,
    CommunityEdition,
    is_open_source_license,
    repository_key,
)

curator = CommunityCurator()


def curate(*candidates, past=()):
    return curator.curate(HN, TODAY, candidates, past)


def urls(projects):
    return [project.repository_url for project in projects]


def project(name, points=100, comments=10, **overrides):
    overrides.setdefault("description", f"A tool called {name}")
    return make_project(
        f"https://github.com/{name}",
        story=make_story(name, points=points, comments=comments),
        **overrides,
    )


def test_the_platform_points_decide_the_rank():
    edition = curate(project("a/low", points=60, language="Go"), project("b/high", points=300))

    assert urls(edition.main) == ["https://github.com/b/high", "https://github.com/a/low"]


def test_on_a_tie_comments_then_the_newer_story_win():
    older = make_story("1", points=100, comments=5, created_at=NOW - timedelta(hours=9))
    newer = make_story("2", points=100, comments=5, created_at=NOW - timedelta(hours=1))
    edition = curate(
        project("a/x", points=100, comments=5, language="Go"),
        project("b/x", points=100, comments=50, language="C"),
        make_project("https://github.com/c/old", story=older, language="Zig"),
        make_project("https://github.com/d/new", story=newer, language="Lua"),
    )

    assert urls(edition.main)[0] == "https://github.com/b/x"
    assert urls(edition.main).index("https://github.com/d/new") < urls(edition.main).index(
        "https://github.com/c/old"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"license_id": None},
        {"license_id": "BUSL-1.1"},
        {"has_code": False},
        {"is_fork": True},
        {"is_archived": True},
        {"description": "A curated list of editors"},
        {"readme": ""},
        {"description": "A Bitcoin wallet"},
    ],
)
def test_only_open_source_projects_with_code_and_without_github_exclusions_stay(overrides):
    assert curate(project("a/x", **overrides)).main == ()


def test_an_unreadable_readme_is_no_reason_to_exclude():
    assert len(curate(project("a/x", readme=None)).main) == 1


def test_an_unrecognized_license_file_counts_as_open_source_and_says_so():
    (chosen,) = curate(project("a/x", license_id="NOASSERTION")).main

    assert (
        "Lizenzdatei vorhanden, die die Forge nicht erkennt. Zählt als Open Source."
        in chosen.reasons
    )


def test_a_repo_linked_by_two_stories_counts_once_with_the_better_story():
    edition = curate(
        project("a/x", points=80),
        make_project("https://github.com/A/X/", story=make_story("9", points=300)),
    )

    assert len(edition.main) == 1
    assert edition.main[0].story.points == 300


def test_ai_projects_go_to_the_ai_section():
    edition = curate(
        project("a/llm-chat", description="A chatbot"), project("b/editor", language="Go")
    )

    assert urls(edition.ai) == ["https://github.com/a/llm-chat"]
    assert urls(edition.main) == ["https://github.com/b/editor"]
    assert any(reason.startswith("Name: AI-Begriffe") for reason in edition.ai[0].reasons)


def test_repos_of_the_own_editions_of_the_last_30_days_are_blocked():
    shown = CommunityEdition(HN, TODAY - timedelta(days=29), main=(project("a/x"),))
    expired = CommunityEdition(HN, TODAY - timedelta(days=30), ai=(project("b/y", language="Go"),))

    edition = curate(project("A/X"), project("b/y", language="Go"), past=[shown, expired])

    assert urls(edition.main) == ["https://github.com/b/y"]


def test_the_variety_rule_counts_owners_per_forge():
    edition = curate(
        project("alice/a", language="Go"),
        project("alice/b", language="C"),
        project("alice/c", language="Zig"),
        make_project("https://codeberg.org/alice/d", story=make_story("d"), language="Lua"),
    )

    assert len(edition.main) == 3


def test_the_reason_says_how_the_repo_was_found():
    direct = curate(project("a/x")).main[0]
    via_site = curate(
        make_project(
            "https://github.com/rust-lang/rust",
            project_url="https://blog.rust-lang.org/2026/11/12/x",
            linked_directly=False,
        )
    ).main[0]

    assert direct.reasons[0] == "Die Story verlinkt das Repo direkt."
    assert via_site.reasons[0] == (
        "Gefunden über einen Link auf blog.rust-lang.org. Repo und Story teilen „lang“, „rust“, „rustlang“."
    )


class TestCommunityEdition:
    def test_refuses_a_repo_twice(self):
        with pytest.raises(ValueError):
            CommunityEdition(LOBSTERS, TODAY, main=(project("a/x"),), ai=(project("A/x/"),))

    def test_refuses_three_repos_of_an_owner(self):
        with pytest.raises(ValueError):
            CommunityEdition(
                HN, TODAY, main=tuple(project(f"a/{i}", language=f"L{i}") for i in range(3))
            )


def test_repository_key_ignores_case_and_a_trailing_slash():
    assert repository_key("https://github.com/A/X/") == repository_key("https://github.com/a/x")


@pytest.mark.parametrize(
    "license_id, expected",
    [("MIT", True), ("NOASSERTION", True), ("BUSL-1.1", False), (None, False)],
)
def test_open_source_licenses(license_id, expected):
    assert is_open_source_license(license_id) is expected


def test_platforms_know_their_discussion_pages():
    assert HN.discussion_url("123") == "https://news.ycombinator.com/item?id=123"
    assert LOBSTERS.discussion_url("abc") == "https://lobste.rs/s/abc"
