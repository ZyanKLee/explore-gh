from datetime import UTC, datetime, timedelta

from github_anti_ai.domain.hn import HnEdition, HnEditionCurator, HnProjectCandidate, HnStory


NOW = datetime(2026, 11, 13, tzinfo=UTC)


def project(story_id, repo_url, points, **overrides):
    story = HnStory(
        id=story_id,
        title=f"Project {story_id}",
        url=f"https://example.test/{story_id}",
        points=points,
        comments=4,
        created_at=NOW,
    )
    values = {
        "story": story,
        "repository_url": repo_url,
        "project_url": story.url,
        "description": "A useful open source project",
        "language": "Rust",
        "license_id": overrides.pop("license_id", "MIT"),
        "is_fork": False,
        "is_archived": False,
        "has_code": True,
    }
    values.update(overrides)
    return HnProjectCandidate(**values)


def test_hn_edition_filters_non_oss_and_ranks_projects_by_hn_points():
    edition = HnEditionCurator().curate(
        NOW.date(),
        [
            project("lower", "https://codeberg.org/a/lower", 20),
            project("unlicensed", "https://codeberg.org/a/unlicensed", 100, license_id=None),
            project("source-available", "https://codeberg.org/a/busl", 90, license_id="BUSL-1.1"),
            project("higher", "https://gitlab.com/a/higher", 50),
        ],
    )

    assert [entry.repository_url for entry in edition.projects] == [
        "https://gitlab.com/a/higher",
        "https://codeberg.org/a/lower",
    ]


def test_hn_edition_rejects_projects_without_code_or_with_fork_or_archive_status():
    edition = HnEditionCurator().curate(
        NOW.date(),
        [
            project("empty", "https://forge.example/a/empty", 100, has_code=False),
            project("fork", "https://forge.example/a/fork", 90, is_fork=True),
            project("archived", "https://forge.example/a/archived", 80, is_archived=True),
        ],
    )

    assert edition.projects == ()

def test_hn_edition_keeps_a_project_whose_license_file_is_not_recognized():
    edition = HnEditionCurator().curate(
        NOW.date(),
        [project("dual", "https://github.com/a/dual", 10, license_id="NOASSERTION")],
    )

    assert [entry.repository_url for entry in edition.projects] == ["https://github.com/a/dual"]


def test_hn_edition_leaves_out_a_repo_it_showed_in_the_last_30_days():
    shown = project("old", "https://github.com/a/shown", 10)
    yesterday = HnEdition(day=NOW.date() - timedelta(days=1), projects=(shown,))
    month_ago = HnEdition(
        day=NOW.date() - timedelta(days=30),
        projects=(project("older", "https://github.com/a/released", 10),),
    )

    edition = HnEditionCurator().curate(
        NOW.date(),
        [
            project("again", "https://github.com/a/shown", 500),
            project("back", "https://github.com/a/released", 50),
            project("fresh", "https://github.com/a/fresh", 20),
        ],
        past_editions=[month_ago, yesterday],
    )

    assert [entry.repository_url for entry in edition.projects] == [
        "https://github.com/a/released",
        "https://github.com/a/fresh",
    ]


def test_hn_edition_puts_ai_focused_projects_into_its_ai_section():
    agent = project("agent", "https://github.com/a/agent", 90,
                    description="An LLM agent", topics=("mcp",))
    editor = project("editor", "https://github.com/b/editor", 10)

    edition = HnEditionCurator().curate(NOW.date(), [agent, editor])

    assert edition.projects == (editor,)
    assert edition.ai_projects == (agent,)


def test_hn_edition_leaves_out_a_repo_of_its_past_ai_section():
    agent = project("agent", "https://github.com/a/agent", 90, description="An LLM agent",
                    topics=("mcp",))
    yesterday = HnEdition(day=NOW.date() - timedelta(days=1), ai_projects=(agent,))

    edition = HnEditionCurator().curate(NOW.date(), [agent], past_editions=[yesterday])

    assert edition.ai_projects == ()


def test_hn_project_readme_is_input_only_and_not_part_of_its_identity():
    assert project("a", "https://github.com/a/a", 1, readme="# A") == project(
        "a", "https://github.com/a/a", 1, readme=""
    )
