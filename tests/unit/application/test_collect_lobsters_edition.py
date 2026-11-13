from datetime import UTC, datetime, timedelta

from builders import FixedClock
from github_anti_ai.application.collect_lobsters_edition import CollectLobstersEdition
from github_anti_ai.domain.lobsters import (
    LobstersEdition,
    LobstersProjectCandidate,
    LobstersStory,
)


NOW = datetime(2026, 11, 13, tzinfo=UTC)


class StorySource:
    def __init__(self, stories):
        self.stories = stories
        self.asked_for = None

    def discover(self, now, limit=None):
        self.asked_for = now
        return self.stories[:limit]


class ProjectResolver:
    def __init__(self, projects):
        self.projects = projects
        self.stories = []

    def resolve(self, story):
        self.stories.append(story)
        return self.projects.get(story.id)


class EditionStore:
    def __init__(self, existing=None, past=()):
        self.saved = []
        self.existing = existing
        self.past = list(past)
        self.asked_since = None

    def load(self, day):
        return self.existing if self.existing and self.existing.day == day else None

    def since(self, day):
        self.asked_since = day
        return [edition for edition in self.past if edition.day >= day]

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

    assert stories.asked_for == NOW
    assert resolver.stories == [story]
    assert store.saved == [edition]
    assert edition.projects == (project,)


def test_lobsters_collection_returns_an_existing_daily_edition_without_searching_again():
    existing = type("Edition", (), {"day": NOW.date()})()
    stories = StorySource([])
    store = EditionStore(existing=existing)

    edition = CollectLobstersEdition(
        story_source=stories,
        project_resolver=ProjectResolver({}),
        edition_store=store,
        clock=FixedClock(NOW),
    ).run()

    assert edition is existing
    assert stories.asked_for is None
    assert store.saved == []

def test_lobsters_collection_leaves_out_repos_of_its_editions_from_the_last_30_days():
    def found(story_id, repo):
        story = LobstersStory(
            story_id, "Tool", f"https://{story_id}.example", f"https://lobste.rs/s/{story_id}",
            42, 9, NOW,
        )
        return story, LobstersProjectCandidate(
            story=story, repository_url=repo, project_url=story.url, description="",
            language="Rust", license_id="MIT", is_fork=False, is_archived=False, has_code=True,
        )

    old_story, again = found("again", "https://github.com/a/shown")
    new_story, fresh = found("fresh", "https://github.com/a/fresh")
    yesterday = LobstersEdition(day=NOW.date() - timedelta(days=1), projects=(again,))
    store = EditionStore(past=[yesterday])

    edition = CollectLobstersEdition(
        story_source=StorySource([old_story, new_story]),
        project_resolver=ProjectResolver({"again": again, "fresh": fresh}),
        edition_store=store,
        clock=FixedClock(NOW),
    ).run()

    assert store.asked_since == NOW.date() - timedelta(days=30)
    assert edition.projects == (fresh,)
