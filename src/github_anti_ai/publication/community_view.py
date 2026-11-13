"""Page models for the community project lists (HN, Lobsters), each with an AI section.

Both platforms store the same edition format; they differ only in the names below.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

FORMAT_VERSION = 1
_EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip


@dataclass(frozen=True)
class Platform:
    slug: str  # first part of every address: hn/, lobsters/
    name: str
    points_key: str  # what the story calls its points in the stored edition
    discussion_url: Callable[[dict], str]


def _hn_discussion(story: dict) -> str:
    return f"https://news.ycombinator.com/item?id={quote(story['id'])}"


def _lobsters_discussion(story: dict) -> str:
    return _safe_url(story.get("discussion_url")) or f"https://lobste.rs/s/{quote(story['id'])}"


HN = Platform(slug="hn", name="HN", points_key="points", discussion_url=_hn_discussion)
LOBSTERS = Platform(
    slug="lobsters", name="Lobsters", points_key="score", discussion_url=_lobsters_discussion
)

# section: (key in the stored edition, start of the heading, what the stats count: one, more)
SECTIONS = {
    "main": ("projects", "Trending auf", ("Open-Source-Projekt", "Open-Source-Projekte")),
    "ai": ("ai_projects", "AI-Projekte auf", ("AI-Projekt", "AI-Projekte")),
}


@dataclass(frozen=True)
class CommunityEntryView:
    rank: int
    title: str
    repository_url: str
    project_url: str | None
    discussion_url: str
    description: str
    language: str | None
    license_id: str | None
    points: str
    comments: str
    reasons: list[str]  # "Warum Platz …?", empty for editions from before 13.11.2026


@dataclass(frozen=True)
class CommunityEditionView:
    """One section of one day, ready for the page."""

    day: date
    section: str  # "main" or "ai"
    heading: str  # "Trending auf HN"
    title: str  # heading plus date
    url: str
    stats: str
    points_label: str
    discussion_label: str
    entries: list[CommunityEntryView]


@dataclass(frozen=True)
class CommunityDay:
    day: date
    main: CommunityEditionView
    ai: CommunityEditionView

    def section(self, name: str) -> CommunityEditionView:
        return self.main if name == "main" else self.ai


def section_url(platform: Platform, section: str) -> str:
    """Address of the newest edition of a section: hn/ or hn/ai/."""
    return f"{platform.slug}/" if section == "main" else f"{platform.slug}/ai/"


def section_heading(platform: Platform, section: str) -> str:
    return f"{SECTIONS[section][1]} {platform.name}"


def load_community_editions(directory: Path, platform: Platform) -> list[CommunityDay]:
    """All days of a platform, oldest first."""
    directory = Path(directory)
    if not directory.exists():
        return []
    days = []
    for path in sorted(directory.iterdir()):
        if not _EDITION_FILE.fullmatch(path.name):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format_version") != FORMAT_VERSION:
            raise ValueError(f"{path.name}: unbekannte {platform.name}-Ausgabeversion")
        day = date.fromisoformat(data["day"])
        days.append(
            CommunityDay(
                day=day,
                main=_edition_view(platform, "main", day, data),
                ai=_edition_view(platform, "ai", day, data),
            )
        )
    return days


def community_feed_html(view: CommunityEditionView) -> str:
    if not view.entries:
        return "<p>Heute nichts gefunden.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.repository_url)}">{escape(entry.title)}</a>'
        f" ({entry.points} {view.points_label}, {entry.comments} Kommentare)"
        f' · <a href="{escape(entry.discussion_url)}">{view.discussion_label}</a></li>'
        for entry in view.entries
    )
    return f"<ol>{items}</ol>"


def _edition_view(platform: Platform, section: str, day: date, data: dict) -> CommunityEditionView:
    key, _, (one, more) = SECTIONS[section]
    # Editions from before the AI section (13.11.2026) have no "ai_projects"
    projects = data.get(key, [])
    heading = section_heading(platform, section)
    return CommunityEditionView(
        day=day,
        section=section,
        heading=heading,
        title=f"{heading} vom {_long_date(day)}",
        url=f"{section_url(platform, section)}{day:%Y/%m/%d}/",
        stats=f"{len(projects)} {one if len(projects) == 1 else more}",
        points_label=f"{platform.name}-Punkte",
        discussion_label=f"Diskussion auf {platform.name}",
        entries=[
            _entry_view(platform, project, rank) for rank, project in enumerate(projects, 1)
        ],
    )


def _entry_view(platform: Platform, project: dict, rank: int) -> CommunityEntryView:
    story = project["story"]
    return CommunityEntryView(
        rank=rank,
        title=story["title"],
        repository_url=_safe_url(project["repository_url"]),
        project_url=_safe_url(project["project_url"]),
        discussion_url=platform.discussion_url(story),
        description=project["description"],
        language=project["language"],
        license_id=_shown_license(project["license_id"]),
        points=_number(story[platform.points_key]),
        comments=_number(story["comments"]),
        reasons=list(project.get("reasons", [])),
    )


def _shown_license(license_id: str | None) -> str | None:
    """GitHub's placeholder for an unidentified license file is not a license name."""
    return None if license_id == "NOASSERTION" else license_id


def _safe_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.hostname else None


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _long_date(day: date) -> str:
    return f"{day.day}. {_MONTHS[day.month - 1]} {day.year}"
