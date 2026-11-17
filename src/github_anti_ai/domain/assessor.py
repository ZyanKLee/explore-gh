"""Turns a Snapshot into an Assessment. See docs/bewertung.md, "Ablauf"."""

from github_anti_ai.domain.ai_assistance import AiAssistanceDetector
from github_anti_ai.domain.ai_focus import AiFocusClassifier
from github_anti_ai.domain.exclusion import ExclusionPolicy
from github_anti_ai.domain.model import Assessment, Snapshot
from github_anti_ai.domain.momentum import MomentumCalculator
from github_anti_ai.domain.owner import OwnerHistory
from github_anti_ai.domain.preferences import (
    ConsoleEmulatorCheck,
    DislikedTopics,
    PlatformPreference,
)
from github_anti_ai.domain.substance import SubstanceCheck


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
