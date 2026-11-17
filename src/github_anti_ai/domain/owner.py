"""History of the owner: an account that has been around and works on other projects.

Campaigns of lures use accounts made for the purpose, a few weeks old and without any
work elsewhere. Followers do not count: not every developer gathers people around them.
See docs/bewertung.md, "Vorgeschichte des Besitzers".
"""

from github_anti_ai.domain.model import Signal, Snapshot

DAYS_PER_MONTH, DAYS_PER_YEAR = 30, 365
OWNER_AGE_POINTS_PER_MONTH, OWNER_AGE_MAX_POINTS = 0.25, 10.0
OWNER_CONTRIBUTION_POINTS, OWNER_CONTRIBUTION_MAX_POINTS = 1.0, 5.0


class OwnerHistory:
    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        found = [self._age(snapshot), self._contributions(snapshot)]
        return tuple(signal for signal in found if signal)

    def _age(self, snapshot: Snapshot) -> Signal | None:
        if snapshot.owner_created_at is None:
            return None
        days = (snapshot.taken_at - snapshot.owner_created_at).days
        months, years = days // DAYS_PER_MONTH, days // DAYS_PER_YEAR
        if months < 1:
            return None
        if years >= 1:
            age = f"{years} Jahr" if years == 1 else f"{years} Jahren"
        else:
            age = f"{months} Monat" if months == 1 else f"{months} Monaten"
        points = min(months * OWNER_AGE_POINTS_PER_MONTH, OWNER_AGE_MAX_POINTS)
        return Signal("owner_age", points, f"Besitzerkonto besteht seit {age}")

    def _contributions(self, snapshot: Snapshot) -> Signal | None:
        projects = snapshot.owner_contributed_to
        if not projects:
            return None
        points = min(projects * OWNER_CONTRIBUTION_POINTS, OWNER_CONTRIBUTION_MAX_POINTS)
        noun = "Projekt" if projects == 1 else "Projekten"
        return Signal(
            "owner_contributions", points, f"Besitzer wirkt an {projects} anderen {noun} mit"
        )
