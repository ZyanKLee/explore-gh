"""Ports: what the use cases need from the outside world."""

from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Protocol

from github_anti_ai.domain.edition import Edition
from github_anti_ai.domain.model import Assessment, RepoId, Snapshot


class SourceUnavailable(Exception):
    """An external source could not deliver."""


class AlreadyPublished(Exception):
    """There is already an Edition for this day. Editions are never replaced."""


class NothingToPublish(Exception):
    """There are no snapshots of the day to build an Edition from."""


class Clock(Protocol):
    def now(self) -> datetime: ...


class CandidateSource(Protocol):
    name: str

    def discover(self, today: date, limit: int | None = None) -> list[RepoId]:
        """With a limit, the source stops looking once it has found that many."""
        ...


class RepoSource(Protocol):
    def fetch(self, repos: Sequence[RepoId], now: datetime) -> list[Snapshot]:
        """Repos that do not exist (any more) are simply left out."""
        ...


class SnapshotStore(Protocol):
    def append(self, day: date, snapshots: Sequence[Snapshot]) -> None: ...

    def load(self, day: date) -> list[Snapshot]:
        """The latest snapshot of each repo of that day."""
        ...

    def prune(self, before: date) -> None: ...


class EditionStore(Protocol):
    def save(self, edition: Edition) -> None:
        """Raises AlreadyPublished if there is an Edition for that day."""
        ...

    def load(self, day: date) -> Edition | None: ...

    def since(self, day: date) -> list[Edition]:
        """Editions from day on (inclusive), in date order."""
        ...


Assessor = Callable[[Snapshot], Assessment]
