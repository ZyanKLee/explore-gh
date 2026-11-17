"""The community lists: trending open source projects on HN and Lobsters.

Both platforms follow the same rules. They differ only in their Platform.
See docs/community.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlsplit

from github_anti_ai.domain.ai_focus import AiFocus, AiFocusClassifier
from github_anti_ai.domain.curation import check_section, check_unique, in_cooldown, varied
from github_anti_ai.domain.exclusion import ExclusionPolicy
from github_anti_ai.domain.model import Section
from github_anti_ai.domain.story_relation import shared_words
from github_anti_ai.domain.text import quoted

# Which stories the searches ask for
HN_STORY_WINDOW = timedelta(hours=48)
HN_MIN_STORY_POINTS = 50
LOBSTERS_HOTTEST_PAGES = 2
LOBSTERS_SHOW_WINDOW = timedelta(days=7)

OPEN_SOURCE_LICENSES = frozenset(
    {
        "0BSD", "AFL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "Apache-2.0",
        "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSL-1.0", "CC0-1.0",
        "CDDL-1.0", "CERN-OHL-P-2.0", "ECL-2.0", "EPL-1.0", "EPL-2.0",
        "EUPL-1.2", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only",
        "GPL-3.0-or-later", "ISC", "LGPL-2.1-only", "LGPL-2.1-or-later",
        "LGPL-3.0-only", "LGPL-3.0-or-later", "MIT", "MPL-2.0", "MS-PL",
        "OFL-1.1", "OSL-3.0", "PostgreSQL", "Python-2.0", "Unlicense", "WTFPL",
        "Zlib",
    }
)  # fmt: skip
# What a forge reports for a license file it cannot identify: typically two license
# files (MIT and Apache) or a modified license text. GitLab's "other" becomes this.
UNRECOGNIZED_LICENSE = "NOASSERTION"
UNRECOGNIZED_LICENSE_REASON = (
    "Lizenzdatei vorhanden, die die Forge nicht erkennt. Zählt als Open Source."
)


def is_open_source_license(license_id: str | None) -> bool:
    """An approved license, or a license file the forge cannot identify."""
    return license_id in OPEN_SOURCE_LICENSES or license_id == UNRECOGNIZED_LICENSE


@dataclass(frozen=True)
class Platform:
    slug: str  # first part of every address and name of the data directory: hn, lobsters
    name: str
    discussion_url_pattern: str  # with {id}

    def discussion_url(self, story_id: str) -> str:
        return self.discussion_url_pattern.format(id=quote(story_id))


HN = Platform("hn", "HN", "https://news.ycombinator.com/item?id={id}")
LOBSTERS = Platform("lobsters", "Lobsters", "https://lobste.rs/s/{id}")
PLATFORMS = (HN, LOBSTERS)


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    url: str  # what the story links: a repo or a website
    discussion_url: str
    points: int  # HN points, Lobsters score
    comments: int
    created_at: datetime


@dataclass(frozen=True)
class CommunityProject:
    """A public software project a story links, with what its forge says about it."""

    story: Story
    repository_url: str
    project_url: str
    description: str
    language: str | None
    license_id: str | None
    is_fork: bool
    is_archived: bool
    has_code: bool
    topics: tuple[str, ...] = ()
    linked_directly: bool = False  # the story links the repo itself, not a website
    # "Warum Platz …?", written by the CommunityCurator: an explanation, not an identity
    reasons: tuple[str, ...] = field(default=(), compare=False)
    # Read for the AI section and the exclusions, never stored, like a Snapshot's README.
    # None: it could not be read. "": the repo has none.
    readme: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def key(self) -> str:
        """Two projects with the same key are the same repo."""
        return repository_key(self.repository_url)

    @property
    def owner_key(self) -> str:
        """Forge and owner: `github.com/alice` is not `codeberg.org/alice`."""
        parsed = urlsplit(self.repository_url)
        owner = next((part for part in parsed.path.split("/") if part), "")
        return f"{parsed.hostname or ''}/{owner}".casefold()

    @property
    def name(self) -> str:
        parts = [part for part in urlsplit(self.repository_url).path.split("/") if part]
        return parts[-1] if parts else ""

    @property
    def is_open_source(self) -> bool:
        return is_open_source_license(self.license_id)


def repository_key(url: str) -> str:
    """Addresses that differ only in case and a trailing slash name the same repo."""
    return url.rstrip("/").casefold()


@dataclass(frozen=True)
class CommunityEdition:
    """The selection of one day on one platform. Projects are in ranking order."""

    platform: Platform
    day: date
    main: tuple[CommunityProject, ...] = ()
    ai: tuple[CommunityProject, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "main", tuple(self.main))
        object.__setattr__(self, "ai", tuple(self.ai))
        name = f"{self.platform.name}-Ausgabe vom {self.day}"
        for section, projects in [("Hauptliste", self.main), ("AI-Sektion", self.ai)]:
            check_section(
                projects,
                language_of=lambda project: project.language,
                owner_of=lambda project: project.owner_key,
                name=f"{name}, {section}",
            )
        check_unique((project.key for project in self.main + self.ai), name)

    def projects(self, section: Section) -> tuple[CommunityProject, ...]:
        return self.main if section is Section.MAIN else self.ai


class CommunityCurator:
    def curate(
        self,
        platform: Platform,
        day: date,
        candidates: Iterable[CommunityProject],
        past_editions: Iterable[CommunityEdition] = (),
    ) -> CommunityEdition:
        """`past_editions` are the platform's own editions; their repos are under cooldown."""
        blocked = {
            project.key
            for edition in past_editions
            if in_cooldown(edition.day, day)
            for project in edition.main + edition.ai
        }
        best: dict[str, CommunityProject] = {}  # one story per repo: the best ranked one
        for candidate in candidates:
            if not _eligible(candidate) or candidate.key in blocked:
                continue
            if candidate.key not in best or _rank(candidate) < _rank(best[candidate.key]):
                best[candidate.key] = candidate
        ranked = sorted(best.values(), key=_rank)
        focus = {project.key: _ai_focus(project) for project in ranked}

        def section(wanted: Section) -> tuple[CommunityProject, ...]:
            chosen = varied(
                (p for p in ranked if focus[p.key].section is wanted),
                language_of=lambda project: project.language,
                owner_of=lambda project: project.owner_key,
            )
            return tuple(_explained(project, focus[project.key]) for project in chosen)

        return CommunityEdition(platform, day, main=section(Section.MAIN), ai=section(Section.AI))


def _rank(project: CommunityProject) -> tuple[int, int, float]:
    """The platform decides: points, then comments, then the newer story."""
    story = project.story
    return -story.points, -story.comments, -story.created_at.timestamp()


def _eligible(project: CommunityProject) -> bool:
    """Open source with code, no fork, not archived, and none of the GitHub text exclusions."""
    excluded = ExclusionPolicy().check_text(
        name=project.name,
        description=project.description,
        topics=project.topics,
        readme=project.readme,
    )
    return (
        project.is_open_source
        and project.has_code
        and not project.is_fork
        and not project.is_archived
        and excluded is None
    )


def _ai_focus(project: CommunityProject) -> AiFocus:
    return AiFocusClassifier().classify_text(
        name=project.name,
        description=project.description,
        topics=project.topics,
        readme=project.readme or "",
    )


def _explained(project: CommunityProject, focus: AiFocus) -> CommunityProject:
    """The project with its "Warum Platz …?" lines: how it was found, license, AI terms."""
    if project.linked_directly:
        found = "Die Story verlinkt das Repo direkt."
    else:
        host = (urlsplit(project.project_url).hostname or "").removeprefix("www.")
        words = shared_words(project.story.title, project.project_url, project.repository_url)
        found = f"Gefunden über einen Link auf {host}."
        if words:
            found += f" Repo und Story teilen {quoted(sorted(words))}."
    reasons = [found]
    if project.license_id == UNRECOGNIZED_LICENSE:
        reasons.append(UNRECOGNIZED_LICENSE_REASON)
    reasons += [signal.reason for signal in focus.signals]
    return replace(project, reasons=tuple(reasons))
