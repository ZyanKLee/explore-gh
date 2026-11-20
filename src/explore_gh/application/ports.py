"""Ports: what the use cases need from the outside world."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from explore_gh.domain.community import CommunityEdition, CommunityProject, Story
from explore_gh.domain.edition import Edition
from explore_gh.domain.history import DailyRecord
from explore_gh.domain.model import Assessment, Candidate, RepoId, Snapshot
from explore_gh.domain.review import Review
from explore_gh.domain.withdrawal import Withdrawal


class SourceUnavailable(Exception):
    """An external source could not deliver."""


class AlreadyPublished(Exception):
    """There is an Edition for this day already. Editions are never replaced."""


class NothingToPublish(Exception):
    """There are no snapshots of the day to build an Edition from."""


class IncompleteCollection(Exception):
    """The collection of the day has holes. An Edition from it could never be replaced."""


@dataclass(frozen=True)
class CollectionStatus:
    """How the collection of a day ended."""

    day: date
    discovered: int
    collected: int
    failed: int  # could not be fetched. Repos that no longer exist do not count.

    @property
    def is_complete(self) -> bool:
        return self.failed == 0


Assess = Callable[[Snapshot], Assessment]


class Clock(Protocol):
    def now(self) -> datetime:
        """Always UTC."""
        ...


class CandidateSource(Protocol):
    name: str

    def discover(self, today: date, limit: int | None = None) -> list[Candidate]:
        """With a limit, the source stops looking once it has found that many."""
        ...


class RepoSource(Protocol):
    def fetch(
        self, repos: Sequence[RepoId], now: datetime, with_star_history: bool = True
    ) -> list[Snapshot]:
        """Repos that do not exist (any more) are left out.

        Without the star history the snapshots come with an empty one.
        """
        ...


class Reviewer(Protocol):
    def review(self, snapshots: Sequence[Snapshot]) -> dict[RepoId, Review]:
        """What a language model thinks of these repos. A repo may be missing in the answer.

        Raises SourceUnavailable if the model cannot be reached or answers nonsense.
        """
        ...


class SnapshotStore(Protocol):
    def append(self, day: date, snapshots: Sequence[Snapshot]) -> None: ...

    def load(self, day: date) -> list[Snapshot]:
        """The latest snapshot of each repo of that day."""
        ...

    def prune(self, before: date) -> None: ...


class CollectionStatusStore(Protocol):
    def save(self, status: CollectionStatus) -> None:
        """Replaces an earlier status of the same day."""
        ...

    def load(self, day: date) -> CollectionStatus | None: ...

    def prune(self, before: date) -> None: ...


class DailyRecordStore(Protocol):
    def save(self, day: date, records: Sequence[DailyRecord]) -> None:
        """Replaces the records of that day."""
        ...

    def load(self, day: date) -> list[DailyRecord]: ...

    def days(self) -> list[date]: ...


class EditionStore(Protocol):
    def save(self, edition: Edition) -> None:
        """Raises AlreadyPublished if there is an Edition for that day."""
        ...

    def load(self, day: date) -> Edition | None: ...

    def since(self, day: date) -> list[Edition]:
        """Editions from day on (inclusive), in date order."""
        ...


class StorySource(Protocol):
    def discover(self, now: datetime, limit: int | None = None) -> list[Story]: ...


class ProjectResolver(Protocol):
    def resolve(self, story: Story) -> CommunityProject | None:
        """The public repo the story is about, or None if there is none."""
        ...


class CommunityEditionStore(Protocol):
    """The editions of one platform."""

    def save(self, edition: CommunityEdition) -> None:
        """Raises AlreadyPublished if there is an edition for that day."""
        ...

    def load(self, day: date) -> CommunityEdition | None: ...

    def since(self, day: date) -> list[CommunityEdition]: ...


class WithdrawalStore(Protocol):
    def load(self) -> list[Withdrawal]:
        """The repos the owner withdrew, written by hand. Empty if there are none."""
        ...
