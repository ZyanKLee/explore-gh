"""Long-term data as gzipped JSON lines, one file per day: YYYY-MM-DD.jsonl.gz

Every line names its day and its format, so that tools can read a whole directory at once.
The same records always give the same bytes: the files live in git.
"""

import gzip
import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from github_anti_ai.domain.history import DailyRecord
from github_anti_ai.domain.model import RepoId, Section

FORMAT_VERSION = 1
SUFFIX = ".jsonl.gz"
DECIMALS = 2  # of scores and weights. More would only make the files bigger.


class JsonDailyRecordStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def save(self, day: date, records: Sequence[DailyRecord]) -> None:
        """Replaces the records of that day."""
        if any(record.day != day for record in records):
            raise ValueError(f"Nicht alle Tageswerte gehören zum {day}")
        ordered = sorted(records, key=lambda record: str(record.repo).lower())
        lines = "".join(
            json.dumps(_to_json(record), ensure_ascii=False, separators=(",", ":")) + "\n"
            for record in ordered
        )
        self._directory.mkdir(parents=True, exist_ok=True)
        # mtime=0: otherwise the time of writing would end up in the file
        self._path(day).write_bytes(gzip.compress(lines.encode(), mtime=0))

    def load(self, day: date) -> list[DailyRecord]:
        path = self._path(day)
        if not path.exists():
            return []
        records = []
        for line in gzip.decompress(path.read_bytes()).decode().splitlines():
            data = json.loads(line)
            if data.get("v") != FORMAT_VERSION:
                raise ValueError(
                    f"{path.name}: unbekanntes Format {data.get('v')!r}, "
                    f"erwartet wird {FORMAT_VERSION}"
                )
            records.append(_from_json(data))
        return records

    def days(self) -> list[date]:
        """The days that have records, in order."""
        if not self._directory.exists():
            return []
        found = []
        for path in self._directory.glob(f"*{SUFFIX}"):
            try:
                found.append(date.fromisoformat(path.name.removesuffix(SUFFIX)))
            except ValueError:
                continue
        return sorted(found)

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}{SUFFIX}"


def _to_json(record: DailyRecord) -> dict:
    return {
        "v": FORMAT_VERSION,
        "day": record.day.isoformat(),
        "repo": str(record.repo),
        "stars": record.stars,
        "forks": record.forks,
        "gained": record.stars_gained,
        "score": round(record.score, DECIMALS),
        "section": record.section.value,
        "exclusion": record.exclusion,
        "signals": [[kind, round(weight, DECIMALS)] for kind, weight in record.signals],
        "rank": record.rank,
        "language": record.language,
        "created_at": record.created_at.isoformat(),
    }


def _from_json(data: dict) -> DailyRecord:
    return DailyRecord(
        day=date.fromisoformat(data["day"]),
        repo=RepoId.parse(data["repo"]),
        stars=data["stars"],
        forks=data["forks"],
        stars_gained=data["gained"],
        score=data["score"],
        section=Section(data["section"]),
        exclusion=data["exclusion"],
        signals=tuple((kind, weight) for kind, weight in data["signals"]),
        rank=data["rank"],
        language=data["language"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
