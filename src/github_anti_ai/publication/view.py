"""Page models of the site: everything about texts and numbers, without Pelican.

Publication only knows the JSON format of the editions, see docs/ausgabe.md.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

FORMAT_VERSION = 1
SECTION_TITLES = {"main": "Trending auf GitHub", "ai": "AI-Projekte auf GitHub"}
SECTION_PREFIXES = {"main": "", "ai": "ai/"}
MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip
SPARKLINE_WIDTH = 120
SPARKLINE_HEIGHT = 24

_EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")


@dataclass(frozen=True)
class SignalLine:
    weight: str
    reason: str


@dataclass(frozen=True)
class EntryView:
    rank: int
    repo: str
    url: str
    description: str
    homepage: str | None
    language: str | None
    license: str | None
    topics: tuple[str, ...]
    stars: str
    gained: str
    forks: str
    active_authors: int
    age: str
    score: str
    signals: tuple[SignalLine, ...]
    sparkline: str


@dataclass(frozen=True)
class SectionView:
    day: date
    section: str
    title: str
    url: str
    stats: str
    entries: list[EntryView]


def load_editions(directory: Path) -> list[dict]:
    """All editions of the directory in date order. An unknown format stops the build."""
    directory = Path(directory)
    if not directory.exists():
        return []
    editions = []
    for path in sorted(directory.iterdir()):
        if not _EDITION_FILE.fullmatch(path.name):
            continue
        edition = json.loads(path.read_text(encoding="utf-8"))
        if edition.get("format_version") != FORMAT_VERSION:
            raise ValueError(
                f"{path.name}: unbekannte format_version {edition.get('format_version')!r}, "
                f"erwartet wird {FORMAT_VERSION}"
            )
        editions.append(edition)
    return editions


def long_date(day: date) -> str:
    return f"{day.day}. {MONTHS[day.month - 1]} {day.year}"


def section_url(day: date, section: str) -> str:
    return f"{SECTION_PREFIXES[section]}{day:%Y/%m/%d}/"


def section_view(edition: dict, section: str) -> SectionView:
    day = date.fromisoformat(edition["day"])
    stats = edition["stats"]
    return SectionView(
        day=day,
        section=section,
        title=f"{SECTION_TITLES[section]} vom {long_date(day)}",
        url=section_url(day, section),
        stats=(
            f"{_number(stats['assessed'])} Repos geprüft, "
            f"{_number(stats['excluded'])} ausgeschlossen, "
            f"{_number(stats['ai_focused'])} als AI-Thema eingestuft"
        ),
        entries=[_entry_view(entry, day) for entry in edition["sections"][section]],
    )


def sparkline_points(history: list[int], width: int, height: int) -> str:
    """Points of an SVG polyline: one per day, the highest day touches the top."""
    top = max(history, default=0)
    last = max(len(history) - 1, 1)
    return " ".join(
        f"{_coordinate(index * width / last)},"
        f"{_coordinate(height - (stars / top * height if top else 0))}"
        for index, stars in enumerate(history)
    )


def _entry_view(entry: dict, day: date) -> EntryView:
    homepage = entry["homepage"] or ""
    return EntryView(
        rank=entry["rank"],
        repo=entry["repo"],
        url=entry["url"],
        description=entry["description"],
        # text from GitHub: only real web addresses may become links
        homepage=homepage if homepage.startswith(("http://", "https://")) else None,
        language=entry["language"],
        license=None if entry["license"] == "NOASSERTION" else entry["license"],
        topics=tuple(entry["topics"]),
        stars=_number(entry["stars"]),
        gained=f"+{_number(entry['stars_gained'])}",
        forks=_number(entry["forks"]),
        active_authors=entry["active_authors"],
        age=_age(datetime.fromisoformat(entry["created_at"]).date(), day),
        score=_decimal(entry["score"]),
        signals=tuple(
            SignalLine(weight=_weight(signal["weight"]), reason=signal["reason"])
            for signal in entry["signals"]
        ),
        sparkline=sparkline_points(entry["star_history"], SPARKLINE_WIDTH, SPARKLINE_HEIGHT),
    )


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _decimal(value: float) -> str:
    text = f"{abs(value):.1f}".replace(".", ",")
    return f"−{text}" if value < 0 else text


def _weight(value: float) -> str:
    if value == 0:
        return "0"
    return f"+{_decimal(value)}" if value > 0 else _decimal(value)


def _age(created: date, day: date) -> str:
    days = (day - created).days
    if days <= 0:
        return "heute erstellt"
    return "1 Tag alt" if days == 1 else f"{days} Tage alt"


def _coordinate(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")


def feed_html(view: SectionView) -> str:
    """The list of a section as plain HTML, for feed readers."""
    from html import escape

    if not view.entries:
        return "<p>Heute nichts gefunden.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.url)}">{escape(entry.repo)}</a>'
        f"{': ' + escape(entry.description) if entry.description else ''}"
        f" ({escape(entry.language or 'ohne Sprache')}, {entry.stars} Sterne,"
        f" {entry.gained} in 7 Tagen)</li>"
        for entry in view.entries
    )
    return f"<ol>{items}</ol>"
