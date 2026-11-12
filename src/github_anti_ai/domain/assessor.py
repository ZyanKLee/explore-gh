"""Turns a Snapshot into an Assessment. The score is the sum of all signal weights."""

from github_anti_ai.domain.ai_assistance import AiAssistanceDetector
from github_anti_ai.domain.ai_focus import AiFocusClassifier
from github_anti_ai.domain.exclusion import ExclusionPolicy
from github_anti_ai.domain.model import Assessment, Snapshot
from github_anti_ai.domain.momentum import MomentumCalculator
from github_anti_ai.domain.substance import SubstanceCheck


class Assessor:
    def __init__(self):
        self._exclusions = ExclusionPolicy()
        self._ai_focus = AiFocusClassifier()
        self._momentum = MomentumCalculator()
        self._substance = SubstanceCheck()
        self._ai_assistance = AiAssistanceDetector()

    def assess(self, snapshot: Snapshot) -> Assessment:
        """Signals, section and score are always worked out, even for an excluded repo."""
        focus = self._ai_focus.classify(snapshot)
        signals = (
            self._momentum.signal(snapshot),
            *self._substance.signals(snapshot),
            *self._ai_assistance.detect(snapshot),
            *focus.signals,
        )
        return Assessment(
            snapshot=snapshot,
            section=focus.section,
            score=sum(signal.weight for signal in signals),
            signals=signals,
            exclusion=self._exclusions.check(snapshot),
        )
