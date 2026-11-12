from datetime import date

from github_anti_ai.application.ports import Assessor, SnapshotStore
from github_anti_ai.domain.model import RepoId, Section

SECTION_NAMES = {Section.MAIN: "Hauptliste", Section.AI: "AI-Sektion"}


class UnknownRepo(Exception):
    def __init__(self, day: date, repo: RepoId):
        super().__init__(f"Keine Momentaufnahme von {repo} am {day}")


class ExplainAssessment:
    def __init__(self, snapshot_store: SnapshotStore, assess: Assessor):
        self._snapshot_store = snapshot_store
        self._assess = assess

    def run(self, day: date, repo: RepoId) -> str:
        """Section, score, exclusion and every signal of a repo as plain text."""
        for snapshot in self._snapshot_store.load(day):
            if snapshot.repo == repo:
                break
        else:
            raise UnknownRepo(day, repo)

        assessment = self._assess(snapshot)
        exclusion = assessment.exclusion.reason if assessment.exclusion else "keiner"
        lines = [
            str(snapshot.repo),
            f"Sektion: {SECTION_NAMES[assessment.section]}",
            f"Punktzahl: {assessment.score:.1f}",
            f"Ausschluss: {exclusion}",
            "Signale:",
        ]
        lines += [f"  {signal.weight:+6.1f}  {signal.reason}" for signal in assessment.signals]
        return "\n".join(lines)
