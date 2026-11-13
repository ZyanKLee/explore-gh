"""Domain types for the independent Lobsters project list."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from github_anti_ai.domain.community import (
    CommunityCurator,
    check_community_edition,
    recently_shown,
)
from github_anti_ai.domain.opensource import is_open_source_license

# Which stories the Lobsters search reads, see docs/datensammlung.md
HOTTEST_PAGES = 2
SHOW_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class LobstersStory:
    id: str
    title: str
    url: str
    discussion_url: str
    score: int
    comments: int
    created_at: datetime


@dataclass(frozen=True)
class LobstersProjectCandidate:
    story: LobstersStory
    repository_url: str
    project_url: str
    description: str
    language: str | None
    license_id: str | None
    is_fork: bool
    is_archived: bool
    has_code: bool
    topics: tuple[str, ...] = ()
    # Only read for the AI section and the exclusions, never stored, like a Snapshot's
    # README. None: it could not be read, "": the repo has none.
    readme: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics))

    @property
    def is_open_source(self) -> bool:
        return is_open_source_license(self.license_id)


@dataclass(frozen=True)
class LobstersEdition:
    day: date
    projects: tuple[LobstersProjectCandidate, ...] = ()  # the main section
    ai_projects: tuple[LobstersProjectCandidate, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "projects", tuple(self.projects))
        object.__setattr__(self, "ai_projects", tuple(self.ai_projects))
        check_community_edition(self.projects, "Lobsters", ai_projects=self.ai_projects)


class LobstersEditionCurator:
    def curate(
        self,
        day: date,
        candidates: list[LobstersProjectCandidate],
        past_editions: Iterable[LobstersEdition] = (),
    ) -> LobstersEdition:
        """`past_editions` are this platform's own editions; their repos are under cooldown."""
        selection = CommunityCurator().select(
            candidates, rank=_story_rank, cooled_down=recently_shown(day, past_editions)
        )
        return LobstersEdition(day=day, projects=selection.main, ai_projects=selection.ai)


def _story_rank(project: LobstersProjectCandidate) -> tuple[int, int, float]:
    story = project.story
    return -story.score, -story.comments, -story.created_at.timestamp()