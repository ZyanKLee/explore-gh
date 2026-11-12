import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from github_anti_ai.application.ports import (
    CandidateSource,
    Clock,
    RepoSource,
    SnapshotStore,
    SourceUnavailable,
)
from github_anti_ai.domain.model import RepoId

SNAPSHOT_RETENTION_DAYS = 14
FETCH_CHUNK_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectionReport:
    day: date
    discovered: int
    collected: int  # candidates with a snapshot of the day, including earlier runs
    missing: tuple[RepoId, ...]  # do not exist (any more)
    failed: tuple[RepoId, ...]  # could not be fetched, a rerun tries them again
    source_errors: tuple[str, ...]
    fetch_errors: tuple[str, ...]


class CollectSnapshots:
    def __init__(
        self,
        candidate_sources: Sequence[CandidateSource],
        repo_source: RepoSource,
        snapshot_store: SnapshotStore,
        clock: Clock,
        limit: int | None = None,
    ):
        self._candidate_sources = candidate_sources
        self._repo_source = repo_source
        self._snapshot_store = snapshot_store
        self._clock = clock
        self._limit = limit

    def run(self) -> CollectionReport:
        now = self._clock.now()
        today = now.date()
        candidates, source_errors = self._discover(today)

        done = {snapshot.repo for snapshot in self._snapshot_store.load(today)}
        pending = [repo for repo in candidates if repo not in done]
        log.info("%d Kandidaten, %d davon noch zu holen", len(candidates), len(pending))

        chunks = [pending[i : i + FETCH_CHUNK_SIZE] for i in range(0, len(pending), FETCH_CHUNK_SIZE)]
        missing: list[RepoId] = []
        failed: list[RepoId] = []
        fetch_errors: dict[str, None] = {}
        failures_in_a_row = 0
        for number, chunk in enumerate(chunks, start=1):
            if failures_in_a_row == MAX_CONSECUTIVE_FAILURES:
                failed.extend(chunk)
                continue
            try:
                snapshots = self._repo_source.fetch(chunk, now)
            except SourceUnavailable as error:
                failures_in_a_row += 1
                failed.extend(chunk)
                fetch_errors.setdefault(str(error), None)
                log.warning("Momentaufnahmen %d/%d fehlgeschlagen: %s", number, len(chunks), error)
                if failures_in_a_row == MAX_CONSECUTIVE_FAILURES:
                    log.warning("%d Fehler in Folge, der Lauf hört auf", failures_in_a_row)
                continue
            failures_in_a_row = 0
            self._snapshot_store.append(today, snapshots)
            fetched = {snapshot.repo for snapshot in snapshots}
            done |= fetched
            missing.extend(repo for repo in chunk if repo not in fetched)
            log.info(
                "Momentaufnahmen %d/%d: %d von %d Repos",
                number,
                len(chunks),
                min(number * FETCH_CHUNK_SIZE, len(pending)),
                len(pending),
            )

        self._snapshot_store.prune(before=today - timedelta(days=SNAPSHOT_RETENTION_DAYS))
        return CollectionReport(
            day=today,
            discovered=len(candidates),
            collected=sum(1 for repo in candidates if repo in done),
            missing=tuple(missing),
            failed=tuple(failed),
            source_errors=tuple(source_errors),
            fetch_errors=tuple(fetch_errors),
        )

    def _discover(self, today: date) -> tuple[list[RepoId], list[str]]:
        candidates: dict[RepoId, None] = {}  # keeps the order of discovery
        errors = []
        for source in self._candidate_sources:
            remaining = None if self._limit is None else self._limit - len(candidates)
            if remaining is not None and remaining <= 0:
                break
            try:
                found = source.discover(today, remaining)
            except SourceUnavailable as error:
                errors.append(f"{source.name}: {error}")
                continue
            for repo in found:
                candidates.setdefault(repo, None)
        return list(candidates)[: self._limit], errors
