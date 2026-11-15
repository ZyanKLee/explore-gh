"""In-memory fakes of the ports, shared by the use case tests."""

from github_anti_ai.application.ports import AlreadyPublished


class InMemorySnapshotStore:
    def __init__(self, days=None):
        self.days = dict(days or {})

    def append(self, day, snapshots):
        self.days.setdefault(day, []).extend(snapshots)

    def load(self, day):
        """Like the port demands: the latest snapshot of each repo."""
        latest = {snapshot.repo: snapshot for snapshot in self.days.get(day, [])}
        return list(latest.values())

    def prune(self, before):
        self.days = {d: s for d, s in self.days.items() if d >= before}


class InMemoryEditionStore:
    def __init__(self, editions=()):
        self.editions = {e.day: e for e in editions}

    def save(self, edition):
        if edition.day in self.editions:
            raise AlreadyPublished(edition.day)
        self.editions[edition.day] = edition

    def load(self, day):
        return self.editions.get(day)

    def since(self, day):
        return [self.editions[d] for d in sorted(self.editions) if d >= day]


class InMemoryCollectionStatusStore:
    def __init__(self, statuses=()):
        self.statuses = {status.day: status for status in statuses}

    def save(self, status):
        self.statuses[status.day] = status

    def load(self, day):
        return self.statuses.get(day)

    def prune(self, before):
        self.statuses = {d: s for d, s in self.statuses.items() if d >= before}


class InMemoryDailyRecordStore:
    def __init__(self):
        self.by_day = {}

    def save(self, day, records):
        self.by_day[day] = list(records)

    def load(self, day):
        return list(self.by_day.get(day, []))

    def days(self):
        return sorted(self.by_day)


class FakeReviewer:
    """Reviews by a table of repo name to Review. Repos not in the table are fine."""

    def __init__(self, reviews=None, unavailable=False, silent=()):
        from github_anti_ai.domain.review import Review

        self._fine = Review("ok", "Unauffällig.")
        self._reviews = reviews or {}
        self._unavailable = unavailable
        self._silent = set(silent)  # repos the reviewer says nothing about
        self.rounds = []  # the repo names of each call

    def review(self, snapshots):
        from github_anti_ai.application.ports import SourceUnavailable

        self.rounds.append([str(s.repo) for s in snapshots])
        if self._unavailable:
            raise SourceUnavailable("copilot: nicht erreichbar")
        return {
            s.repo: self._reviews.get(str(s.repo), self._fine)
            for s in snapshots
            if str(s.repo) not in self._silent
        }

    @property
    def asked(self):
        return [repo for round_ in self.rounds for repo in round_]
