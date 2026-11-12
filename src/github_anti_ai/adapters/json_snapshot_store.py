"""Snapshots as gzipped JSON lines, one file per day: YYYY-MM-DD.jsonl.gz"""

import gzip
import json
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from github_anti_ai.domain.model import Commit, RepoId, Snapshot, StarHistory

SUFFIX = ".jsonl.gz"


class JsonSnapshotStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def append(self, day: date, snapshots: Sequence[Snapshot]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        lines = "".join(json.dumps(_to_json(s), ensure_ascii=False) + "\n" for s in snapshots)
        with self._path(day).open("ab") as file:  # gzip files may be concatenated
            file.write(gzip.compress(lines.encode()))

    def load(self, day: date) -> list[Snapshot]:
        path = self._path(day)
        if not path.exists():
            return []
        lines = gzip.decompress(path.read_bytes()).decode().splitlines()
        latest: dict[RepoId, Snapshot] = {}
        for line in lines:
            snapshot = _from_json(json.loads(line))
            latest[snapshot.repo] = snapshot
        return list(latest.values())

    def prune(self, before: date) -> None:
        if not self._directory.exists():
            return
        for path in self._directory.glob(f"*{SUFFIX}"):
            try:
                day = date.fromisoformat(path.name.removesuffix(SUFFIX))
            except ValueError:
                continue
            if day < before:
                path.unlink()

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}{SUFFIX}"


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_time(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def _to_json(snapshot: Snapshot) -> dict:
    return {
        "repo": str(snapshot.repo),
        "taken_at": _time(snapshot.taken_at),
        "description": snapshot.description,
        "homepage": snapshot.homepage,
        "topics": list(snapshot.topics),
        "primary_language": snapshot.primary_language,
        "created_at": _time(snapshot.created_at),
        "pushed_at": _time(snapshot.pushed_at),
        "stars": snapshot.stars,
        "forks": snapshot.forks,
        "open_issues": snapshot.open_issues,
        "watchers": snapshot.watchers,
        "pull_requests": snapshot.pull_requests,
        "recent_issue_authors": snapshot.recent_issue_authors,
        "is_fork": snapshot.is_fork,
        "is_archived": snapshot.is_archived,
        "is_mirror": snapshot.is_mirror,
        "is_template": snapshot.is_template,
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
    }


def _from_json(data: dict) -> Snapshot:
    return Snapshot(
        repo=RepoId.parse(data["repo"]),
        taken_at=_parse_time(data["taken_at"]),
        description=data["description"],
        homepage=data["homepage"],
        topics=tuple(data["topics"]),
        primary_language=data["primary_language"],
        created_at=_parse_time(data["created_at"]),
        pushed_at=_parse_time(data["pushed_at"]),
        stars=data["stars"],
        forks=data["forks"],
        open_issues=data["open_issues"],
        watchers=data["watchers"],
        pull_requests=data["pull_requests"],
        recent_issue_authors=data["recent_issue_authors"],
        is_fork=data["is_fork"],
        is_archived=data["is_archived"],
        is_mirror=data["is_mirror"],
        is_template=data["is_template"],
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
        star_history=StarHistory(daily=tuple(data["star_history"])),
    )
