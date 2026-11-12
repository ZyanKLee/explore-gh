"""Builders for domain objects with sensible defaults, so tests only state what matters."""

from datetime import UTC, date, datetime

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
from github_anti_ai.domain.edition import Edition, Entry

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)
TODAY = date(2026, 11, 12)


class FixedClock:
    def __init__(self, now: datetime = NOW):
        self._now = now

    def now(self) -> datetime:
        return self._now


def star_history(gained: int, days: int = 35) -> StarHistory:
    """A history in which all stars of the growth window were gained today."""
    return StarHistory(daily=(0,) * (days - 1) + (gained,))


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
    fields = dict(
        repo=RepoId.parse(repo),
        taken_at=NOW,
        description="A tiny terminal text editor",
        homepage=None,
        topics=("editor", "terminal"),
        primary_language="Rust",
        created_at=datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
        pushed_at=datetime(2026, 11, 10, 19, 2, 11, tzinfo=UTC),
        stars=812,
        forks=31,
        open_issues=12,
        watchers=9,
        pull_requests=27,
        recent_issue_authors=14,
        is_fork=False,
        is_archived=False,
        is_mirror=False,
        is_template=False,
        license="MIT",
        root_files=("Cargo.toml", "README.md", "src"),
        readme="# tiny-editor\n\nA tiny terminal text editor.\n",
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
    signals: tuple[Signal, ...] = (),
    exclusion: Exclusion | None = None,
) -> Assessment:
    snapshot = make_snapshot(
        repo,
        primary_language=language,
        star_history=star_history(gained),
    )
    return Assessment(
        snapshot=snapshot,
        section=section,
        score=score,
        signals=signals,
        exclusion=exclusion,
    )


def make_entry(repo: str = "alice/tiny-editor", **assessment_options) -> Entry:
    return Entry.from_assessment(make_assessment(repo, **assessment_options))


def make_edition(day: date = TODAY, main=(), ai=()) -> Edition:
    """main and ai are repo names or Entries."""

    def entries(items):
        return tuple(make_entry(i) if isinstance(i, str) else i for i in items)

    return Edition(day=day, main=entries(main), ai=entries(ai))
