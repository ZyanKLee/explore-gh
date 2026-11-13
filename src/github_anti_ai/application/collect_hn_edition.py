"""Collect, filter and persist the daily Hacker News project list."""

import logging
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from github_anti_ai.application.ports import AlreadyPublished, Clock, SourceUnavailable
from github_anti_ai.domain.hn import HnEdition, HnEditionCurator, HnProjectCandidate, HnStory

log = logging.getLogger(__name__)


class HnStorySource(Protocol):
    def discover(self, today: date, limit: int | None = None) -> list[HnStory]: ...


class HnProjectResolver(Protocol):
    def resolve(self, story: HnStory) -> HnProjectCandidate | None: ...


class HnEditionStore(Protocol):
    def load(self, day: date) -> HnEdition | None: ...

    def save(self, edition: HnEdition) -> None: ...


class CollectHnEdition:
    def __init__(
        self,
        story_source: HnStorySource,
        project_resolver: HnProjectResolver,
        edition_store: HnEditionStore,
        clock: Clock,
        curator: HnEditionCurator | None = None,
        limit: int | None = None,
    ):
        self._story_source = story_source
        self._project_resolver = project_resolver
        self._edition_store = edition_store
        self._clock = clock
        self._curator = curator or HnEditionCurator()
        self._limit = limit

    def run(self) -> HnEdition:
        today = self._clock.now().date()
        if existing := self._edition_store.load(today):
            log.info("HN-Ausgabe vom %s existiert bereits; Sammlung übersprungen", today)
            return existing
        stories = self._story_source.discover(today, self._limit)
        candidates = []
        for story in stories:
            try:
                candidate = self._project_resolver.resolve(story)
            except SourceUnavailable as error:
                log.warning("HN-Projekt nicht auflösbar (%s): %s", story.url, error)
                continue
            if candidate is not None:
                candidates.append(candidate)

        edition = self._curator.curate(today, candidates)
        try:
            self._edition_store.save(edition)
        except AlreadyPublished:
            if existing := self._edition_store.load(today):
                log.info("HN-Ausgabe vom %s wurde parallel erstellt", today)
                return existing
            raise
        log.info("HN-Ausgabe: %d Storys, %d OSS-Projekte", len(stories), len(edition.projects))
        return edition