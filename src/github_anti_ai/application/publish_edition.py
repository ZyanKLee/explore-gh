from datetime import date, timedelta

from github_anti_ai.application.ports import (
    AlreadyPublished,
    Assessor,
    Clock,
    EditionStore,
    NothingToPublish,
    SnapshotStore,
)
from github_anti_ai.domain.edition import COOLDOWN_DAYS, Edition, EditionCurator


class PublishEdition:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        edition_store: EditionStore,
        assess: Assessor,
        clock: Clock,
        ignore_cooldown: bool = False,
    ):
        self._snapshot_store = snapshot_store
        self._edition_store = edition_store
        self._assess = assess
        self._clock = clock
        self._ignore_cooldown = ignore_cooldown
        self._curator = EditionCurator()

    def run(self, day: date | None = None) -> Edition:
        """Publishes the Edition of the given day, by default of today."""
        today = day or self._clock.now().date()
        if self._edition_store.load(today) is not None:
            raise AlreadyPublished(today)
        snapshots = self._snapshot_store.load(today)
        if not snapshots:
            raise NothingToPublish(today)

        assessments = [self._assess(snapshot) for snapshot in snapshots]
        past_editions = (
            []
            if self._ignore_cooldown
            else self._edition_store.since(today - timedelta(days=COOLDOWN_DAYS))
        )
        edition = self._curator.curate(today, assessments, past_editions)
        self._edition_store.save(edition)
        return edition
