"""Resolve Lobsters story links to public repositories using the shared forge checks."""

import httpx

from github_anti_ai.adapters.hn_projects import HnProjectResolver
from github_anti_ai.domain.lobsters import LobstersProjectCandidate, LobstersStory


class LobstersProjectResolver:
    def __init__(
        self,
        client: httpx.Client,
        *,
        github_client: httpx.Client | None = None,
        resolve_host=None,
    ):
        self._resolver = HnProjectResolver(
            client,
            github_client=github_client,
            resolve_host=resolve_host,
        )

    def resolve(self, story: LobstersStory) -> LobstersProjectCandidate | None:
        project = self._resolver.resolve(story)
        if project is None:
            return None
        return LobstersProjectCandidate(
            story=story,
            repository_url=project.repository_url,
            project_url=project.project_url,
            description=project.description,
            language=project.language,
            license_id=project.license_id,
            is_fork=project.is_fork,
            is_archived=project.is_archived,
            has_code=project.has_code,
        )