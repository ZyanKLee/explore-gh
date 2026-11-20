"""Page models of the GitHub list: everything about texts and numbers, without Pelican.

Publication only knows the JSON format of the editions. See docs/veroeffentlichung.md.
"""

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path

from explore_gh.publication.german import (
    age,
    decimal,
    load_edition_files,
    long_date,
    number,
    shown_license,
    web_url,
    weight,
)

# Editions until 2026-11-15 do not say over how many days they counted the gain.
FORMER_GROWTH_WINDOW_DAYS = 7
SECTION_TITLES = {"main": "Trending auf GitHub", "ai": "AI-Projekte auf GitHub"}
SECTION_PREFIXES = {"main": "", "ai": "ai/"}
SPARKLINE_WIDTH = 120
SPARKLINE_HEIGHT = 24


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
    gained_days: int  # the days the gain was counted over
    forks: str
    active_authors: int
    age: str
    score: str
    signals: tuple[SignalLine, ...]
    sparkline: str


@dataclass(frozen=True)
class SectionView:
    day: date
    section: str  # "main" or "ai"
    title: str
    url: str
    stats: str
    entries: list[EntryView]


@dataclass(frozen=True)
class GitHubDay:
    day: date
    main: SectionView
    ai: SectionView

    def section(self, name: str) -> SectionView:
        return self.main if name == "main" else self.ai

    @property
    def date(self) -> str:
        return long_date(self.day)


def load_github_days(directory: Path) -> list[GitHubDay]:
    """All days of the GitHub list, oldest first."""
    return [
        GitHubDay(
            day=date.fromisoformat(edition["day"]),
            main=section_view(edition, "main"),
            ai=section_view(edition, "ai"),
        )
        for edition in load_edition_files(directory, "GitHub-Ausgabe")
    ]


def section_url(day: date, section: str) -> str:
    return f"{SECTION_PREFIXES[section]}{day:%Y/%m/%d}/"


def section_view(edition: dict, section: str) -> SectionView:
    day = date.fromisoformat(edition["day"])
    stats = edition["stats"]
    gained_days = edition.get("growth_window_days", FORMER_GROWTH_WINDOW_DAYS)
    return SectionView(
        day=day,
        section=section,
        title=f"{SECTION_TITLES[section]} vom {long_date(day)}",
        url=section_url(day, section),
        stats=(
            f"{number(stats['assessed'])} Repos geprüft, "
            f"{number(stats['excluded'])} ausgeschlossen, "
            f"{number(stats['ai_focused'])} als AI-Thema eingestuft"
        ),
        entries=[_entry_view(entry, day, gained_days) for entry in edition["sections"][section]],
    )


def sparkline_points(history: list[int], width: int, height: int) -> str:
    """Points of an SVG polyline: one per day, the best day touches the top."""
    top = max(history, default=0)
    last = max(len(history) - 1, 1)
    return " ".join(
        f"{_coordinate(index * width / last)},"
        f"{_coordinate(height - (stars / top * height if top else 0))}"
        for index, stars in enumerate(history)
    )


def feed_html(view: SectionView) -> str:
    """The list of a section as plain HTML, for feed readers."""
    if not view.entries:
        return "<p>Heute nichts gefunden.</p>"
    items = "".join(
        f'<li><a href="{escape(entry.url)}">{escape(entry.repo)}</a>'
        f"{': ' + escape(entry.description) if entry.description else ''}"
        f" ({escape(entry.language or 'ohne Sprache')}, {entry.stars} Sterne,"
        f" {entry.gained} in {entry.gained_days} Tagen)</li>"
        for entry in view.entries
    )
    return f"<ol>{items}</ol>"


def _entry_view(entry: dict, day: date, gained_days: int) -> EntryView:
    return EntryView(
        rank=entry["rank"],
        repo=entry["repo"],
        url=entry["url"],
        description=entry["description"],
        homepage=web_url(entry["homepage"]),
        language=entry["language"],
        license=shown_license(entry["license"]),
        topics=tuple(entry["topics"]),
        stars=number(entry["stars"]),
        gained=f"+{number(entry['stars_gained'])}",
        gained_days=gained_days,
        forks=number(entry["forks"]),
        active_authors=entry["active_authors"],
        age=age(datetime.fromisoformat(entry["created_at"]).date(), day),
        score=decimal(entry["score"]),
        signals=tuple(
            SignalLine(weight=weight(signal["weight"]), reason=signal["reason"])
            for signal in entry["signals"]
        ),
        sparkline=sparkline_points(entry["star_history"], SPARKLINE_WIDTH, SPARKLINE_HEIGHT),
    )


def _coordinate(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")
