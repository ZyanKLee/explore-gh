"""Collects the snapshots of a day. See docs/datensammlung.md."""

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from github_anti_ai.application.ports import (
    Assess,
    CandidateSource,
    Clock,
    CollectionStatus,
    CollectionStatusStore,
    RepoSource,
    SnapshotStore,
    SourceUnavailable,
)
from github_anti_ai.domain.copies import CopyCheck
from github_anti_ai.domain.model import Candidate, RepoId, Section, Snapshot

SNAPSHOT_RETENTION_DAYS = 14
FETCH_CHUNK_SIZE = 20  # saved after each chunk: a crash loses at most this many
MAX_CONSECUTIVE_FAILURES = 3
# Facts of this age are fetched again. A repo not seen for longer counts as new.
REFRESH_AFTER_DAYS = 3
# So many of the best repos per section get fresh facts before they are published.
FRESH_LEADERS_PER_SECTION = 60

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectionReport:
    day: date
    discovered: int
    collected: int  # candidates with a snapshot of the day, earlier runs included
    missing: tuple[RepoId, ...]  # do not exist (any more)
    failed: tuple[RepoId, ...]  # could not be fetched, a rerun tries them again
    source_errors: tuple[str, ...]
    fetch_errors: tuple[str, ...]
    fetched: int = 0  # in this run: facts and star history from GitHub
    refreshed: int = 0  # in this run: facts from GitHub, star history continued
    carried_over: int = 0  # in this run: snapshot of an earlier day with today's stars


@dataclass
class _Plan:
    """What to do with each candidate of the day."""

    new: list[RepoId] = field(default_factory=list)  # facts and star history
    stale: list[Candidate] = field(default_factory=list)  # facts only
    reusable: list[Candidate] = field(default_factory=list)  # no request at all
    done: int = 0  # collected by an earlier run of the day


class CollectSnapshots:
    def __init__(
        self,
        candidate_sources: Sequence[CandidateSource],
        repo_source: RepoSource,
        snapshot_store: SnapshotStore,
        status_store: CollectionStatusStore,
        clock: Clock,
        assess: Assess | None = None,
        limit: int | None = None,
    ):
        """Without `assess` the best repos are not refreshed before publishing."""
        self._candidate_sources = candidate_sources
        self._repo_source = repo_source
        self._snapshots = snapshot_store
        self._status = status_store
        self._clock = clock
        self._assess = assess
        self._limit = limit

    def run(self) -> CollectionReport:
        now = self._clock.now()
        today = now.date()
        candidates, source_errors = self._discover(today)
        collected = {snapshot.repo for snapshot in self._snapshots.load(today)}
        previous = self._previous_snapshots(today)
        plan = _plan(candidates, collected, previous, today)
        log.info(
            "%d Kandidaten: %d neu holen, %d auffrischen, %d übernehmen, %d schon da",
            len(candidates), len(plan.new), len(plan.stale), len(plan.reusable), plan.done,
        )  # fmt: skip

        fetcher = _Fetcher(self._repo_source, now)
        carried = self._carry_over(plan.reusable, previous, now)
        collected |= carried

        for chunk, snapshots in fetcher.fetch(plan.new, with_star_history=True, label="Neu holen"):
            if snapshots is None:
                fetcher.failed.extend(chunk)
                continue
            self._snapshots.append(today, snapshots)
            collected |= {snapshot.repo for snapshot in snapshots}
            fetcher.fetched += len(snapshots)

        stars_of = {candidate.repo: candidate for candidate in plan.stale}
        for chunk, snapshots in fetcher.fetch(
            [c.repo for c in plan.stale], with_star_history=False, label="Auffrischen"
        ):
            if snapshots is None:
                # older facts are better than none, if the source told today's stars
                known = [stars_of[repo] for repo in chunk if stars_of[repo].stars is not None]
                carried |= self._carry_over(known, previous, now)
                collected |= carried
                fetcher.failed.extend(repo for repo in chunk if stars_of[repo].stars is None)
                continue
            self._snapshots.append(today, [previous[s.repo].with_facts_of(s) for s in snapshots])
            collected |= {snapshot.repo for snapshot in snapshots}
            fetcher.refreshed += len(snapshots)

        refreshed_leaders = self._refresh_leaders(fetcher, today)

        oldest = today - timedelta(days=SNAPSHOT_RETENTION_DAYS)
        self._snapshots.prune(before=oldest)
        report = CollectionReport(
            day=today,
            discovered=len(candidates),
            collected=sum(1 for candidate in candidates if candidate.repo in collected),
            missing=tuple(fetcher.missing),
            failed=tuple(fetcher.failed),
            source_errors=tuple(source_errors),
            fetch_errors=tuple(fetcher.errors),
            fetched=fetcher.fetched,
            refreshed=fetcher.refreshed,
            carried_over=len(carried - refreshed_leaders),
        )
        self._status.save(
            CollectionStatus(today, report.discovered, report.collected, len(report.failed))
        )
        self._status.prune(before=oldest)
        return report

    def _discover(self, today: date) -> tuple[list[Candidate], list[str]]:
        """Candidates of all sources, each repo once, in the order of discovery."""
        candidates: dict[RepoId, Candidate] = {}
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
            for snapshot in self._snapshots.load(today - timedelta(days=back)):
                latest[snapshot.repo] = snapshot
        return latest

    def _carry_over(
        self, candidates: Sequence[Candidate], previous: dict[RepoId, Snapshot], now: datetime
    ) -> set[RepoId]:
        snapshots = [previous[c.repo].carried_over(now, c.stars) for c in candidates]
        self._snapshots.append(now.date(), snapshots)
        return {snapshot.repo for snapshot in snapshots}

    def _refresh_leaders(self, fetcher: "_Fetcher", today: date) -> set[RepoId]:
        """Fresh facts for the best repos of each section: nothing published is old."""
        if self._assess is None:
            return set()
        current = {snapshot.repo: snapshot for snapshot in self._snapshots.load(today)}
        assessments = CopyCheck().apply([self._assess(s) for s in current.values()])
        leaders: list[RepoId] = []
        for section in Section:
            ranked = sorted(
                (a for a in assessments if a.section is section and a.exclusion is None),
                key=lambda a: a.score,
                reverse=True,
            )
            leaders += [
                a.repo
                for a in ranked[:FRESH_LEADERS_PER_SECTION]
                if a.snapshot.facts_at.date() < today
            ]

        refreshed: set[RepoId] = set()
        for _, snapshots in fetcher.fetch(
            leaders, with_star_history=False, label="Die Besten auffrischen", report_missing=False
        ):
            if snapshots is None:
                continue  # the carried over snapshot stays
            self._snapshots.append(today, [current[s.repo].with_facts_of(s) for s in snapshots])
            refreshed |= {snapshot.repo for snapshot in snapshots}
            fetcher.refreshed += len(snapshots)
        return refreshed


def _plan(
    candidates: Sequence[Candidate],
    collected: set[RepoId],
    previous: dict[RepoId, Snapshot],
    today: date,
) -> _Plan:
    plan = _Plan()
    for candidate in candidates:
        old = previous.get(candidate.repo)
        if candidate.repo in collected:
            plan.done += 1
        elif old is None or not old.star_history.daily:
            plan.new.append(candidate.repo)
        elif candidate.stars is None or (today - old.facts_at.date()).days >= REFRESH_AFTER_DAYS:
            plan.stale.append(candidate)
        else:
            plan.reusable.append(candidate)
    return plan


class _Fetcher:
    """Fetches in chunks, keeps count, and gives up after several failures in a row."""

    def __init__(self, repo_source: RepoSource, now: datetime):
        self._repo_source = repo_source
        self._now = now
        self._failures_in_a_row = 0
        self.missing: list[RepoId] = []
        self.failed: list[RepoId] = []
        self.errors: dict[str, None] = {}  # each message once, in order
        self.fetched = 0
        self.refreshed = 0

    def fetch(
        self,
        repos: Sequence[RepoId],
        *,
        with_star_history: bool,
        label: str,
        report_missing: bool = True,
    ) -> Iterator[tuple[Sequence[RepoId], list[Snapshot] | None]]:
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
                self.missing += [repo for repo in chunk if repo not in found]
            log.info(
                "%s %d/%d: %d von %d Repos",
                label, number, len(chunks), min(number * FETCH_CHUNK_SIZE, len(repos)), len(repos),
            )  # fmt: skip
            yield chunk, snapshots
