"""Editions of a community platform, one immutable JSON file per day (per week for the
forums list, named after its Monday): hn-editions/, lobsters-editions/, forums-editions/

All share the format. HN calls the points of a story "points" and stores no
discussion_url, Lobsters calls them "score". The forums list stores the origin of each
story. See docs/community.md.
"""

from datetime import date, datetime
from pathlib import Path

from github_anti_ai.adapters.files import day_files, read_json, write_new_json
from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.community import (
    HN,
    CommunityEdition,
    CommunityProject,
    Origin,
    Platform,
    Story,
)

FORMAT_VERSION = 1
POINTS_KEYS = {"hn": "points", "lobsters": "score", "forums": "points"}


def directory_name(platform: Platform) -> str:
    return f"{platform.slug}-editions"


class JsonCommunityEditionStore:
    def __init__(self, platform: Platform, data_dir: Path):
        """The editions live in data_dir/<platform>-editions/."""
        self._platform = platform
        self._directory = Path(data_dir) / directory_name(platform)

    def save(self, edition: CommunityEdition) -> None:
        if edition.platform != self._platform:
            raise ValueError(f"Keine {self._platform.name}-Ausgabe")
        if not write_new_json(self._path(edition.day), to_json(edition)):
            raise AlreadyPublished(edition.day)

    def load(self, day: date) -> CommunityEdition | None:
        path = self._path(day)
        return from_json(self._platform, read_json(path)) if path.exists() else None

    def since(self, day: date) -> list[CommunityEdition]:
        return [
            from_json(self._platform, read_json(path))
            for found, path in day_files(self._directory, ".json").items()
            if found >= day
        ]

    def _path(self, day: date) -> Path:
        return self._directory / f"{day.isoformat()}.json"


def to_json(edition: CommunityEdition) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "day": edition.day.isoformat(),
        "projects": [_project_to_json(edition.platform, p) for p in edition.main],
        "ai_projects": [_project_to_json(edition.platform, p) for p in edition.ai],
    }


def _project_to_json(platform: Platform, project: CommunityProject) -> dict:
    """The README is not stored, as in the GitHub editions."""
    story = project.story
    story_json = {"id": story.id, "title": story.title, "url": story.url}
    if platform != HN:  # HN's discussion page follows from the id
        story_json["discussion_url"] = story.discussion_url
    story_json[POINTS_KEYS[platform.slug]] = story.points
    story_json |= {"comments": story.comments, "created_at": story.created_at.isoformat()}
    if story.origin:
        story_json["origin"] = {
            "name": story.origin.name,
            "reference_points": story.origin.reference_points,
            "min_points": story.origin.min_points,
            "points_label": story.origin.points_label,
        }
    stored = {
        "story": story_json,
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
    if project.found_in_post:
        stored["found_in_post"] = True
    return stored


def from_json(platform: Platform, data: dict) -> CommunityEdition:
    """Editions before 2026-11-13 have no AI section, no topics and no reasons."""
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"{platform.name}-Ausgabe vom {data.get('day')}: unbekanntes Format")
    return CommunityEdition(
        platform=platform,
        day=date.fromisoformat(data["day"]),
        main=tuple(_project_from_json(platform, p) for p in data["projects"]),
        ai=tuple(_project_from_json(platform, p) for p in data.get("ai_projects", [])),
    )


def _project_from_json(platform: Platform, data: dict) -> CommunityProject:
    story = data["story"]
    return CommunityProject(
        story=Story(
            id=story["id"],
            title=story["title"],
            url=story["url"],
            discussion_url=story.get("discussion_url") or platform.discussion_url(story["id"]),
            points=story[POINTS_KEYS[platform.slug]],
            comments=story["comments"],
            created_at=datetime.fromisoformat(story["created_at"]),
            origin=Origin(**story["origin"]) if "origin" in story else None,
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
        linked_directly=data.get("linked_directly", False),
        found_in_post=data.get("found_in_post", False),
        reasons=tuple(data.get("reasons", [])),
    )
