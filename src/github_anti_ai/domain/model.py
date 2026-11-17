"""The shared vocabulary of the GitHub list. The glossary in AGENTS.md explains the terms."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# A repo is shown after 14 days of development at the earliest. The growth window has the
# same length, so the stars of its first days still count on the day it may appear.
GROWTH_WINDOW_DAYS = 14
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
class Candidate:
    """A repo a CandidateSource found, with its star count if the source knows it."""

    repo: RepoId
    stars: int | None = None


@dataclass(frozen=True)
class Commit:
    committed_at: datetime
    author: str  # GitHub login, otherwise the name in git
    is_bot: bool
    co_authors: tuple[str, ...]  # the values of the Co-authored-by lines
    headline: str


@dataclass(frozen=True)
class StarHistory:
    """New stars per day, oldest first. The last entry is the day of the snapshot."""

    daily: tuple[int, ...] = ()  # empty if the history was not collected

    def __post_init__(self):
        object.__setattr__(self, "daily", tuple(self.daily))
        if any(stars < 0 for stars in self.daily):
            raise ValueError("Sterne pro Tag können nicht negativ sein")

    def gained(self, days: int = GROWTH_WINDOW_DAYS) -> int:
        """New stars of the most recent days, the day of the snapshot included."""
        return sum(self.daily[-days:])

    def continued(self, days_passed: int, gained: int) -> StarHistory:
        """The history some days later. The whole gain is booked on the last day.

        A history that was never collected stays empty.
        """
        if days_passed < 0 or gained < 0:
            raise ValueError("Ein Sternverlauf lässt sich nur vorwärts und ohne Verlust fortführen")
        if not self.daily:
            return self
        if days_passed == 0:
            return StarHistory(self.daily[:-1] + (self.daily[-1] + gained,))
        daily = self.daily + (0,) * (days_passed - 1) + (gained,)
        return StarHistory(daily[-len(self.daily) :])


@dataclass(frozen=True)
class Snapshot:
    """Everything collected about a repo at one moment."""

    repo: RepoId
    taken_at: datetime  # the day the snapshot belongs to
    description: str
    homepage: str | None
    topics: tuple[str, ...]
    primary_language: str | None
    created_at: datetime
    pushed_at: datetime | None
    stars: int
    forks: int
    pull_requests: int
    recent_issue_authors: int  # distinct people among the authors of the last 100 issues
    is_fork: bool
    is_archived: bool
    is_mirror: bool
    license: str | None
    root_files: tuple[str, ...]
    readme: str
    recent_commits: tuple[Commit, ...]
    star_history: StarHistory
    # When the facts last came from GitHub. A snapshot carried over from an earlier day
    # is older here than in taken_at. None means: as old as the snapshot.
    facts_at: datetime | None = None
    # History of the owner. None means unknown. Organizations have no contributions.
    owner_created_at: datetime | None = None
    owner_contributed_to: int | None = None

    def __post_init__(self):
        if self.facts_at is None:
            object.__setattr__(self, "facts_at", self.taken_at)

    def carried_over(self, now: datetime, stars: int) -> Snapshot:
        """This snapshot as the snapshot of a later moment, with the star count of then."""
        days_passed = (now.date() - self.taken_at.date()).days
        gained = max(0, stars - self.stars)  # people can take their star back
        return dataclasses.replace(
            self,
            taken_at=now,
            stars=stars,
            star_history=self.star_history.continued(days_passed, gained),
        )

    def with_facts_of(self, fresh: Snapshot) -> Snapshot:
        """Fresh facts from GitHub with this snapshot's star history, continued."""
        days_passed = (fresh.taken_at.date() - self.taken_at.date()).days
        gained = max(0, fresh.stars - self.stars)
        return dataclasses.replace(
            fresh, star_history=self.star_history.continued(days_passed, gained)
        )

    @property
    def can_never_be_shown(self) -> bool:
        """Fork, archived, mirror or without recognized code: excluded whatever else is true.

        The collection does not fetch the star history of such a repo.
        """
        return self.is_fork or self.is_archived or self.is_mirror or not self.primary_language

    @property
    def active_authors(self) -> int:
        """Distinct people (no bots) behind the recent commits."""
        return len({commit.author for commit in self.recent_commits if not commit.is_bot})


class Section(Enum):
    MAIN = "main"
    AI = "ai"


@dataclass(frozen=True)
class Signal:
    kind: str
    weight: float
    reason: str  # the sentence shown under "Warum Platz …?"


@dataclass(frozen=True)
class Exclusion:
    reason: str
    kind: str


@dataclass(frozen=True)
class Assessment:
    snapshot: Snapshot
    section: Section
    signals: tuple[Signal, ...]
    exclusion: Exclusion | None = None

    @property
    def repo(self) -> RepoId:
        return self.snapshot.repo

    @property
    def score(self) -> float:
        """The sum of all signal weights. Nothing else goes into it."""
        return sum(signal.weight for signal in self.signals)
