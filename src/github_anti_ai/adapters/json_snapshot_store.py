"""Snapshots as gzipped JSON lines, one file per day: snapshots/YYYY-MM-DD.jsonl.gz

Working data, not in git. Each run appends a gzip member; gzip files may be concatenated.
"""

import gzip
import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from github_anti_ai.adapters.files import day_files
from github_anti_ai.domain.model import Commit, RepoId, Snapshot, StarHistory

SUFFIX = ".jsonl.gz"


class JsonSnapshotStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def append(self, day: date, snapshots: Sequence[Snapshot]) -> None:
        if not snapshots:
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        lines = "".join(json.dumps(to_json(s), ensure_ascii=False) + "\n" for s in snapshots)
        with self._path(day).open("ab") as file:
            file.write(gzip.compress(lines.encode()))

    def load(self, day: date) -> list[Snapshot]:
        """The latest snapshot of each repo of that day."""
        path = self._path(day)
        if not path.exists():
            return []
        latest: dict[RepoId, Snapshot] = {}
        for line in gzip.decompress(path.read_bytes()).decode().splitlines():
            snapshot = from_json(json.loads(line))
            latest[snapshot.repo] = snapshot
        return list(latest.values())

    def prune(self, before: date) -> None:
        for day, path in day_files(self._directory, SUFFIX).items():
            if day < before:
                path.unlink()

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}{SUFFIX}"


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_time(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def to_json(snapshot: Snapshot) -> dict:
    return {
        "repo": str(snapshot.repo),
        "taken_at": _time(snapshot.taken_at),
        "facts_at": _time(snapshot.facts_at),
        "description": snapshot.description,
        "homepage": snapshot.homepage,
        "topics": list(snapshot.topics),
        "primary_language": snapshot.primary_language,
        "created_at": _time(snapshot.created_at),
        "pushed_at": _time(snapshot.pushed_at),
        "stars": snapshot.stars,
        "forks": snapshot.forks,
        "pull_requests": snapshot.pull_requests,
        "recent_issue_authors": snapshot.recent_issue_authors,
        "is_fork": snapshot.is_fork,
        "is_archived": snapshot.is_archived,
        "is_mirror": snapshot.is_mirror,
        "license": snapshot.license,
        "root_files": list(snapshot.root_files),
        "readme": snapshot.readme,
        "recent_commits": [
            {
                "committed_at": _time(c.committed_at),
                "author": c.author,
                "is_bot": c.is_bot,
                "co_authors": list(c.co_authors),
                "headline": c.headline,
            }
            for c in snapshot.recent_commits
        ],
        "star_history": list(snapshot.star_history.daily),
        "owner_created_at": _time(snapshot.owner_created_at),
        "owner_contributed_to": snapshot.owner_contributed_to,
    }


def from_json(data: dict) -> Snapshot:
    """Also reads the files of earlier versions: without facts_at and owner history, and
    with fields no rule uses any more (open_issues, watchers, is_template)."""
    return Snapshot(
        repo=RepoId.parse(data["repo"]),
        taken_at=_parse_time(data["taken_at"]),
        facts_at=_parse_time(data.get("facts_at")),
        description=data["description"],
        homepage=data["homepage"],
        topics=tuple(data["topics"]),
        primary_language=data["primary_language"],
        created_at=_parse_time(data["created_at"]),
        pushed_at=_parse_time(data["pushed_at"]),
        stars=data["stars"],
        forks=data["forks"],
        pull_requests=data["pull_requests"],
        recent_issue_authors=data["recent_issue_authors"],
        is_fork=data["is_fork"],
        is_archived=data["is_archived"],
        is_mirror=data["is_mirror"],
        license=data["license"],
        root_files=tuple(data["root_files"]),
        readme=data["readme"],
        recent_commits=tuple(
            Commit(
                committed_at=_parse_time(c["committed_at"]),
                author=c["author"],
                is_bot=c["is_bot"],
                co_authors=tuple(c["co_authors"]),
                headline=c["headline"],
            )
            for c in data["recent_commits"]
        ),
        star_history=StarHistory(tuple(data["star_history"])),
        owner_created_at=_parse_time(data.get("owner_created_at")),
        owner_contributed_to=data.get("owner_contributed_to"),
    )
