from datetime import UTC, datetime

import pytest

from github_anti_ai.adapters.json_lobsters_edition_store import JsonLobstersEditionStore
from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.lobsters import (
    LobstersEdition,
    LobstersProjectCandidate,
    LobstersStory,
)


def sample_edition():
    story = LobstersStory(
        id="abc",
        title="A project",
        url="https://project.example",
        discussion_url="https://lobste.rs/s/abc",
        score=42,
        comments=9,
        created_at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    return LobstersEdition(
        day=story.created_at.date(),
        projects=(
            LobstersProjectCandidate(
                story=story,
                repository_url="https://codeberg.org/owner/project",
                project_url=story.url,
                description="A useful open source project",
                language="Rust",
                license_id="MIT",
                is_fork=False,
                is_archived=False,
                has_code=True,
            ),
        ),
    )


def test_lobsters_edition_is_saved_and_loaded_with_its_story_and_project_facts(tmp_path):
    store = JsonLobstersEditionStore(tmp_path / "lobsters-editions")
    edition = sample_edition()

    store.save(edition)

    assert store.load(edition.day) == edition
    assert store.since(edition.day) == [edition]


def test_lobsters_edition_cannot_be_replaced_after_publication(tmp_path):
    store = JsonLobstersEditionStore(tmp_path / "lobsters-editions")
    edition = sample_edition()
    store.save(edition)

    with pytest.raises(AlreadyPublished):
        store.save(edition)