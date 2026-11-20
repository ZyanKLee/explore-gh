"""In-memory fakes of the ports, shared by the use case tests."""

import dataclasses

from explore_gh.application.ports import AlreadyPublished, SourceUnavailable
from explore_gh.domain.model import Candidate, RepoId, StarHistory
from explore_gh.domain.review import Review


class InMemorySnapshotStore:
    def __init__(self, days=None):
        self.days = {day: list(snapshots) for day, snapshots in (days or {}).items()}

    def append(self, day, snapshots):
        self.days.setdefault(day, []).extend(snapshots)

    def load(self, day):
        latest = {snapshot.repo: snapshot for snapshot in self.days.get(day, [])}
        return list(latest.values())

    def prune(self, before):
        self.days = {day: s for day, s in self.days.items() if day >= before}


class InMemoryStatusStore:
    def __init__(self, statuses=()):
        self.statuses = {status.day: status for status in statuses}

    def save(self, status):
        self.statuses[status.day] = status

    def load(self, day):
        return self.statuses.get(day)

    def prune(self, before):
        self.statuses = {day: s for day, s in self.statuses.items() if day >= before}


class InMemoryEditionStore:
    """Also serves as the store of a community platform."""

    def __init__(self, editions=()):
        self.editions = {edition.day: edition for edition in editions}

    def save(self, edition):
        if edition.day in self.editions:
            raise AlreadyPublished(edition.day)
        self.editions[edition.day] = edition

    def load(self, day):
        return self.editions.get(day)

    def since(self, day):
        return [self.editions[d] for d in sorted(self.editions) if d >= day]


class InMemoryDailyRecordStore:
    def __init__(self):
        self.by_day = {}

    def save(self, day, records):
        self.by_day[day] = list(records)

    def load(self, day):
        return list(self.by_day.get(day, []))

    def days(self):
        return sorted(self.by_day)


class FakeCandidateSource:
    def __init__(self, *repos, name="fake", stars=100, unavailable=False):
        """repos are names, or (name, stars) pairs."""
        self.name = name
        self._candidates = [
            Candidate(RepoId.parse(r), stars)
            if isinstance(r, str)
            else Candidate(RepoId.parse(r[0]), r[1])
            for r in repos
        ]
        self._unavailable = unavailable

    def discover(self, today, limit=None):
        if self._unavailable:
            raise SourceUnavailable("Suche nicht erreichbar")
        return self._candidates[:limit]


class FakeRepoSource:
    """Knows a snapshot for each repo; hands it out as taken now.

    Repos it does not know do not exist. `failing` repos make their whole call fail.
    """

    def __init__(self, *snapshots, failing=()):
        self.known = {snapshot.repo: snapshot for snapshot in snapshots}
        self.failing = {RepoId.parse(name) for name in failing}
        self.calls = []  # (repo names, with_star_history) per call

    def fetch(self, repos, now, with_star_history=True):
        self.calls.append(([str(repo) for repo in repos], with_star_history))
        if self.failing & set(repos):
            raise SourceUnavailable("HTTP 502")
        return [
            dataclasses.replace(
                self.known[repo],
                taken_at=now,
                facts_at=now,
                star_history=self.known[repo].star_history
                if with_star_history
                else StarHistory(()),
            )
            for repo in repos
            if repo in self.known
        ]

    @property
    def fetched(self):
        return [name for names, _ in self.calls for name in names]


class FakeReviewer:
    """Reviews by a table of repo name to category. Repos not in the table are fine."""

    def __init__(self, categories=None, unavailable=False, silent=()):
        self._categories = categories or {}
        self._unavailable = unavailable
        self._silent = set(silent)  # repos the reviewer says nothing about
        self.rounds = []  # the repo names of each call

    def review(self, snapshots):
        self.rounds.append([str(s.repo) for s in snapshots])
        if self._unavailable:
            raise SourceUnavailable("copilot: nicht erreichbar")
        return {
            s.repo: Review(self._categories.get(str(s.repo), "ok"), "Begründung des Modells.")
            for s in snapshots
            if str(s.repo) not in self._silent
        }

    @property
    def asked(self):
        return [repo for round_ in self.rounds for repo in round_]


class FakeStorySource:
    def __init__(self, *stories):
        self.stories = list(stories)
        self.asked = 0

    def discover(self, now, limit=None):
        self.asked += 1
        return self.stories[:limit]


class FakeResolver:
    """Maps a story id to its project. `failing` story ids raise SourceUnavailable."""

    def __init__(self, projects=None, failing=()):
        self._projects = projects or {}
        self._failing = set(failing)

    def resolve(self, story):
        if story.id in self._failing:
            raise SourceUnavailable("HTTP 503")
        return self._projects.get(story.id)
