"""Page models of the community lists (HN, Lobsters, forums), each with an AI section.

All store the same format; they differ in the names below. In the weekly forums list each
story names its origin, and so its points and discussion.
"""

from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

from github_anti_ai.publication.german import (
    load_edition_files,
    long_date,
    number,
    shown_license,
)


@dataclass(frozen=True)
class Platform:
    slug: str  # first part of every address: hn/, lobsters/, forums/
    name: str
    points_key: str  # what the stored story calls its points
    discussion_pattern: str  # if the story does not name its discussion page
    place: str = ""  # "auf HN"; empty: "auf" and the name
    weekly: bool = False

    @property
    def where(self) -> str:
        return self.place or f"auf {self.name}"

    def discussion_url(self, story: dict) -> str:
        return _web_url(story.get("discussion_url")) or self.discussion_pattern.format(
            id=quote(story["id"])
        )


HN = Platform("hn", "HN", "points", "https://news.ycombinator.com/item?id={id}")
LOBSTERS = Platform("lobsters", "Lobsters", "score", "https://lobste.rs/s/{id}")
FORUMS = Platform("forums", "Foren", "points", "{id}", place="in den Foren", weekly=True)
PLATFORMS = (HN, LOBSTERS, FORUMS)

# section: (key in the stored edition, start of the heading, what the stats count: one, more)
SECTIONS = {
    "main": ("projects", "Trending", ("Open-Source-Projekt", "Open-Source-Projekte")),
    "ai": ("ai_projects", "AI-Projekte", ("AI-Projekt", "AI-Projekte")),
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
    points_label: str  # "HN-Punkte", "Punkte auf Lobsters"
    discussion_label: str  # "Diskussion auf HN"
    comments: str
    reasons: list[str]  # "Warum Platz …?", empty for editions before 2026-11-13


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
    empty_text: str
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
    return f"{SECTIONS[section][1]} {platform.where}"


def load_community_editions(directory: Path, platform: Platform) -> list[CommunityDay]:
    """All days of a platform, oldest first."""
    days = []
    for data in load_edition_files(directory, f"{platform.name}-Ausgabe"):
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
        return f"<p>{view.empty_text}.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.repository_url)}">{escape(entry.title)}</a>'
        f" ({entry.points} {escape(entry.points_label)}, {entry.comments} Kommentare)"
        f' · <a href="{escape(entry.discussion_url)}">{escape(entry.discussion_label)}</a></li>'
        for entry in view.entries
    )
    return f"<ol>{items}</ol>"


def _edition_view(platform: Platform, section: str, day: date, data: dict) -> CommunityEditionView:
    key, _, (one, more) = SECTIONS[section]
    projects = data.get(key, [])  # editions before 2026-11-13 have no AI section
    heading = section_heading(platform, section)
    return CommunityEditionView(
        day=day,
        section=section,
        heading=heading,
        title=f"{heading}, Woche vom {long_date(day)}"
        if platform.weekly
        else f"{heading} vom {long_date(day)}",
        url=f"{section_url(platform, section)}{day:%Y/%m/%d}/",
        stats=f"{len(projects)} {one if len(projects) == 1 else more}",
        points_label=f"{platform.name}-Punkte",
        discussion_label=f"Diskussion auf {platform.name}",
        empty_text="Diese Woche nichts gefunden" if platform.weekly else "Heute nichts gefunden",
        entries=[_entry_view(platform, project, rank) for rank, project in enumerate(projects, 1)],
    )


def _entry_view(platform: Platform, project: dict, rank: int) -> CommunityEntryView:
    story = project["story"]
    origin = story.get("origin")
    if origin:
        points_label = f"{origin['points_label']} auf {origin['name']}"
        discussion_label = f"Diskussion auf {origin['name']}"
    else:
        points_label = f"{platform.name}-Punkte"
        discussion_label = f"Diskussion auf {platform.name}"
    return CommunityEntryView(
        rank=rank,
        title=story["title"],
        repository_url=_web_url(project["repository_url"]),
        project_url=_web_url(project["project_url"]),
        discussion_url=platform.discussion_url(story),
        description=project["description"],
        language=project["language"],
        license_id=shown_license(project["license_id"]),
        points=number(story[platform.points_key]),
        points_label=points_label,
        discussion_label=discussion_label,
        comments=number(story["comments"]),
        reasons=list(project.get("reasons", [])),
    )


def _web_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.hostname else None
