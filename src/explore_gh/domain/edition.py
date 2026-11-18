"""The daily Edition of the GitHub list and how it is put together. See docs/ausgabe.md."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from explore_gh.domain.curation import check_section, check_unique, in_cooldown, varied
from explore_gh.domain.model import Assessment, RepoId, Section, Signal, StarHistory


@dataclass(frozen=True)
class Entry:
    """A repo within an Edition, with everything the page shows about it.

    Snapshots are deleted after 14 days, the archive has to stay readable for good.
    """

    repo: RepoId
    score: float
    signals: tuple[Signal, ...]
    description: str
    homepage: str | None
    primary_language: str | None
    topics: tuple[str, ...]
    stars: int
    star_history: StarHistory
    created_at: datetime
    pushed_at: datetime | None
    license: str | None
    forks: int
    active_authors: int

    @classmethod
    def from_assessment(cls, assessment: Assessment) -> Entry:
        snapshot = assessment.snapshot
        return cls(
            repo=snapshot.repo,
            score=assessment.score,
            signals=assessment.signals,
            description=snapshot.description,
            homepage=snapshot.homepage,
            primary_language=snapshot.primary_language,
            topics=snapshot.topics,
            stars=snapshot.stars,
            star_history=snapshot.star_history,
            created_at=snapshot.created_at,
            pushed_at=snapshot.pushed_at,
            license=snapshot.license,
            forks=snapshot.forks,
            active_authors=snapshot.active_authors,
        )


@dataclass(frozen=True)
class EditionStats:
    """How many repos stood behind the selection of the day."""

    assessed: int = 0
    excluded: int = 0
    ai_focused: int = 0


@dataclass(frozen=True)
class Edition:
    """The selection of one day. Entries are in ranking order. Never changed once published."""

    day: date
    main: tuple[Entry, ...] = ()
    ai: tuple[Entry, ...] = ()
    stats: EditionStats = field(default_factory=EditionStats)

    def __post_init__(self):
        object.__setattr__(self, "main", tuple(self.main))
        object.__setattr__(self, "ai", tuple(self.ai))
        for section in Section:
            check_section(
                self.entries(section),
                language_of=lambda entry: entry.primary_language,
                owner_of=lambda entry: entry.repo.owner.lower(),
                name=f"Sektion {section.value}",
            )
        check_unique((entry.repo for entry in self.main + self.ai), f"Ausgabe vom {self.day}")

    def entries(self, section: Section) -> tuple[Entry, ...]:
        return self.main if section is Section.MAIN else self.ai

    def ranks(self) -> dict[RepoId, int]:
        """The place of each repo within its section, starting at 1."""
        return {
            entry.repo: place
            for section in Section
            for place, entry in enumerate(self.entries(section), start=1)
        }


class EditionCurator:
    def curate(
        self, day: date, assessments: Sequence[Assessment], past_editions: Iterable[Edition]
    ) -> Edition:
        blocked = {
            repo
            for edition in past_editions
            if in_cooldown(edition.day, day)
            for repo in edition.ranks()
        }
        eligible = [a for a in assessments if a.exclusion is None and a.repo not in blocked]
        return Edition(
            day=day,
            main=_select(a for a in eligible if a.section is Section.MAIN),
            ai=_select(a for a in eligible if a.section is Section.AI),
            stats=EditionStats(
                assessed=len(assessments),
                excluded=sum(1 for a in assessments if a.exclusion is not None),
                ai_focused=sum(
                    1 for a in assessments if a.exclusion is None and a.section is Section.AI
                ),
            ),
        )


def _select(assessments: Iterable[Assessment]) -> tuple[Entry, ...]:
    """Highest score first; on a tie more new stars, then the name. Always the same result."""
    ranked = sorted(
        assessments,
        key=lambda a: (-a.score, -a.snapshot.star_history.gained(), str(a.repo).lower()),
    )
    chosen = varied(
        ranked,
        language_of=lambda a: a.snapshot.primary_language,
        owner_of=lambda a: a.repo.owner.lower(),
    )
    return tuple(Entry.from_assessment(a) for a in chosen)
