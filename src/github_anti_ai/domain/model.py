"""Shared vocabulary of the domain. Terms are explained in the glossary in AGENTS.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

GROWTH_WINDOW_DAYS = 7
STAR_HISTORY_DAYS = 35
COMMIT_LOOKBACK = timedelta(days=90)
README_MAX_CHARS = 20_000

_NAME_PART = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True, eq=False)
class RepoId:
    """owner/name of a GitHub repository. Compares case-insensitively, like GitHub."""

    owner: str
    name: str

    def __post_init__(self):
        if not (_NAME_PART.fullmatch(self.owner) and _NAME_PART.fullmatch(self.name)):
            raise ValueError(f"Ungültige Repo-ID: {self.owner}/{self.name}")

    @classmethod
    def parse(cls, text: str) -> RepoId:
        owner, separator, name = text.partition("/")
        if not separator:
            raise ValueError(f"Ungültige Repo-ID: {text!r}")
        return cls(owner, name)

    @property
    def url(self) -> str:
        return f"https://github.com/{self}"

    def _key(self) -> tuple[str, str]:
        return self.owner.lower(), self.name.lower()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RepoId) and self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class Commit:
    committed_at: datetime
    author: str
    is_bot: bool
    co_authors: tuple[str, ...]
    headline: str


@dataclass(frozen=True)
class StarHistory:
    """Stars gained per day, oldest first. The last entry is the day of the snapshot."""

    daily: tuple[int, ...]  # empty if the history was not collected

    def __post_init__(self):
        if any(stars < 0 for stars in self.daily):
            raise ValueError("Sterne pro Tag können nicht negativ sein")

    def gained(self, days: int = GROWTH_WINDOW_DAYS) -> int:
        """Stars gained on the most recent days, the day of the snapshot included."""
        return sum(self.daily[-days:])


@dataclass(frozen=True)
class Snapshot:
    repo: RepoId
    taken_at: datetime
    description: str
    homepage: str | None
    topics: tuple[str, ...]
    primary_language: str | None
    created_at: datetime
    pushed_at: datetime | None
    stars: int
    forks: int
    open_issues: int
    watchers: int
    pull_requests: int
    recent_issue_authors: int
    is_fork: bool
    is_archived: bool
    is_mirror: bool
    is_template: bool
    license: str | None
    root_files: tuple[str, ...]
    readme: str
    recent_commits: tuple[Commit, ...]
    star_history: StarHistory

    @property
    def can_never_be_shown(self) -> bool:
        """Fork, archived, mirror or without recognized code: excluded whatever else is true.

        The collection does not fetch the star history of such a repo.
        """
        return self.is_fork or self.is_archived or self.is_mirror or not self.primary_language

    @property
    def active_authors(self) -> int:
        """Distinct people (no bots) behind the recent commits."""
        return len({c.author for c in self.recent_commits if not c.is_bot})


class Section(Enum):
    MAIN = "main"
    AI = "ai"


@dataclass(frozen=True)
class Signal:
    kind: str
    weight: float
    reason: str


@dataclass(frozen=True)
class Exclusion:
    reason: str


@dataclass(frozen=True)
class Assessment:
    snapshot: Snapshot
    section: Section
    score: float
    signals: tuple[Signal, ...]
    exclusion: Exclusion | None = None

    @property
    def repo(self) -> RepoId:
        return self.snapshot.repo
