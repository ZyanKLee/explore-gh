"""Withdrawal: the owner takes a repo back that a published edition showed.

Editions never change. A withdrawn repo stays in them, but the site shows it without a
link and with the reason, and no new edition shows it again. See docs/ausgabe.md.
"""

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from explore_gh.domain.model import Assessment, Exclusion


@dataclass(frozen=True)
class Withdrawal:
    repository_url: str  # the address of the repo, on GitHub or another forge
    day: date
    reason: str

    def names(self, url: str) -> bool:
        return _key(url) == _key(self.repository_url)

    @property
    def note(self) -> str:
        return f"Zurückgezogen am {self.day:%d.%m.%Y}: {self.reason}"


def withdrawn(assessment: Assessment, withdrawals: Iterable[Withdrawal]) -> Assessment:
    """The assessment, excluded if the repo was withdrawn."""
    for withdrawal in withdrawals:
        if withdrawal.names(assessment.repo.url):
            exclusion = Exclusion(withdrawal.note, "withdrawn")
            return dataclasses.replace(assessment, exclusion=exclusion)
    return assessment


def _key(url: str) -> str:
    return url.rstrip("/").casefold()
