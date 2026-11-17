"""How the collection of a day ended: snapshots/YYYY-MM-DD.status.json"""

import json
from datetime import date
from pathlib import Path

from github_anti_ai.adapters.files import day_files, read_json
from github_anti_ai.application.ports import CollectionStatus

SUFFIX = ".status.json"


class JsonCollectionStatusStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def save(self, status: CollectionStatus) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        data = {
            "day": status.day.isoformat(),
            "discovered": status.discovered,
            "collected": status.collected,
            "failed": status.failed,
        }
        self._path(status.day).write_text(json.dumps(data, indent=2) + "\n")

    def load(self, day: date) -> CollectionStatus | None:
        path = self._path(day)
        if not path.exists():
            return None
        data = read_json(path)
        return CollectionStatus(
            day=date.fromisoformat(data["day"]),
            discovered=data["discovered"],
            collected=data["collected"],
            failed=data["failed"],
        )

    def prune(self, before: date) -> None:
        for day, path in day_files(self._directory, SUFFIX).items():
            if day < before:
                path.unlink()

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}{SUFFIX}"
