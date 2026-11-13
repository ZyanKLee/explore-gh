"""Collects the snapshots of a day. See docs/datensammlung.md."""

import dataclasses
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from github_anti_ai.application.ports import (
    Assessor,
    CandidateSource,
    Clock,
    CollectionStatus,
    CollectionStatusStore,
    RepoSource,
    SnapshotStore,
    SourceUnavailable,
)
from github_anti_ai.domain.model import Candidate, RepoId, Section, Snapshot

SNAPSHOT_RETENTION_DAYS = 14
FETCH_CHUNK_SIZE = 20
MAX_CONSECUTIVE_FAILURES = 3
# Facts of this age are fetched again. A repo not seen for longer counts as new.
REFRESH_AFTER_DAYS = 3
# So many of the best repos per section always get fresh facts before publishing.
FRESH_LEADERS_PER_SECTION = 60

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
    fetched: int = 0  # in this run: facts and star history from GitHub
    refreshed: int = 0  # in this run: facts from GitHub, star history continued
    carried_over: int = 0  # in this run: snapshot of an earlier day with today's stars


class CollectSnapshots:
    def __init__(
        self,
        candidate_sources: Sequence[CandidateSource],
        repo_source: RepoSource,
        snapshot_store: SnapshotStore,
        clock: Clock,
        assess: Assessor | None = None,
        limit: int | None = None,
        status_store: CollectionStatusStore | None = None,
    ):
        self._candidate_sources = candidate_sources
        self._repo_source = repo_source
        self._snapshot_store = snapshot_store
        self._clock = clock
        self._assess = assess
        self._limit = limit
        self._status_store = status_store

    def run(self) -> CollectionReport:
        now = self._clock.now()
        today = now.date()
        candidates, source_errors = self._discover(today)

        done = {snapshot.repo for snapshot in self._snapshot_store.load(today)}
        previous = self._previous_snapshots(today)
        new: list[RepoId] = []
        stale: list[Candidate] = []
        reusable: list[Candidate] = []
        for candidate in candidates:
            old = previous.get(candidate.repo)
            if candidate.repo in done:
                continue
            if old is None or not old.star_history.daily:
                new.append(candidate.repo)
            elif candidate.stars is None or _facts_age(old, today) >= REFRESH_AFTER_DAYS:
                stale.append(candidate)
            else:
                reusable.append(candidate)
        log.info(
            "%d Kandidaten: %d neu holen, %d auffrischen, %d übernehmen, %d schon da",
            len(candidates),
            len(new),
            len(stale),
            len(reusable),
            len(candidates) - len(new) - len(stale) - len(reusable),
        )

        run = _Run(self._repo_source, now)
        carried = self._carry_over(reusable, previous, now)
        done |= carried

        for chunk, snapshots in run.fetch(new, with_star_history=True, label="Neu holen"):
            if snapshots is None:
                run.failed.extend(chunk)
                continue
            self._snapshot_store.append(today, snapshots)
            done |= {snapshot.repo for snapshot in snapshots}
            run.fetched += len(snapshots)

        stars_of = {candidate.repo: candidate for candidate in stale}
        for chunk, snapshots in run.fetch(
            [c.repo for c in stale], with_star_history=False, label="Auffrischen"
        ):
            if snapshots is None:
                # older facts are better than none
                fallback = [stars_of[repo] for repo in chunk if stars_of[repo].stars is not None]
                carried |= self._carry_over(fallback, previous, now)
                done |= carried
                run.failed.extend(repo for repo in chunk if stars_of[repo].stars is None)
                continue
            continued = [_continue_history(previous[s.repo], s) for s in snapshots]
            self._snapshot_store.append(today, continued)
            done |= {snapshot.repo for snapshot in snapshots}
            run.refreshed += len(snapshots)

        refreshed_leaders = self._refresh_leaders(run, today)

        collected = sum(1 for candidate in candidates if candidate.repo in done)
        oldest = today - timedelta(days=SNAPSHOT_RETENTION_DAYS)
        self._snapshot_store.prune(before=oldest)
        if self._status_store is not None:
            self._status_store.save(
                CollectionStatus(
                    day=today,
                    discovered=len(candidates),
                    collected=collected,
                    failed=len(run.failed),
                )
            )
            self._status_store.prune(before=oldest)
        return CollectionReport(
            day=today,
            discovered=len(candidates),
            collected=collected,
            missing=tuple(run.missing),
            failed=tuple(run.failed),
            source_errors=tuple(source_errors),
            fetch_errors=tuple(run.errors),
            fetched=run.fetched,
            refreshed=run.refreshed,
            carried_over=len(carried - refreshed_leaders),
        )

    def _discover(self, today: date) -> tuple[list[Candidate], list[str]]:
        candidates: dict[RepoId, Candidate] = {}  # keeps the order of discovery
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
            for candidate in found:
                known = candidates.get(candidate.repo)
                if known is None or (known.stars is None and candidate.stars is not None):
                    candidates[candidate.repo] = candidate
        return list(candidates.values())[: self._limit], errors

    def _previous_snapshots(self, today: date) -> dict[RepoId, Snapshot]:
        """The latest snapshot of each repo from the days before today."""
        latest: dict[RepoId, Snapshot] = {}
        for back in range(REFRESH_AFTER_DAYS, 0, -1):  # oldest first, later days win
            for snapshot in self._snapshot_store.load(today - timedelta(days=back)):
                latest[snapshot.repo] = snapshot
        return latest

    def _carry_over(
        self, candidates: Sequence[Candidate], previous: dict[RepoId, Snapshot], now: datetime
    ) -> set[RepoId]:
        snapshots = [previous[c.repo].carried_over(now, c.stars) for c in candidates]
        if snapshots:
            self._snapshot_store.append(now.date(), snapshots)
        return {snapshot.repo for snapshot in snapshots}

    def _refresh_leaders(self, run: "_Run", today: date) -> set[RepoId]:
        """Fresh facts for the best repos of each section, so that nothing published is old."""
        if self._assess is None:
            return set()
        current = {snapshot.repo: snapshot for snapshot in self._snapshot_store.load(today)}
        assessments = [self._assess(snapshot) for snapshot in current.values()]
        leaders: list[RepoId] = []
        for section in Section:
            ranked = sorted(
                (a for a in assessments if a.section is section and a.exclusion is None),
                key=lambda a: a.score,
                reverse=True,
            )
            leaders.extend(
                a.repo
                for a in ranked[:FRESH_LEADERS_PER_SECTION]
                if a.snapshot.facts_at.date() < today
            )

        refreshed: set[RepoId] = set()
        for _, snapshots in run.fetch(
            leaders, with_star_history=False, label="Die Besten auffrischen", report_missing=False
        ):
            if snapshots is None:
                continue  # the carried over snapshot stays
            continued = [_continue_history(current[s.repo], s) for s in snapshots]
            self._snapshot_store.append(today, continued)
            refreshed |= {snapshot.repo for snapshot in snapshots}
            run.refreshed += len(snapshots)
        return refreshed


class _Run:
    """Fetches in chunks and keeps count of what happened."""

    def __init__(self, repo_source: RepoSource, now: datetime):
        self._repo_source = repo_source
        self._now = now
        self._failures_in_a_row = 0
        self.missing: list[RepoId] = []
        self.failed: list[RepoId] = []
        self.errors: dict[str, None] = {}
        self.fetched = 0
        self.refreshed = 0

    def fetch(
        self, repos: Sequence[RepoId], *, with_star_history: bool, label: str, report_missing=True
    ):
        """Yields each chunk with its snapshots, or with None if it could not be fetched."""
        chunks = [repos[i : i + FETCH_CHUNK_SIZE] for i in range(0, len(repos), FETCH_CHUNK_SIZE)]
        for number, chunk in enumerate(chunks, start=1):
            if self._failures_in_a_row >= MAX_CONSECUTIVE_FAILURES:
                yield chunk, None
                continue
            try:
                snapshots = self._repo_source.fetch(chunk, self._now, with_star_history)
            except SourceUnavailable as error:
                self._failures_in_a_row += 1
                self.errors.setdefault(str(error), None)
                log.warning("%s %d/%d fehlgeschlagen: %s", label, number, len(chunks), error)
                if self._failures_in_a_row == MAX_CONSECUTIVE_FAILURES:
                    log.warning("%d Fehler in Folge, der Lauf hört auf", self._failures_in_a_row)
                yield chunk, None
                continue
            self._failures_in_a_row = 0
            if report_missing:
                found = {snapshot.repo for snapshot in snapshots}
                self.missing.extend(repo for repo in chunk if repo not in found)
            log.info(
                "%s %d/%d: %d von %d Repos",
                label,
                number,
                len(chunks),
                min(number * FETCH_CHUNK_SIZE, len(repos)),
                len(repos),
            )
            yield chunk, snapshots


def _facts_age(snapshot: Snapshot, today: date) -> int:
    return (today - snapshot.facts_at.date()).days


def _continue_history(old: Snapshot, fresh: Snapshot) -> Snapshot:
    """Fresh facts with our own star history: the old one plus the stars gained since."""
    days_passed = (fresh.taken_at.date() - old.taken_at.date()).days
    gained = max(0, fresh.stars - old.stars)
    return dataclasses.replace(
        fresh, star_history=old.star_history.continued(days_passed, gained)
    )
