"""Hacker News stories used by the independent HN project list."""

from dataclasses import dataclass
from datetime import date, datetime

from github_anti_ai.domain.opensource import OPEN_SOURCE_LICENSES


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
        return self.license_id in OPEN_SOURCE_LICENSES


@dataclass(frozen=True)
class HnEdition:
    day: date
    projects: tuple[HnProjectCandidate, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "projects", tuple(self.projects))
        urls = [_repository_key(project.repository_url) for project in self.projects]
        if len(urls) != len(set(urls)):
            raise ValueError("Ein Repo steht mehrfach in der HN-Ausgabe")


class HnEditionCurator:
    def curate(self, day: date, candidates: list[HnProjectCandidate]) -> HnEdition:
        eligible = [
            candidate
            for candidate in candidates
            if candidate.is_open_source
            and candidate.has_code
            and not candidate.is_fork
            and not candidate.is_archived
        ]
        unique: dict[str, HnProjectCandidate] = {}
        for candidate in eligible:
            key = _repository_key(candidate.repository_url)
            current = unique.get(key)
            if current is None or _story_rank(candidate) < _story_rank(current):
                unique[key] = candidate
        projects = tuple(sorted(unique.values(), key=_story_rank))
        return HnEdition(day=day, projects=projects[:20])


def _repository_key(url: str) -> str:
    return url.rstrip("/").casefold()


def _story_rank(project: HnProjectCandidate) -> tuple[int, int, float]:
    story = project.story
    return -story.points, -story.comments, -story.created_at.timestamp()
