"""Explains the assessment of one repo on one day, also of one that was not shown."""

from datetime import date

from explore_gh.application.ports import Assess, SnapshotStore
from explore_gh.domain.copies import CopyCheck
from explore_gh.domain.model import RepoId, Section

SECTION_NAMES = {Section.MAIN: "Hauptliste", Section.AI: "AI-Sektion"}


class UnknownRepo(Exception):
    def __init__(self, day: date, repo: RepoId):
        super().__init__(f"Keine Momentaufnahme von {repo} am {day}")


class ExplainAssessment:
    def __init__(self, snapshot_store: SnapshotStore, assess: Assess):
        self._snapshots = snapshot_store
        self._assess = assess

    def run(self, day: date, repo: RepoId) -> str:
        """Section, score, exclusion and every signal as plain text."""
        snapshots = self._snapshots.load(day)
        snapshot = next((s for s in snapshots if s.repo == repo), None)
        if snapshot is None:
            raise UnknownRepo(day, repo)

        assessment = self._assess(snapshot)
        # a copy only shows among the other repos of the day
        exclusion = assessment.exclusion or CopyCheck().find(snapshots).get(snapshot.repo)
        lines = [
            str(snapshot.repo),
            f"Sektion: {SECTION_NAMES[assessment.section]}",
            f"Punktzahl: {assessment.score:.1f}",
            f"Ausschluss: {exclusion.reason if exclusion else 'keiner'}",
            "Signale:",
        ]
        lines += [f"  {signal.weight:+6.1f}  {signal.reason}" for signal in assessment.signals]
        return "\n".join(lines)
