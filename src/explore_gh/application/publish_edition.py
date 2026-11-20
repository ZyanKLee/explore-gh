"""Builds and stores the Edition of a day. See docs/ausgabe.md."""

import logging
from collections.abc import Sequence
from datetime import date, timedelta

from explore_gh.application.ports import (
    AlreadyPublished,
    Assess,
    CollectionStatusStore,
    DailyRecordStore,
    EditionStore,
    IncompleteCollection,
    NothingToPublish,
    Reviewer,
    SnapshotStore,
    SourceUnavailable,
)
from explore_gh.domain.copies import CopyCheck
from explore_gh.domain.curation import COOLDOWN_DAYS
from explore_gh.domain.edition import Edition, EditionCurator
from explore_gh.domain.history import DailyRecord
from explore_gh.domain.model import Assessment, RepoId, Section
from explore_gh.domain.review import REVIEWER_NAME, Review, reviewed
from explore_gh.domain.withdrawal import Withdrawal, withdrawn

# Each round reads what moved up for the repos the round before took out.
MAX_REVIEW_ROUNDS = 5

log = logging.getLogger(__name__)


class PublishEdition:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        status_store: CollectionStatusStore,
        edition_store: EditionStore,
        record_store: DailyRecordStore,
        assess: Assess,
        reviewer: Reviewer | None = None,
        ignore_cooldown: bool = False,
        allow_incomplete: bool = False,
        withdrawals: Sequence[Withdrawal] = (),
    ):
        self._snapshots = snapshot_store
        self._status = status_store
        self._editions = edition_store
        self._records = record_store
        self._assess = assess
        self._reviewer = reviewer
        self._ignore_cooldown = ignore_cooldown
        self._allow_incomplete = allow_incomplete
        self._withdrawals = withdrawals
        self._curator = EditionCurator()

    def run(self, day: date) -> Edition:
        """`day` is the day the collection began, even if it ran past midnight."""
        if self._editions.load(day) is not None:
            raise AlreadyPublished(day)
        snapshots = self._snapshots.load(day)
        if not snapshots:
            raise NothingToPublish(day)
        if not self._allow_incomplete:
            self._refuse_incomplete_collection(day)

        assessments = [
            withdrawn(assessment, self._withdrawals)
            for assessment in CopyCheck().apply([self._assess(s) for s in snapshots])
        ]
        past = (
            []
            if self._ignore_cooldown
            else self._editions.since(day - timedelta(days=COOLDOWN_DAYS))
        )
        reviews: dict[RepoId, Review] = {}
        if self._reviewer is not None:
            assessments, reviews = self._review(day, assessments, past)
        edition = self._curator.curate(day, assessments, past)

        ranks = edition.ranks()
        records = [
            DailyRecord.from_assessment(
                day,
                assessment,
                rank=ranks.get(assessment.repo),
                review=reviews[assessment.repo].category if assessment.repo in reviews else None,
            )
            for assessment in assessments
        ]
        # The records first: an Edition is never replaced. If they fail, the day stays open.
        self._records.save(day, records)
        self._editions.save(edition)
        return edition

    def _review(
        self, day: date, assessments: list[Assessment], past: Sequence[Edition]
    ) -> tuple[list[Assessment], dict[RepoId, Review]]:
        """Lets the reviewer read the repos that would be shown, and only those.

        A repo it takes out makes room for the next one, which is read in the next round.
        Without an answer the Edition appears without review: better than no Edition.
        """
        asked: set[RepoId] = set()
        found: dict[RepoId, Review] = {}
        moved = removed = 0
        for _ in range(MAX_REVIEW_ROUNDS):
            shown = set(self._curator.curate(day, assessments, past).ranks())
            pending = [a.snapshot for a in assessments if a.repo in shown - asked]
            if not pending:
                break
            asked |= {snapshot.repo for snapshot in pending}
            try:
                reviews = self._reviewer.review(pending)
            except SourceUnavailable as error:
                log.warning("Gegenlesen ausgefallen, die Ausgabe erscheint ohne: %s", error)
                break
            found |= reviews
            after = [reviewed(a, reviews[a.repo]) if a.repo in reviews else a for a in assessments]
            # the model's reasons stay in the log of the run, never in the data
            for before, now in zip(assessments, after, strict=True):
                if now.exclusion is not None and before.exclusion is None:
                    removed += 1
                    review = reviews[now.repo]
                    log.info(
                        "%s: %s herausgenommen (%s): %s",
                        REVIEWER_NAME, now.repo, review.category, review.reason,
                    )  # fmt: skip
                elif now.section is not before.section:
                    moved += 1
                    log.info(
                        "%s: %s in die AI-Sektion verschoben: %s",
                        REVIEWER_NAME, now.repo, reviews[now.repo].reason,
                    )  # fmt: skip
            assessments = after
        if found:
            log.info(
                "Gegenlesen: %d gelesen, %d in die AI-Sektion verschoben, %d herausgenommen",
                len(found), moved, removed,
            )  # fmt: skip
        return assessments, found

    def _refuse_incomplete_collection(self, day: date) -> None:
        status = self._status.load(day)
        if status is None:
            raise IncompleteCollection(f"Die Sammlung vom {day} ist nicht abgeschlossen.")
        if not status.is_complete:
            raise IncompleteCollection(
                f"Die Sammlung vom {day} ist unvollständig: "
                f"{status.failed} von {status.discovered} Repos konnten nicht geholt werden."
            )


def reviewed_entries(edition: Edition) -> tuple[int, int]:
    """How many entries the reviewer read, of how many."""
    entries = [entry for section in Section for entry in edition.entries(section)]
    read = sum(1 for entry in entries if any(s.kind == "review" for s in entry.signals))
    return read, len(entries)
