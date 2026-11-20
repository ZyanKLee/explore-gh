"""Turns a Snapshot into an Assessment. See docs/bewertung.md, "Ablauf"."""

from explore_gh.domain.ai_assistance import AiAssistanceDetector
from explore_gh.domain.ai_focus import AiFocusClassifier
from explore_gh.domain.exclusion import ExclusionPolicy
from explore_gh.domain.model import Assessment, Snapshot
from explore_gh.domain.momentum import MomentumCalculator
from explore_gh.domain.owner import OwnerHistory
from explore_gh.domain.preferences import (
    ConsoleEmulatorCheck,
    DislikedTopics,
    PlatformPreference,
)
from explore_gh.domain.substance import SubstanceCheck


class Assessor:
    def __init__(self):
        self._exclusions = ExclusionPolicy()
        self._ai_focus = AiFocusClassifier()
        self._momentum = MomentumCalculator()
        self._signal_rules = [
            SubstanceCheck(),
            OwnerHistory(),
            AiAssistanceDetector(),
            PlatformPreference(),
            ConsoleEmulatorCheck(),
            DislikedTopics(),
        ]

    def assess(self, snapshot: Snapshot) -> Assessment:
        """Signals and section are always worked out, even for an excluded repo.

        So `explain` shows the whole picture.
        """
        focus = self._ai_focus.classify(snapshot)
        signals = (
            self._momentum.signal(snapshot),
            *(signal for rule in self._signal_rules for signal in rule.signals(snapshot)),
            *focus.signals,
        )
        return Assessment(
            snapshot=snapshot,
            section=focus.section,
            signals=signals,
            exclusion=self._exclusions.check(snapshot),
        )
