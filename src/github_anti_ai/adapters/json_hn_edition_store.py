"""One immutable JSON file per Hacker News edition."""

import json
from datetime import date, datetime
from pathlib import Path

from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.hn import HnEdition, HnProjectCandidate, HnStory

FORMAT_VERSION = 1


class JsonHnEditionStore:
    def __init__(self, directory: Path):
        self._directory = Path(directory)

    def save(self, edition: HnEdition) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(_to_json(edition), indent=2, ensure_ascii=False) + "\n"
        try:
            with self._path(edition.day).open("x", encoding="utf-8") as file:
                file.write(text)
        except FileExistsError:
            raise AlreadyPublished(edition.day) from None

    def load(self, day: date) -> HnEdition | None:
        path = self._path(day)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format_version") != FORMAT_VERSION:
            raise ValueError(f"{path.name}: unbekannte HN-Ausgabeversion")
        return _from_json(data)

    def since(self, day: date) -> list[HnEdition]:
        if not self._directory.exists():
            return []
        days = []
        for path in self._directory.glob("*.json"):
            try:
                days.append(date.fromisoformat(path.stem))
            except ValueError:
                continue
        return [self.load(item) for item in sorted(days) if item >= day]

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}.json"


def _to_json(edition: HnEdition) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "day": edition.day.isoformat(),
        "projects": [_project_to_json(project) for project in edition.projects],
        "ai_projects": [_project_to_json(project) for project in edition.ai_projects],
    }


def _project_to_json(project: HnProjectCandidate) -> dict:
    """The README is not stored, like in the GitHub editions."""
    return {
        "story": {
            "id": project.story.id,
            "title": project.story.title,
            "url": project.story.url,
            "points": project.story.points,
            "comments": project.story.comments,
            "created_at": project.story.created_at.isoformat(),
        },
        "repository_url": project.repository_url,
        "project_url": project.project_url,
        "description": project.description,
        "language": project.language,
        "license_id": project.license_id,
        "is_fork": project.is_fork,
        "is_archived": project.is_archived,
        "has_code": project.has_code,
        "topics": list(project.topics),
        "linked_directly": project.linked_directly,
        "reasons": list(project.reasons),
    }


def _from_json(data: dict) -> HnEdition:
    return HnEdition(
        day=date.fromisoformat(data["day"]),
        projects=tuple(_project_from_json(project) for project in data["projects"]),
        # Editions from before the AI section (13.11.2026) have neither section nor topics
        ai_projects=tuple(_project_from_json(project) for project in data.get("ai_projects", [])),
    )


def _project_from_json(data: dict) -> HnProjectCandidate:
    story = data["story"]
    return HnProjectCandidate(
        story=HnStory(
            id=story["id"],
            title=story["title"],
            url=story["url"],
            points=story["points"],
            comments=story["comments"],
            created_at=datetime.fromisoformat(story["created_at"]),
        ),
        repository_url=data["repository_url"],
        project_url=data["project_url"],
        description=data["description"],
        language=data["language"],
        license_id=data["license_id"],
        is_fork=data["is_fork"],
        is_archived=data["is_archived"],
        has_code=data["has_code"],
        topics=tuple(data.get("topics", [])),
        # Editions from before "Warum Platz …?" (13.11.2026) have neither
        linked_directly=data.get("linked_directly", False),
        reasons=tuple(data.get("reasons", [])),
    )