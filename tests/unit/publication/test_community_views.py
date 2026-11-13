import json

import pytest

from github_anti_ai.publication.community_view import (
    HN,
    LOBSTERS,
    community_feed_html,
    load_community_editions,
)

HN_STORY = {"points": 10}
LOBSTERS_STORY = {"score": 10, "discussion_url": "https://lobste.rs/s/abc"}


def project(repo="a/tool", license_id="MIT", **story):
    return {
        "story": {
            "id": "abc", "title": f"Story about {repo}", "url": "https://tool.example/",
            "comments": 1, "created_at": "2026-11-13T06:00:00+00:00", **story,
        },
        "repository_url": f"https://github.com/{repo}",
        "project_url": "https://tool.example/",
        "description": "",
        "language": "Rust",
        "license_id": license_id,
        "is_fork": False,
        "is_archived": False,
        "has_code": True,
    }


def write(directory, projects, ai_projects=None):
    directory.mkdir(exist_ok=True)
    edition = {"format_version": 1, "day": "2026-11-13", "projects": projects}
    if ai_projects is not None:
        edition["ai_projects"] = ai_projects
    (directory / "2026-11-13.json").write_text(json.dumps(edition), encoding="utf-8")
    return directory


def test_community_day_has_a_main_list_and_an_ai_section_with_own_titles_and_addresses(tmp_path):
    directory = write(
        tmp_path / "hn", [project("a/editor", **HN_STORY)], [project("b/agent", **HN_STORY)]
    )

    [day] = load_community_editions(directory, HN)

    assert day.main.title == "Trending auf HN vom 13. November 2026"
    assert day.main.url == "hn/2026/11/13/"
    assert day.main.stats == "1 Open-Source-Projekt"
    assert [entry.repository_url for entry in day.main.entries] == ["https://github.com/a/editor"]
    assert day.ai.title == "AI-Projekte auf HN vom 13. November 2026"
    assert day.ai.url == "hn/ai/2026/11/13/"
    assert day.ai.stats == "1 AI-Projekt"
    assert [entry.repository_url for entry in day.ai.entries] == ["https://github.com/b/agent"]


def test_community_edition_from_before_the_ai_section_has_an_empty_one(tmp_path):
    [day] = load_community_editions(write(tmp_path / "hn", [project(**HN_STORY)]), HN)

    assert day.ai.entries == []


def test_each_platform_names_its_points_and_links_its_discussion(tmp_path):
    [hn] = load_community_editions(write(tmp_path / "hn", [project(**HN_STORY)]), HN)
    [lobsters] = load_community_editions(
        write(tmp_path / "lobsters", [project(**LOBSTERS_STORY)]), LOBSTERS
    )

    assert hn.main.points_label == "HN-Punkte"
    assert hn.main.entries[0].discussion_url == "https://news.ycombinator.com/item?id=abc"
    assert lobsters.main.points_label == "Lobsters-Punkte"
    assert lobsters.main.entries[0].discussion_url == "https://lobste.rs/s/abc"
    assert lobsters.ai.url == "lobsters/ai/2026/11/13/"


@pytest.mark.parametrize(("platform", "story"), [(HN, HN_STORY), (LOBSTERS, LOBSTERS_STORY)])
@pytest.mark.parametrize(("license_id", "shown"), [("NOASSERTION", None), ("MIT", "MIT")])
def test_placeholder_for_an_unrecognized_license_is_not_shown_as_a_license(
    tmp_path, platform, story, license_id, shown
):
    [day] = load_community_editions(
        write(tmp_path / "editions", [project(license_id=license_id, **story)]), platform
    )

    assert day.main.entries[0].license_id == shown


def test_feed_of_the_ai_section_lists_only_ai_projects(tmp_path):
    directory = write(
        tmp_path / "hn", [project("a/editor", **HN_STORY)], [project("b/agent", **HN_STORY)]
    )
    [day] = load_community_editions(directory, HN)

    feed = community_feed_html(day.ai)

    assert "b/agent" in feed
    assert "a/editor" not in feed


def test_unknown_community_edition_format_is_rejected(tmp_path):
    directory = write(tmp_path / "hn", [])
    data = json.loads((directory / "2026-11-13.json").read_text())
    (directory / "2026-11-13.json").write_text(json.dumps(data | {"format_version": 9}))

    with pytest.raises(ValueError, match="HN"):
        load_community_editions(directory, HN)


def test_stats_count_several_projects_in_the_plural(tmp_path):
    directory = write(tmp_path / "hn", [project("a/one", **HN_STORY), project("b/two", **HN_STORY)])

    [day] = load_community_editions(directory, HN)

    assert day.main.stats == "2 Open-Source-Projekte"
    assert day.ai.stats == "0 AI-Projekte"
