"""Editions as readable JSON, one file per day. The format is the contract with
Publication (Pelican), see docs/ausgabe.md."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.edition import Edition, EditionStats, Entry
from github_anti_ai.domain.model import RepoId, Section, Signal, StarHistory

FORMAT_VERSION = 1


class JsonEditionStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def save(self, edition: Edition) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(_to_json(edition), indent=2, ensure_ascii=False) + "\n"
        try:
            with self._path(edition.day).open("x", encoding="utf-8") as file:
                file.write(text)
        except FileExistsError:
            raise AlreadyPublished(edition.day) from None

    def load(self, day: date) -> Edition | None:
        path = self._path(day)
        if not path.exists():
            return None
        return _from_json(json.loads(path.read_text(encoding="utf-8")))

    def since(self, day: date) -> list[Edition]:
        if not self._directory.exists():
            return []
        days = []
        for path in self._directory.glob("*.json"):
            try:
                days.append(date.fromisoformat(path.stem))
            except ValueError:
                continue
        return [self.load(d) for d in sorted(days) if d >= day]

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}.json"


def _to_json(edition: Edition) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "day": edition.day.isoformat(),
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


def _from_json(data: dict) -> Edition:
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
        star_history=StarHistory(daily=tuple(data["star_history"])),
        created_at=datetime.fromisoformat(data["created_at"]),
        pushed_at=datetime.fromisoformat(data["pushed_at"]) if data["pushed_at"] else None,
        license=data["license"],
        forks=data["forks"],
        active_authors=data["active_authors"],
    )


def _time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
