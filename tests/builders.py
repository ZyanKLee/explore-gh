"""Builders for domain objects with sensible defaults, so tests only state what matters."""

import zlib
from datetime import UTC, date, datetime, timedelta

from github_anti_ai.domain.community import HN, CommunityProject, Platform, Story
from github_anti_ai.domain.edition import Edition, Entry
from github_anti_ai.domain.model import (
    Assessment,
    Commit,
    Exclusion,
    RepoId,
    Section,
    Signal,
    Snapshot,
    StarHistory,
)

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)
TODAY = NOW.date()

ENGLISH_README = (
    "# tiny-editor\n\nA tiny terminal text editor. It is written in Rust and has syntax "
    "highlighting for the files you edit most. You can open more than one file at a time, "
    "and the editor will remember where you were. All keys can be changed in the "
    "configuration file, which is read when the editor starts.\n"
)


class FixedClock:
    def __init__(self, now: datetime = NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def star_history(gained: int, days: int = 35) -> StarHistory:
    """A history in which all stars of the growth window came today."""
    return StarHistory((0,) * (days - 1) + (gained,))


def make_commit(**overrides) -> Commit:
    fields = dict(
        committed_at=datetime(2026, 11, 10, 19, 2, 11, tzinfo=UTC),
        author="alice",
        is_bot=False,
        co_authors=(),
        headline="Add syntax highlighting for TOML",
    )
    fields.update(overrides)
    return Commit(**fields)


def make_snapshot(repo: str = "alice/tiny-editor", **overrides) -> Snapshot:
    """A repo that passes every rule: in the main list, not excluded."""
    fields = dict(
        repo=RepoId.parse(repo),
        taken_at=NOW,
        # every repo its own text: the same description and topics would make them copies
        description=(
            "A tiny terminal text editor"
            if repo == "alice/tiny-editor"
            else f"A tiny terminal text editor, build {zlib.crc32(repo.lower().encode())}"
        ),
        homepage=None,
        topics=("editor", "terminal"),
        primary_language="Rust",
        created_at=NOW - timedelta(days=23),
        pushed_at=NOW - timedelta(days=1),
        stars=812,
        forks=31,
        pull_requests=27,
        recent_issue_authors=14,
        is_fork=False,
        is_archived=False,
        is_mirror=False,
        license="MIT",
        root_files=("Cargo.toml", "README.md", "src"),
        readme=ENGLISH_README,
        recent_commits=(make_commit(),),
        star_history=star_history(120),
    )
    fields.update(overrides)
    return Snapshot(**fields)


def make_assessment(
    repo: str = "alice/tiny-editor",
    *,
    section: Section = Section.MAIN,
    score: float = 1.0,
    language: str | None = "Rust",
    gained: int = 120,
    exclusion: Exclusion | None = None,
    **snapshot_overrides,
) -> Assessment:
    """An assessment with a single signal that carries the whole score."""
    snapshot = make_snapshot(
        repo, primary_language=language, star_history=star_history(gained), **snapshot_overrides
    )
    return Assessment(
        snapshot=snapshot,
        section=section,
        signals=(Signal("momentum", score, f"{score} Punkte"),),
        exclusion=exclusion,
    )


def make_entry(repo: str = "alice/tiny-editor", **assessment_options) -> Entry:
    return Entry.from_assessment(make_assessment(repo, **assessment_options))


def make_edition(day: date = TODAY, main=(), ai=()) -> Edition:
    """main and ai hold repo names or Entries."""

    def entries(items):
        return tuple(make_entry(i) if isinstance(i, str) else i for i in items)

    return Edition(day=day, main=entries(main), ai=entries(ai))


def make_story(id: str = "1", platform: Platform = HN, **overrides) -> Story:
    fields = dict(
        id=id,
        title="Tiny Editor: a terminal text editor",
        url="https://github.com/alice/tiny-editor",
        discussion_url=platform.discussion_url(id),
        points=120,
        comments=30,
        created_at=NOW - timedelta(hours=5),
    )
    fields.update(overrides)
    return Story(**fields)


def make_project(
    repository_url: str = "https://github.com/alice/tiny-editor", **overrides
) -> CommunityProject:
    """An open source project that passes every rule of the community lists."""
    fields = dict(
        story=make_story(),
        repository_url=repository_url,
        project_url=repository_url,
        description="A tiny terminal text editor",
        language="Rust",
        license_id="MIT",
        is_fork=False,
        is_archived=False,
        has_code=True,
        topics=("editor",),
        linked_directly=True,
        readme=ENGLISH_README,
    )
    fields.update(overrides)
    return CommunityProject(**fields)
