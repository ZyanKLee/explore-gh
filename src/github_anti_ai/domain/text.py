"""Helpers for the term lists and reason texts of the assessment rules."""

import re
from collections.abc import Iterable


def normalize(text: str) -> str:
    """Lower case, hyphens and underscores become spaces."""
    return re.sub(r"[-_]+", " ", text.lower())


class TermList:
    """Finds terms as whole words. A plural s at the end of a term counts as well."""

    def __init__(self, terms: Iterable[str]):
        # longer terms first, so that "ai agent" is found before "ai"
        ordered = sorted(set(terms), key=lambda term: (-len(term), term))
        alternatives = "|".join(re.escape(term).replace(r"\ ", r"\s+") for term in ordered)
        self._pattern = re.compile(rf"(?<![a-z0-9])({alternatives})s?(?![a-z0-9])")

    def find(self, text: str) -> list[str]:
        """Every occurrence in the order of the text, without overlaps."""
        return [re.sub(r"\s+", " ", found) for found in self._pattern.findall(normalize(text))]

    def distinct(self, text: str) -> list[str]:
        return list(dict.fromkeys(self.find(text)))


def number(value: int) -> str:
    """German thousands separator: 91943 becomes 91.943."""
    return f"{value:,}".replace(",", ".")


def quoted(terms: Iterable[str], shown: int = 4) -> str:
    terms = list(terms)
    text = ", ".join(f"„{term}“" for term in terms[:shown])
    return text + (" …" if len(terms) > shown else "")
