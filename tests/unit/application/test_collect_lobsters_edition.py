from datetime import UTC, datetime

from builders import FixedClock
from github_anti_ai.application.collect_lobsters_edition import CollectLobstersEdition
from github_anti_ai.domain.lobsters import LobstersProjectCandidate, LobstersStory


NOW = datetime(2026, 11, 13, tzinfo=UTC)


class StorySource:
    def __init__(self, stories):
        self.stories = stories
        self.asked_for = None

    def discover(self, today, limit=None):
        self.asked_for = today
        return self.stories[:limit]


class ProjectResolver:
    def __init__(self, projects):
        self.projects = projects
        self.stories = []

    def resolve(self, story):
        self.stories.append(story)
        return self.projects.get(story.id)


class EditionStore:
    def __init__(self):
        self.saved = []

    def save(self, edition):
        self.saved.append(edition)


def test_lobsters_collection_uses_its_own_search_resolution_filter_and_store():
    story = LobstersStory(
        id="abc",
        title="A project",
        url="https://project.example",
        discussion_url="https://lobste.rs/s/abc",
        score=42,
        comments=9,
        created_at=NOW,
    )
    project = LobstersProjectCandidate(
        story=story,
        repository_url="https://codeberg.org/owner/project",
        project_url=story.url,
        description="An open source project",
        language="Rust",
        license_id="MIT",
        is_fork=False,
        is_archived=False,
        has_code=True,
    )
    stories = StorySource([story])
    resolver = ProjectResolver({story.id: project})
    store = EditionStore()

    edition = CollectLobstersEdition(
        story_source=stories,
        project_resolver=resolver,
        edition_store=store,
        clock=FixedClock(NOW),
    ).run()

    assert stories.asked_for == NOW.date()
    assert resolver.stories == [story]
    assert store.saved == [edition]
    assert edition.projects == (project,)