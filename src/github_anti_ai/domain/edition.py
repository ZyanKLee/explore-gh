"""Curation: the daily Edition and how it is put together. See docs/ausgabe.md."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from github_anti_ai.domain.model import Assessment, RepoId, Section, Signal, StarHistory

ENTRIES_PER_SECTION = 20
MAX_PER_LANGUAGE = 4
MAX_PER_OWNER = 2
COOLDOWN_DAYS = 30


@dataclass(frozen=True)
class Entry:
    """A repo within an Edition, with everything the page shows about it."""

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
    """The selection of one day. Entries are in ranking order."""

    day: date
    main: tuple[Entry, ...] = ()
    ai: tuple[Entry, ...] = ()
    stats: EditionStats = field(default_factory=EditionStats)

    def __post_init__(self):
        object.__setattr__(self, "main", tuple(self.main))
        object.__setattr__(self, "ai", tuple(self.ai))
        for section in Section:
            _check_section(section, self.entries(section))
        repos = [entry.repo for entry in self.main + self.ai]
        if len(set(repos)) != len(repos):
            raise ValueError("Ein Repo steht mehrfach in der Ausgabe")

    def entries(self, section: Section) -> tuple[Entry, ...]:
        return self.main if section is Section.MAIN else self.ai

    def shows(self, repo: RepoId) -> bool:
        return any(entry.repo == repo for entry in self.main + self.ai)


def _check_section(section: Section, entries: tuple[Entry, ...]) -> None:
    if len(entries) > ENTRIES_PER_SECTION:
        raise ValueError(f"Sektion {section.value}: mehr als {ENTRIES_PER_SECTION} Einträge")
    languages = Counter(entry.primary_language for entry in entries)
    if languages and max(languages.values()) > MAX_PER_LANGUAGE:
        raise ValueError(f"Sektion {section.value}: mehr als {MAX_PER_LANGUAGE} Einträge einer Sprache")
    owners = Counter(entry.repo.owner.lower() for entry in entries)
    if owners and max(owners.values()) > MAX_PER_OWNER:
        raise ValueError(f"Sektion {section.value}: mehr als {MAX_PER_OWNER} Repos eines Besitzers")


class EditionCurator:
    def curate(
        self, day: date, assessments: Sequence[Assessment], past_editions: Iterable[Edition]
    ) -> Edition:
        cooled_down = {
            entry.repo
            for edition in past_editions
            if (day - edition.day).days < COOLDOWN_DAYS
            for entry in edition.main + edition.ai
        }
        eligible = [a for a in assessments if a.exclusion is None and a.repo not in cooled_down]
        return Edition(
            day=day,
            main=_select([a for a in eligible if a.section is Section.MAIN]),
            ai=_select([a for a in eligible if a.section is Section.AI]),
            stats=EditionStats(
                assessed=len(assessments),
                excluded=sum(1 for a in assessments if a.exclusion is not None),
                ai_focused=sum(
                    1 for a in assessments if a.exclusion is None and a.section is Section.AI
                ),
            ),
        )


def _select(assessments: list[Assessment]) -> tuple[Entry, ...]:
    ranked = sorted(
        assessments,
        key=lambda a: (-a.score, -a.snapshot.star_history.gained(), str(a.repo).lower()),
    )
    selected: list[Entry] = []
    per_language: Counter[str | None] = Counter()
    per_owner: Counter[str] = Counter()
    for assessment in ranked:
        language = assessment.snapshot.primary_language
        owner = assessment.repo.owner.lower()
        if per_language[language] == MAX_PER_LANGUAGE or per_owner[owner] == MAX_PER_OWNER:
            continue
        per_language[language] += 1
        per_owner[owner] += 1
        selected.append(Entry.from_assessment(assessment))
        if len(selected) == ENTRIES_PER_SECTION:
            break
    return tuple(selected)
