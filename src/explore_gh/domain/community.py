"""The community lists: trending open source projects on HN and in small forums.

All lists follow the same rules. They differ in their Platform, and the forums list ranks
stories of several origins by the multiple of their origin's threshold.
See docs/community.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlsplit

from explore_gh.domain.ai_focus import AiFocus, AiFocusClassifier
from explore_gh.domain.curation import check_section, check_unique, in_cooldown, varied
from explore_gh.domain.exclusion import ExclusionPolicy
from explore_gh.domain.model import Section
from explore_gh.domain.story_relation import shared_words
from explore_gh.domain.text import quoted
from explore_gh.domain.withdrawal import Withdrawal

# Which stories the searches ask for
HN_STORY_WINDOW = timedelta(hours=48)
HN_MIN_STORY_POINTS = 50
# The weekly forums list takes the stories that are 1 to 8 days old on its day
FORUMS_MIN_STORY_AGE = timedelta(days=1)
FORUMS_MAX_STORY_AGE = timedelta(days=8)
LOBSTERS_MIN_POINTS = 10
LEMMY_MIN_POINTS = 15
LEMMY_COMMUNITIES = (
    "programming", "rust", "devops", "opensource@lemmy.ml", "linux@lemmy.ml",
    "selfhosted@lemmy.world",
)  # fmt: skip
MASTODON_TAGS = ("opensource", "foss", "rust", "linux")
# Mastodon has no threshold for now: favourites and boosts are rare. Its stories are ranked
# as if 5 reactions were the threshold.
MASTODON_REFERENCE_POINTS = 5

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
    slug: str  # first part of every address and name of the data directory: hn, forums
    name: str
    discussion_url_pattern: str  # with {id}
    weekly: bool = False  # one edition a week, on Monday

    def discussion_url(self, story_id: str) -> str:
        return self.discussion_url_pattern.format(id=quote(story_id))


HN = Platform("hn", "HN", "https://news.ycombinator.com/item?id={id}")
# Daily until 2026-11-17, its editions stay in the archive. Since then part of FORUMS.
LOBSTERS = Platform("lobsters", "Lobsters", "https://lobste.rs/s/{id}")
FORUMS = Platform("forums", "Foren", "{id}", weekly=True)  # stories name their discussion
PLATFORMS = (HN, LOBSTERS, FORUMS)


def edition_day(platform: Platform, today: date) -> date:
    """The day an edition belongs to: today, or the Monday of this week for a weekly list."""
    return today - timedelta(days=today.weekday()) if platform.weekly else today


@dataclass(frozen=True)
class Origin:
    """Where a story of the forums list comes from, with the threshold of that place."""

    name: str  # "Lobsters", "Lemmy c/rust", "Mastodon #rust"
    reference_points: int  # the rank is points divided by this
    min_points: int  # fewer points: the story is left out
    points_label: str = "Punkte"

    def reason(self, points: int) -> str:
        multiple = f"{points / self.reference_points:.1f}".replace(".", ",")
        if self.min_points == self.reference_points:
            return (
                f"{points} {self.points_label} auf {self.name}, das {multiple}-Fache der "
                f"Schwelle von {self.reference_points}."
            )
        return (
            f"{points} {self.points_label} auf {self.name}, das {multiple}-Fache der "
            f"Bezugsgröße von {self.reference_points}. Testweise ohne Schwelle."
        )


LOBSTERS_ORIGIN = Origin("Lobsters", LOBSTERS_MIN_POINTS, LOBSTERS_MIN_POINTS)


def lemmy_origin(community: str) -> Origin:
    """`rust` and `linux@lemmy.ml` give "Lemmy c/rust" and "Lemmy c/linux@lemmy.ml"."""
    return Origin(f"Lemmy c/{community}", LEMMY_MIN_POINTS, LEMMY_MIN_POINTS)


def mastodon_origin(tag: str) -> Origin:
    return Origin(f"Mastodon #{tag}", MASTODON_REFERENCE_POINTS, 0, "Reaktionen")


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    url: str  # what the story links: a repo or a website; "" for a post with text only
    discussion_url: str
    points: int  # HN points, Lobsters score, Lemmy score, Mastodon favourites and boosts
    comments: int
    created_at: datetime
    origin: Origin | None = None  # only in the forums list
    # Links in the text of the first post, never in replies. Read, never stored.
    links: tuple[str, ...] = field(default=(), compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "links", tuple(self.links))

    @property
    def relative_points(self) -> float:
        """The multiple of the origin's reference points; plain points without an origin."""
        return self.points / self.origin.reference_points if self.origin else self.points

    @property
    def reaches_threshold(self) -> bool:
        return self.origin is None or self.points >= self.origin.min_points


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
    found_in_post: bool = False  # the text of the first post links the repo
    # "Warum Platz …?", written by the CommunityCurator: an explanation, not an identity
    reasons: tuple[str, ...] = field(default=(), compare=False)
    # The other stories that link the repo, in ranking order. Their discussions are
    # linked on the page. Written by the CommunityCurator.
    other_stories: tuple[Story, ...] = field(default=(), compare=False)
    # Read for the AI section and the exclusions, never stored, like a Snapshot's README.
    # None: it could not be read. "": the repo has none.
    readme: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "other_stories", tuple(self.other_stories))

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
    """The selection of one day (one week, for a weekly list) on one platform.

    Projects are in ranking order. A weekly edition belongs to the Monday of its week.
    """

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
        withdrawals: Iterable[Withdrawal] = (),
    ) -> CommunityEdition:
        """`past_editions` are the platform's own editions; their repos are under cooldown.
        Withdrawn repos never come back."""
        withdrawals = list(withdrawals)
        blocked = {
            project.key
            for edition in past_editions
            if in_cooldown(edition.day, day)
            for project in edition.main + edition.ai
        }
        found: dict[str, list[CommunityProject]] = {}  # all stories of a repo
        for candidate in candidates:
            if (
                _eligible(candidate)
                and candidate.key not in blocked
                and not any(w.names(candidate.repository_url) for w in withdrawals)
            ):
                found.setdefault(candidate.key, []).append(candidate)
        for stories in found.values():
            stories.sort(key=_rank)
        ranked = sorted((stories[0] for stories in found.values()), key=_rank)
        focus = {project.key: _ai_focus(project) for project in ranked}

        def section(wanted: Section) -> tuple[CommunityProject, ...]:
            chosen = varied(
                (p for p in ranked if focus[p.key].section is wanted),
                language_of=lambda project: project.language,
                owner_of=lambda project: project.owner_key,
            )
            return tuple(
                _explained(project, focus[project.key], found[project.key]) for project in chosen
            )

        return CommunityEdition(platform, day, main=section(Section.MAIN), ai=section(Section.AI))


def _rank(project: CommunityProject) -> tuple[float, int, float]:
    """The platform decides: points (their multiple of the threshold in the forums list),
    then comments, then the newer story."""
    story = project.story
    return -story.relative_points, -story.comments, -story.created_at.timestamp()


def _eligible(project: CommunityProject) -> bool:
    """Open source with code, no fork, not archived, and none of the GitHub text exclusions."""
    excluded = ExclusionPolicy().check_text(
        name=project.name,
        description=project.description,
        topics=project.topics,
        readme=project.readme,
    )
    return (
        project.story.reaches_threshold
        and project.is_open_source
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


def _explained(
    project: CommunityProject, focus: AiFocus, all_stories: Iterable[CommunityProject] = ()
) -> CommunityProject:
    """The project with its "Warum Platz …?" lines: how it was found, its points and other
    origins (forums list), license, AI terms."""
    if project.linked_directly:
        found = "Die Story verlinkt das Repo direkt."
    elif project.found_in_post:
        words = shared_words(project.story.title, project.story.url, project.repository_url)
        found = "Gefunden im ersten Beitrag."
        if words:
            found += f" Repo und Story teilen {quoted(sorted(words))}."
    else:
        host = (urlsplit(project.project_url).hostname or "").removeprefix("www.")
        words = shared_words(project.story.title, project.project_url, project.repository_url)
        found = f"Gefunden über einen Link auf {host}."
        if words:
            found += f" Repo und Story teilen {quoted(sorted(words))}."
    reasons = [found]
    story = project.story
    if story.origin:
        reasons.append(story.origin.reason(story.points))
        for other in all_stories:
            origin = other.story.origin
            if other is not project and origin and origin != story.origin:
                reasons.append(
                    f"Auch auf {origin.name}, {other.story.points} {origin.points_label}."
                )
    if project.license_id == UNRECOGNIZED_LICENSE:
        reasons.append(UNRECOGNIZED_LICENSE_REASON)
    reasons += [signal.reason for signal in focus.signals]
    return replace(
        project, reasons=tuple(reasons), other_stories=_other_stories(project, all_stories)
    )


def _other_stories(project: CommunityProject, all_stories: Iterable[CommunityProject]):
    """Every other discussion of the repo, once. `all_stories` come in ranking order."""
    seen = {project.story.discussion_url}
    others = []
    for other in all_stories:
        if other.story.discussion_url not in seen:
            seen.add(other.story.discussion_url)
            others.append(other.story)
    return tuple(others)
