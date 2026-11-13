"""Hacker News stories used by the independent HN project list."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from github_anti_ai.domain.community import (
    CommunityCurator,
    check_community_edition,
    recently_shown,
)
from github_anti_ai.domain.opensource import is_open_source_license

# Which stories the HN search asks for, see docs/datensammlung.md
STORY_WINDOW = timedelta(hours=48)
MIN_STORY_POINTS = 50


@dataclass(frozen=True)
class HnStory:
    id: str
    title: str
    url: str
    points: int
    comments: int
    created_at: datetime


@dataclass(frozen=True)
class HnProjectCandidate:
    story: HnStory
    repository_url: str
    project_url: str
    description: str
    language: str | None
    license_id: str | None
    is_fork: bool
    is_archived: bool
    has_code: bool

    @property
    def is_open_source(self) -> bool:
        return is_open_source_license(self.license_id)


@dataclass(frozen=True)
class HnEdition:
    day: date
    projects: tuple[HnProjectCandidate, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "projects", tuple(self.projects))
        check_community_edition(self.projects, "HN")


class HnEditionCurator:
    def curate(
        self,
        day: date,
        candidates: list[HnProjectCandidate],
        past_editions: Iterable[HnEdition] = (),
    ) -> HnEdition:
        """`past_editions` are this platform's own editions; their repos are under cooldown."""
        projects = CommunityCurator().select(
            candidates, rank=_story_rank, cooled_down=recently_shown(day, past_editions)
        )
        return HnEdition(day=day, projects=projects)


def _story_rank(project: HnProjectCandidate) -> tuple[int, int, float]:
    story = project.story
    return -story.points, -story.comments, -story.created_at.timestamp()
