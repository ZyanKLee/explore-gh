"""Collect, filter and persist the daily Lobsters project list."""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Protocol

from github_anti_ai.application.ports import AlreadyPublished, Clock, SourceUnavailable
from github_anti_ai.domain.edition import COOLDOWN_DAYS
from github_anti_ai.domain.lobsters import (
    LobstersEdition,
    LobstersEditionCurator,
    LobstersProjectCandidate,
    LobstersStory,
)

log = logging.getLogger(__name__)


class LobstersStorySource(Protocol):
    def discover(self, now: datetime, limit: int | None = None) -> list[LobstersStory]: ...


class LobstersProjectResolver(Protocol):
    def resolve(self, story: LobstersStory) -> LobstersProjectCandidate | None: ...


class LobstersEditionStore(Protocol):
    def load(self, day: date) -> LobstersEdition | None: ...

    def save(self, edition: LobstersEdition) -> None: ...

    def since(self, day: date) -> list[LobstersEdition]: ...


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
        now = self._clock.now()
        today = now.date()
        if existing := self._edition_store.load(today):
            log.info("Lobsters-Ausgabe vom %s existiert bereits; Sammlung übersprungen", today)
            return existing
        stories = self._story_source.discover(now, self._limit)
        candidates = []
        for story in stories:
            try:
                candidate = self._project_resolver.resolve(story)
            except SourceUnavailable as error:
                log.warning("Lobsters-Projekt nicht auflösbar (%s): %s", story.url, error)
                continue
            if candidate is not None:
                candidates.append(candidate)

        past_editions = self._edition_store.since(today - timedelta(days=COOLDOWN_DAYS))
        edition = self._curator.curate(today, candidates, past_editions)
        try:
            self._edition_store.save(edition)
        except AlreadyPublished:
            if existing := self._edition_store.load(today):
                log.info("Lobsters-Ausgabe vom %s wurde parallel erstellt", today)
                return existing
            raise
        log.info(
            "Lobsters-Ausgabe: %d Storys, %d OSS-Projekte", len(stories), len(edition.projects)
        )
        return edition