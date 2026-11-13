from datetime import UTC, datetime

from builders import FixedClock
from github_anti_ai.application.collect_hn_edition import CollectHnEdition
from github_anti_ai.domain.hn import HnProjectCandidate, HnStory


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
    def __init__(self, existing=None):
        self.saved = []
        self.existing = existing

    def load(self, day):
        return self.existing if self.existing and self.existing.day == day else None

    def save(self, edition):
        self.saved.append(edition)


def test_hn_collection_uses_its_own_search_resolution_filter_and_store():
    story = HnStory(
        id="123",
        title="A project",
        url="https://project.example",
        points=42,
        comments=9,
        created_at=NOW,
    )
    project = HnProjectCandidate(
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

    edition = CollectHnEdition(
        story_source=stories,
        project_resolver=resolver,
        edition_store=store,
        clock=FixedClock(NOW),
    ).run()

    assert stories.asked_for == NOW.date()
    assert resolver.stories == [story]
    assert store.saved == [edition]
    assert edition.projects == (project,)


def test_hn_collection_returns_an_existing_daily_edition_without_searching_again():
    existing = type("Edition", (), {"day": NOW.date()})()
    stories = StorySource([])
    store = EditionStore(existing=existing)

    edition = CollectHnEdition(
        story_source=stories,
        project_resolver=ProjectResolver({}),
        edition_store=store,
        clock=FixedClock(NOW),
    ).run()

    assert edition is existing
    assert stories.asked_for is None
    assert store.saved == []