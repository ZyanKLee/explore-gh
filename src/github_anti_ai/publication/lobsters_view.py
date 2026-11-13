"""Page models for the independent Lobsters project list."""

import json
import re
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

LOBSTERS_FORMAT_VERSION = 1
_EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip


@dataclass(frozen=True)
class LobstersEntryView:
    rank: int
    title: str
    repository_url: str
    project_url: str | None
    discussion_url: str
    description: str
    language: str | None
    license_id: str
    score: str
    comments: str


@dataclass(frozen=True)
class LobstersEditionView:
    day: date
    title: str
    url: str
    stats: str
    entries: list[LobstersEntryView]


def load_lobsters_editions(directory: Path) -> list[LobstersEditionView]:
    directory = Path(directory)
    if not directory.exists():
        return []
    editions = []
    for path in sorted(directory.iterdir()):
        if not _EDITION_FILE.fullmatch(path.name):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format_version") != LOBSTERS_FORMAT_VERSION:
            raise ValueError(f"{path.name}: unbekannte Lobsters-Ausgabeversion")
        editions.append(_edition_view(data))
    return editions


def lobsters_archive_url(day: date) -> str:
    return f"lobsters/{day:%Y/%m/%d}/"


def _edition_view(data: dict) -> LobstersEditionView:
    day = date.fromisoformat(data["day"])
    projects = data["projects"]
    return LobstersEditionView(
        day=day,
        title=f"Trending auf Lobsters vom {_long_date(day)}",
        url=lobsters_archive_url(day),
        stats=f"{len(projects)} Open-Source-Projekte",
        entries=[_entry_view(project, rank) for rank, project in enumerate(projects, 1)],
    )


def _entry_view(project: dict, rank: int) -> LobstersEntryView:
    story = project["story"]
    return LobstersEntryView(
        rank=rank,
        title=story["title"],
        repository_url=_safe_url(project["repository_url"]),
        project_url=_safe_url(project["project_url"]),
        discussion_url=_safe_url(story["discussion_url"])
        or f"https://lobste.rs/s/{quote(story['id'])}",
        description=project["description"],
        language=project["language"],
        license_id=project["license_id"],
        score=_number(story["score"]),
        comments=_number(story["comments"]),
    )


def lobsters_feed_html(view: LobstersEditionView) -> str:
    if not view.entries:
        return "<p>Heute nichts gefunden.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.repository_url)}">{escape(entry.title)}</a>'
        f" ({entry.score} Punkte, {entry.comments} Kommentare)"
        f' · <a href="{escape(entry.discussion_url)}">Diskussion auf Lobsters</a></li>'
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