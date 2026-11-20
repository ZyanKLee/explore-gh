"""Finds the stories of a platform, resolves their projects and stores the edition.

The same use case for the daily HN list and the weekly forums list. See docs/community.md.
"""

import logging
from collections.abc import Sequence
from datetime import timedelta

from explore_gh.application.ports import (
    AlreadyPublished,
    Clock,
    CommunityEditionStore,
    ProjectResolver,
    SourceUnavailable,
    StorySource,
)
from explore_gh.domain.community import (
    CommunityCurator,
    CommunityEdition,
    Platform,
    edition_day,
)
from explore_gh.domain.curation import COOLDOWN_DAYS
from explore_gh.domain.withdrawal import Withdrawal

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
        withdrawals: Sequence[Withdrawal] = (),
    ):
        self._platform = platform
        self._stories = story_source
        self._resolver = resolver
        self._editions = edition_store
        self._clock = clock
        self._limit = limit
        self._withdrawals = withdrawals

    def run(self) -> CommunityEdition:
        """The edition of today, or of this week's Monday for a weekly list.

        If there is one already, nothing is fetched. A weekly run that failed on Monday is
        made up for on the following days.
        """
        now = self._clock.now()
        today = edition_day(self._platform, now.date())
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
        edition = CommunityCurator().curate(
            self._platform, today, candidates, past, self._withdrawals
        )
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
