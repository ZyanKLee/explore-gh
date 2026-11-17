"""Copies: one project uploaded under several owners. Seen live as campaigns of lures.

Unlike the other exclusions this one needs all repos of a day, not a single Snapshot.
See docs/bewertung.md, "Kopien".
"""

import dataclasses
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Sequence
from datetime import timedelta

from github_anti_ai.domain.model import Assessment, Exclusion, RepoId, Snapshot

# A repo this much older than the next one of its group counts as the original and stays.
COPY_ORIGINAL_MIN_LEAD = timedelta(days=7)
# Shorter READMEs are too often the same by chance: a title and "TODO".
MIN_COPIED_README_CHARS = 500


def _text(text: str) -> str:
    """Without case and spacing."""
    return " ".join(text.casefold().split())


def _name_and_description(snapshot: Snapshot) -> Hashable | None:
    description = _text(snapshot.description)
    return (snapshot.repo.name.casefold(), description) if description else None


def _description_and_topics(snapshot: Snapshot) -> Hashable | None:
    description = _text(snapshot.description)
    return (description, frozenset(snapshot.topics)) if description and snapshot.topics else None


def _readme(snapshot: Snapshot) -> Hashable | None:
    readme = _text(snapshot.readme)
    return readme if len(readme) >= MIN_COPIED_README_CHARS else None


# What two repos of different owners must share to count as copies, and how to say it.
# The first match gives the reason.
SHARED: tuple[tuple[str, Callable[[Snapshot], Hashable | None]], ...] = (
    ("gleichem Namen und gleicher Beschreibung", _name_and_description),
    ("gleicher Beschreibung und gleichen Topics", _description_and_topics),
    ("gleichem README", _readme),
)


class CopyCheck:
    def find(self, snapshots: Iterable[Snapshot]) -> dict[RepoId, Exclusion]:
        """The repos that are the same as a repo of another owner."""
        candidates = [s for s in snapshots if not s.is_fork]  # a fork is excluded as a fork
        found: dict[RepoId, Exclusion] = {}
        for shared, key_of in SHARED:
            groups: dict[Hashable, list[Snapshot]] = defaultdict(list)
            for snapshot in candidates:
                if (key := key_of(snapshot)) is not None:
                    groups[key].append(snapshot)
            for group in groups.values():
                for repo, exclusion in _copies(group, shared).items():
                    found.setdefault(repo, exclusion)
        return found

    def apply(self, assessments: Sequence[Assessment]) -> list[Assessment]:
        """The assessments with the copies excluded. An earlier exclusion keeps its reason."""
        copies = self.find(assessment.snapshot for assessment in assessments)
        return [
            dataclasses.replace(assessment, exclusion=copies[assessment.repo])
            if assessment.exclusion is None and assessment.repo in copies
            else assessment
            for assessment in assessments
        ]


def _copies(group: list[Snapshot], shared: str) -> dict[RepoId, Exclusion]:
    if len({snapshot.repo.owner.casefold() for snapshot in group}) < 2:
        return {}
    oldest, second, *_ = sorted(group, key=lambda snapshot: snapshot.created_at)
    if second.created_at - oldest.created_at >= COPY_ORIGINAL_MIN_LEAD:
        exclusion = Exclusion(f"Kopie von {oldest.repo}", "copy")
        return {s.repo: exclusion for s in group if s is not oldest}
    exclusion = Exclusion(
        f"Kopie: {len(group)} Repos mit {shared}, fast gleichzeitig angelegt", "copy"
    )
    return {s.repo: exclusion for s in group}
