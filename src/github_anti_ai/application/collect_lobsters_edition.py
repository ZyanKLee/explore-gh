"""Collect, filter and persist the daily Lobsters project list."""

import logging
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from github_anti_ai.application.ports import Clock, SourceUnavailable
from github_anti_ai.domain.lobsters import (
    LobstersEdition,
    LobstersEditionCurator,
    LobstersProjectCandidate,
    LobstersStory,
)

log = logging.getLogger(__name__)


class LobstersStorySource(Protocol):
    def discover(self, today: date, limit: int | None = None) -> list[LobstersStory]: ...


class LobstersProjectResolver(Protocol):
    def resolve(self, story: LobstersStory) -> LobstersProjectCandidate | None: ...


class LobstersEditionStore(Protocol):
    def save(self, edition: LobstersEdition) -> None: ...


class CollectLobstersEdition:
    def __init__(
        self,
        story_source: LobstersStorySource,
        project_resolver: LobstersProjectResolver,
        edition_store: LobstersEditionStore,
        clock: Clock,
        curator: LobstersEditionCurator | None = None,
        limit: int | None = None,
    ):
        self._story_source = story_source
        self._project_resolver = project_resolver
        self._edition_store = edition_store
        self._clock = clock
        self._curator = curator or LobstersEditionCurator()
        self._limit = limit

    def run(self) -> LobstersEdition:
        today = self._clock.now().date()
        stories = self._story_source.discover(today, self._limit)
        candidates = []
        for story in stories:
            try:
                candidate = self._project_resolver.resolve(story)
            except SourceUnavailable as error:
                log.warning("Lobsters-Projekt nicht auflösbar (%s): %s", story.url, error)
                continue
            if candidate is not None:
                candidates.append(candidate)

        edition = self._curator.curate(today, candidates)
        self._edition_store.save(edition)
        log.info(
            "Lobsters-Ausgabe: %d Storys, %d OSS-Projekte", len(stories), len(edition.projects)
        )
        return edition