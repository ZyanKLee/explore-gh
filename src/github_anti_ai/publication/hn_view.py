"""Page models for the independent Hacker News project list."""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

HN_FORMAT_VERSION = 1
_EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip


@dataclass(frozen=True)
class HnEntryView:
    rank: int
    title: str
    repository_url: str
    project_url: str | None
    story_url: str
    description: str
    language: str | None
    license_id: str | None
    points: str
    comments: str


@dataclass(frozen=True)
class HnEditionView:
    day: date
    title: str
    url: str
    stats: str
    entries: list[HnEntryView]


def load_hn_editions(directory: Path) -> list[HnEditionView]:
    directory = Path(directory)
    if not directory.exists():
        return []
    editions = []
    for path in sorted(directory.iterdir()):
        if not _EDITION_FILE.fullmatch(path.name):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format_version") != HN_FORMAT_VERSION:
            raise ValueError(f"{path.name}: unbekannte HN-Ausgabeversion")
        editions.append(_edition_view(data))
    return editions


def hn_archive_url(day: date) -> str:
    return f"hn/{day:%Y/%m/%d}/"


def _edition_view(data: dict) -> HnEditionView:
    day = date.fromisoformat(data["day"])
    projects = data["projects"]
    return HnEditionView(
        day=day,
        title=f"Trending auf HN vom {_long_date(day)}",
        url=hn_archive_url(day),
        stats=f"{len(projects)} Open-Source-Projekte",
        entries=[_entry_view(project, rank) for rank, project in enumerate(projects, 1)],
    )


def _entry_view(project: dict, rank: int) -> HnEntryView:
    story = project["story"]
    return HnEntryView(
        rank=rank,
        title=story["title"],
        repository_url=_safe_url(project["repository_url"]),
        project_url=_safe_url(project["project_url"]),
        story_url=f"https://news.ycombinator.com/item?id={quote(story['id'])}",
        description=project["description"],
        language=project["language"],
        license_id=_shown_license(project["license_id"]),
        points=_number(story["points"]),
        comments=_number(story["comments"]),
    )


def hn_feed_html(view: HnEditionView) -> str:
    if not view.entries:
        return "<p>Heute nichts gefunden.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.repository_url)}">{escape(entry.title)}</a>'
        f" ({entry.points} HN-Punkte, {entry.comments} Kommentare)"
        f' · <a href="{escape(entry.story_url)}">Diskussion auf HN</a></li>'
        for entry in view.entries
    )
    return f"<ol>{items}</ol>"


def _safe_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.hostname else None


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _long_date(day: date) -> str:
    return f"{day.day}. {_MONTHS[day.month - 1]} {day.year}"

def _shown_license(license_id: str | None) -> str | None:
    """GitHub's placeholder for an unidentified license file is not a license name."""
    return None if license_id == "NOASSERTION" else license_id
