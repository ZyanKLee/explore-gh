"""Copies: one project uploaded under several owners. Seen live as a campaign of lures.

Unlike the other exclusions this one needs all repos of a day, not a single Snapshot.
"""

import dataclasses
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import timedelta

from github_anti_ai.domain.model import Assessment, Exclusion, RepoId, Snapshot

# A repo this much older than the next one of its group counts as the original and stays.
COPY_ORIGINAL_MIN_LEAD = timedelta(days=7)


class CopyCheck:
    def find(self, snapshots: Iterable[Snapshot]) -> dict[RepoId, Exclusion]:
        """The repos that share name and description with a repo of another owner."""
        groups: dict[tuple[str, str], list[Snapshot]] = defaultdict(list)
        for snapshot in snapshots:
            description = " ".join(snapshot.description.casefold().split())
            if description and not snapshot.is_fork:  # a fork is excluded as a fork
                groups[snapshot.repo.name.casefold(), description].append(snapshot)

        found: dict[RepoId, Exclusion] = {}
        for group in groups.values():
            if len({snapshot.repo.owner.casefold() for snapshot in group}) < 2:
                continue
            oldest, second, *_ = sorted(group, key=lambda snapshot: snapshot.created_at)
            if second.created_at - oldest.created_at >= COPY_ORIGINAL_MIN_LEAD:
                exclusion = Exclusion(f"Kopie von {oldest.repo}", "copy")
                copies = [snapshot for snapshot in group if snapshot is not oldest]
            else:
                exclusion = Exclusion(
                    f"Kopie: {len(group)} Repos mit gleichem Namen und gleicher Beschreibung, "
                    "fast gleichzeitig angelegt",
                    "copy",
                )
                copies = group
            for snapshot in copies:
                found[snapshot.repo] = exclusion
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
