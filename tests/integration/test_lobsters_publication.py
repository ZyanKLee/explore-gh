from datetime import UTC, datetime

from github_anti_ai.adapters.json_lobsters_edition_store import JsonLobstersEditionStore
from github_anti_ai.domain.lobsters import (
    LobstersEdition,
    LobstersProjectCandidate,
    LobstersStory,
)
from github_anti_ai.publication.site import build_site


def test_lobsters_projects_have_separate_pages_archive_and_feed(tmp_path):
    story = LobstersStory(
        id="abc",
        title="A project worth exploring",
        url="https://project.example",
        discussion_url="https://lobste.rs/s/abc",
        score=42,
        comments=9,
        created_at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    edition = LobstersEdition(
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
    lobsters_editions = tmp_path / "lobsters-editions"
    JsonLobstersEditionStore(lobsters_editions).save(edition)

    build_site(
        tmp_path / "editions",
        tmp_path / "output",
        lobsters_editions_dir=lobsters_editions,
    )

    start = (tmp_path / "output/lobsters/index.html").read_text(encoding="utf-8")
    day = (tmp_path / "output/lobsters/2026/11/13/index.html").read_text(encoding="utf-8")
    archive = (tmp_path / "output/lobsters/archiv/index.html").read_text(encoding="utf-8")
    feed = (tmp_path / "output/lobsters/feed.xml").read_text(encoding="utf-8")

    assert "Trending auf Lobsters" in start
    assert "owner/project" in start
    assert "https://lobste.rs/s/abc" in day
    assert "13. November 2026" in archive
    assert "owner/project" in feed
    assert "owner/project" not in (tmp_path / "output/index.html").read_text(encoding="utf-8")