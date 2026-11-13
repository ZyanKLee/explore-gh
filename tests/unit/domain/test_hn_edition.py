from datetime import UTC, datetime

from github_anti_ai.domain.hn import HnProjectCandidate, HnEditionCurator, HnStory


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
                project("unlicensed", "https://codeberg.org/a/unlicensed", 100,
                    license_id="NOASSERTION"),
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