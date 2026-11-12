"""Signs of real work and real interest, and the cross-check against bought stars."""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import number

TEAM_MIN_AUTHORS, TEAM_POINTS = 2, 5.0
LARGE_TEAM_MIN_AUTHORS, LARGE_TEAM_POINTS = 5, 8.0
CONTINUITY_MIN_WEEKS, CONTINUITY_POINTS = 4, 5.0
LONG_CONTINUITY_MIN_WEEKS, LONG_CONTINUITY_POINTS = 8, 10.0
COMMIT_LIST_LIMIT = 100  # the collection knows at most this many commits
ENGAGEMENT_MIN_ISSUE_AUTHORS, ENGAGEMENT_POINTS = 3, 5.0
NEW_PROJECT_MAX_AGE_DAYS, NEW_PROJECT_POINTS = 30, 3.0
STARS_PER_ECHO, NO_ECHO_PENALTY = 100, 40.0
FORK_FARM_MIN_SHARE, FORK_FARM_PENALTY = 0.6, 40.0


class SubstanceCheck:
    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        found = [
            self._team(snapshot),
            self._continuity(snapshot),
            self._engagement(snapshot),
            self._new_project(snapshot),
            self._no_echo(snapshot),
            self._fork_farm(snapshot),
        ]
        return tuple(signal for signal in found if signal)

    def _team(self, snapshot: Snapshot) -> Signal | None:
        authors = snapshot.active_authors
        if authors < TEAM_MIN_AUTHORS:
            return None
        points = LARGE_TEAM_POINTS if authors >= LARGE_TEAM_MIN_AUTHORS else TEAM_POINTS
        return Signal("team", points, f"{authors} aktive Autoren in 90 Tagen")

    def _continuity(self, snapshot: Snapshot) -> Signal | None:
        if len(snapshot.recent_commits) >= COMMIT_LIST_LIMIT:
            return None  # the list is cut off and may cover just a few days
        weeks = len(
            {c.committed_at.isocalendar()[:2] for c in snapshot.recent_commits if not c.is_bot}
        )
        if weeks < CONTINUITY_MIN_WEEKS:
            return None
        points = (
            LONG_CONTINUITY_POINTS if weeks >= LONG_CONTINUITY_MIN_WEEKS else CONTINUITY_POINTS
        )
        return Signal("continuity", points, f"Commits in {weeks} verschiedenen Wochen")

    def _engagement(self, snapshot: Snapshot) -> Signal | None:
        people = snapshot.recent_issue_authors
        if people < ENGAGEMENT_MIN_ISSUE_AUTHORS:
            return None
        return Signal("engagement", ENGAGEMENT_POINTS, f"Issues von {people} verschiedenen Personen")

    def _new_project(self, snapshot: Snapshot) -> Signal | None:
        age = (snapshot.taken_at - snapshot.created_at).days
        if age > NEW_PROJECT_MAX_AGE_DAYS:
            return None
        return Signal("new_project", NEW_PROJECT_POINTS, f"Neues Projekt, {age} Tage alt")

    def _no_echo(self, snapshot: Snapshot) -> Signal | None:
        echo = snapshot.forks + snapshot.recent_issue_authors + snapshot.pull_requests
        if echo * STARS_PER_ECHO >= snapshot.stars:
            return None
        return Signal(
            "no_echo",
            -NO_ECHO_PENALTY,
            f"{number(snapshot.stars)} Sterne, aber kaum Echo: {snapshot.forks} Forks, "
            f"{snapshot.recent_issue_authors} Issue-Autoren, {snapshot.pull_requests} Pull Requests",
        )

    def _fork_farm(self, snapshot: Snapshot) -> Signal | None:
        if snapshot.stars == 0 or snapshot.forks < FORK_FARM_MIN_SHARE * snapshot.stars:
            return None
        return Signal(
            "fork_farm",
            -FORK_FARM_PENALTY,
            f"Auffällig viele Forks: {number(snapshot.forks)} bei {number(snapshot.stars)} Sternen",
        )
