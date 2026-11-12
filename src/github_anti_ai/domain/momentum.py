"""Momentum: how much attention a repo is gaining right now."""

from math import log10, sqrt

from github_anti_ai.domain.model import GROWTH_WINDOW_DAYS, Signal, Snapshot
from github_anti_ai.domain.text import number

POINTS_PER_POWER_OF_TEN = 20
MIN_RELATIVE_FACTOR = 0.5


class MomentumCalculator:
    def signal(self, snapshot: Snapshot) -> Signal:
        gained = snapshot.star_history.gained()
        stars = max(snapshot.stars, gained)  # people can remove their star again
        points = 0.0
        if gained > 0:
            relative = MIN_RELATIVE_FACTOR + (1 - MIN_RELATIVE_FACTOR) * sqrt(gained / stars)
            points = POINTS_PER_POWER_OF_TEN * log10(gained) * relative
        return Signal(
            kind="momentum",
            weight=points,
            reason=(
                f"+{number(gained)} Sterne in {GROWTH_WINDOW_DAYS} Tagen "
                f"bei {number(snapshot.stars)} insgesamt"
            ),
        )
