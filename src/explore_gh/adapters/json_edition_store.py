"""Editions of the GitHub list as readable JSON, one file per day: editions/YYYY-MM-DD.json

The format is the contract with Publication. See docs/ausgabe.md, "Speicherformat".
"""

from datetime import UTC, date, datetime
from pathlib import Path

from explore_gh.adapters.files import day_files, read_json, write_new_json
from explore_gh.application.ports import AlreadyPublished
from explore_gh.domain.edition import Edition, EditionStats, Entry
from explore_gh.domain.model import GROWTH_WINDOW_DAYS, RepoId, Section, Signal, StarHistory

FORMAT_VERSION = 1


class JsonEditionStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def save(self, edition: Edition) -> None:
        if not write_new_json(self._path(edition.day), to_json(edition)):
            raise AlreadyPublished(edition.day)

    def load(self, day: date) -> Edition | None:
        path = self._path(day)
        return from_json(read_json(path)) if path.exists() else None

    def since(self, day: date) -> list[Edition]:
        return [
            from_json(read_json(path))
            for found, path in day_files(self._directory, ".json").items()
            if found >= day
        ]

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}.json"


def to_json(edition: Edition) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "day": edition.day.isoformat(),
        # the days stars_gained of each entry was counted over
        "growth_window_days": GROWTH_WINDOW_DAYS,
        "stats": {
            "assessed": edition.stats.assessed,
            "excluded": edition.stats.excluded,
            "ai_focused": edition.stats.ai_focused,
        },
        "sections": {
            section.value: [
                _entry_to_json(rank, entry)
                for rank, entry in enumerate(edition.entries(section), start=1)
            ]
            for section in Section
        },
    }


def _entry_to_json(rank: int, entry: Entry) -> dict:
    return {
        "rank": rank,
        "repo": str(entry.repo),
        "url": entry.repo.url,
        "description": entry.description,
        "homepage": entry.homepage,
        "language": entry.primary_language,
        "topics": list(entry.topics),
        "stars": entry.stars,
        "stars_gained": entry.star_history.gained(),
        "star_history": list(entry.star_history.daily),
        "created_at": _time(entry.created_at),
        "pushed_at": _time(entry.pushed_at) if entry.pushed_at else None,
        "license": entry.license,
        "forks": entry.forks,
        "active_authors": entry.active_authors,
        "score": entry.score,
        "signals": [
            {"kind": s.kind, "weight": s.weight, "reason": s.reason} for s in entry.signals
        ],
    }


def from_json(data: dict) -> Edition:
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Ausgabe vom {data.get('day')}: unbekanntes Format")
    sections = data["sections"]
    return Edition(
        day=date.fromisoformat(data["day"]),
        main=tuple(_entry_from_json(e) for e in sections[Section.MAIN.value]),
        ai=tuple(_entry_from_json(e) for e in sections[Section.AI.value]),
        stats=EditionStats(**data["stats"]),
    )


def _entry_from_json(data: dict) -> Entry:
    return Entry(
        repo=RepoId.parse(data["repo"]),
        score=data["score"],
        signals=tuple(Signal(**s) for s in data["signals"]),
        description=data["description"],
        homepage=data["homepage"],
        primary_language=data["language"],
        topics=tuple(data["topics"]),
        stars=data["stars"],
        star_history=StarHistory(tuple(data["star_history"])),
        created_at=datetime.fromisoformat(data["created_at"]),
        pushed_at=datetime.fromisoformat(data["pushed_at"]) if data["pushed_at"] else None,
        license=data["license"],
        forks=data["forks"],
        active_authors=data["active_authors"],
    )


def _time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
