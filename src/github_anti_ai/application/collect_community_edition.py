"""Finds the stories of a platform, resolves their projects and stores the edition.

The same use case for HN and Lobsters. See docs/community.md.
"""

import logging
from datetime import timedelta

from github_anti_ai.application.ports import (
    AlreadyPublished,
    Clock,
    CommunityEditionStore,
    ProjectResolver,
    SourceUnavailable,
    StorySource,
)
from github_anti_ai.domain.community import CommunityCurator, CommunityEdition, Platform
from github_anti_ai.domain.curation import COOLDOWN_DAYS

log = logging.getLogger(__name__)


class CollectCommunityEdition:
    def __init__(
        self,
        platform: Platform,
        story_source: StorySource,
        resolver: ProjectResolver,
        edition_store: CommunityEditionStore,
        clock: Clock,
        limit: int | None = None,
    ):
        self._platform = platform
        self._stories = story_source
        self._resolver = resolver
        self._editions = edition_store
        self._clock = clock
        self._limit = limit

    def run(self) -> CommunityEdition:
        """The edition of today. If there is one already, nothing is fetched."""
        now = self._clock.now()
        today = now.date()
        name = self._platform.name
        if existing := self._editions.load(today):
            log.info("%s-Ausgabe vom %s gibt es schon, nichts zu tun", name, today)
            return existing

        stories = self._stories.discover(now, self._limit)
        candidates = []
        for story in stories:
            try:
                project = self._resolver.resolve(story)
            except SourceUnavailable as error:
                log.warning("%s-Story ohne Projekt (%s): %s", name, story.url, error)
                continue
            if project is not None:
                candidates.append(project)

        past = self._editions.since(today - timedelta(days=COOLDOWN_DAYS))
        edition = CommunityCurator().curate(self._platform, today, candidates, past)
        try:
            self._editions.save(edition)
        except AlreadyPublished:
            # another run was faster
            if existing := self._editions.load(today):
                return existing
            raise
        log.info(
            "%s-Ausgabe: %d Storys, %d Projekte, %d AI-Projekte",
            name, len(stories), len(edition.main), len(edition.ai),
        )  # fmt: skip
        return edition
