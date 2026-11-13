"""What stays of an Assessment for good. See docs/langzeitdaten.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from github_anti_ai.domain.model import Assessment, RepoId, Section


@dataclass(frozen=True)
class DailyRecord:
    """Numbers and verdict of one repo on one day. No texts, no commits, no people."""

    day: date
    repo: RepoId
    stars: int
    forks: int
    stars_gained: int  # in the growth window of 7 days
    score: float
    section: Section
    exclusion: str | None  # kind of the Exclusion
    signals: tuple[tuple[str, float], ...]  # kind and weight, without the reason
    rank: int | None  # place in the Edition, None if the repo was not shown
    language: str | None
    created_at: datetime

    @classmethod
    def from_assessment(
        cls, day: date, assessment: Assessment, rank: int | None = None
    ) -> DailyRecord:
        snapshot = assessment.snapshot
        return cls(
            day=day,
            repo=snapshot.repo,
            stars=snapshot.stars,
            forks=snapshot.forks,
            stars_gained=snapshot.star_history.gained(),
            score=assessment.score,
            section=assessment.section,
            exclusion=assessment.exclusion.kind if assessment.exclusion else None,
            signals=tuple((signal.kind, signal.weight) for signal in assessment.signals),
            rank=rank,
            language=snapshot.primary_language,
            created_at=snapshot.created_at,
        )
