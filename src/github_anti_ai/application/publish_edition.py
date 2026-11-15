import logging
from collections.abc import Sequence
from datetime import date, timedelta

from github_anti_ai.application.ports import (
    AlreadyPublished,
    Assessor,
    Clock,
    CollectionStatusStore,
    DailyRecordStore,
    EditionStore,
    IncompleteCollection,
    NothingToPublish,
    Reviewer,
    SnapshotStore,
    SourceUnavailable,
)
from github_anti_ai.domain.copies import CopyCheck
from github_anti_ai.domain.edition import COOLDOWN_DAYS, Edition, EditionCurator
from github_anti_ai.domain.history import DailyRecord
from github_anti_ai.domain.model import Assessment, RepoId, Section
from github_anti_ai.domain.review import reviewed

# Each round reviews what moved up for the repos the round before took out.
MAX_REVIEW_ROUNDS = 5

log = logging.getLogger(__name__)


class PublishEdition:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        edition_store: EditionStore,
        collection_status_store: CollectionStatusStore,
        record_store: DailyRecordStore,
        assess: Assessor,
        clock: Clock,
        ignore_cooldown: bool = False,
        allow_incomplete: bool = False,
        reviewer: Reviewer | None = None,
    ):
        self._snapshot_store = snapshot_store
        self._edition_store = edition_store
        self._assess = assess
        self._clock = clock
        self._collection_status_store = collection_status_store
        self._record_store = record_store
        self._ignore_cooldown = ignore_cooldown
        self._allow_incomplete = allow_incomplete
        self._reviewer = reviewer
        self._curator = EditionCurator()

    def run(self, day: date | None = None) -> Edition:
        """Publishes the Edition of the given day, by default of today."""
        today = day or self._clock.now().date()
        if self._edition_store.load(today) is not None:
            raise AlreadyPublished(today)
        snapshots = self._snapshot_store.load(today)
        if not snapshots:
            raise NothingToPublish(today)
        if not self._allow_incomplete:
            self._refuse_incomplete_collection(today)

        assessments = CopyCheck().apply([self._assess(snapshot) for snapshot in snapshots])
        past_editions = (
            []
            if self._ignore_cooldown
            else self._edition_store.since(today - timedelta(days=COOLDOWN_DAYS))
        )
        if self._reviewer is not None:
            assessments = self._review(today, assessments, past_editions)
        edition = self._curator.curate(today, assessments, past_editions)

        ranks = {
            entry.repo: place
            for section in Section
            for place, entry in enumerate(edition.entries(section), start=1)
        }
        records = [
            DailyRecord.from_assessment(today, assessment, rank=ranks.get(assessment.repo))
            for assessment in assessments
        ]
        # The records first: an Edition can never be replaced. If they fail, the day stays open.
        self._record_store.save(today, records)
        self._edition_store.save(edition)
        return edition

    def _review(
        self, day: date, assessments: list[Assessment], past_editions: Sequence[Edition]
    ) -> list[Assessment]:
        """Lets the reviewer read the repos that would be shown, and only those.

        A repo it takes out makes room for the next one, which is read in the next round.
        Without an answer the Edition appears without review: better than no Edition.
        """
        asked: set[RepoId] = set()
        for _ in range(MAX_REVIEW_ROUNDS):
            edition = self._curator.curate(day, assessments, past_editions)
            shown = {entry.repo for section in Section for entry in edition.entries(section)}
            pending = [a.snapshot for a in assessments if a.repo in shown - asked]
            if not pending:
                break
            asked.update(snapshot.repo for snapshot in pending)
            try:
                reviews = self._reviewer.review(pending)
            except SourceUnavailable as error:
                log.warning("Gegenlesen ausgefallen, die Ausgabe erscheint ohne: %s", error)
                break
            assessments = [
                reviewed(a, reviews[a.repo]) if a.repo in reviews else a for a in assessments
            ]
        return assessments

    def _refuse_incomplete_collection(self, day: date) -> None:
        status = self._collection_status_store.load(day)
        if status is None:
            raise IncompleteCollection(f"Die Sammlung vom {day} ist nicht abgeschlossen.")
        if not status.is_complete:
            raise IncompleteCollection(
                f"Die Sammlung vom {day} ist unvollständig: "
                f"{status.failed} von {status.discovered} Repos konnten nicht geholt werden."
            )
