"""Helpers for the term lists and reason texts of the assessment rules."""

import re
from collections.abc import Iterable


def normalize(text: str) -> str:
    """Lower case, hyphens and underscores become spaces."""
    return re.sub(r"[-_]+", " ", text.lower())


class TermList:
    """Finds terms as whole words. A plural s at the end of a term counts as well.

    Phrases in unless_in are taken out of the text first: in them a term means something else.
    """

    def __init__(self, terms: Iterable[str], unless_in: Iterable[str] = ()):
        self._unless_in = [
            re.compile(rf"(?<![a-z0-9]){re.escape(phrase).replace(r'\ ', r'\s+')}s?(?![a-z0-9])")
            for phrase in unless_in
        ]
        # longer terms first, so that "ai agent" is found before "ai"
        ordered = sorted(set(terms), key=lambda term: (-len(term), term))
        alternatives = "|".join(re.escape(term).replace(r"\ ", r"\s+") for term in ordered)
        self._pattern = re.compile(rf"(?<![a-z0-9])({alternatives})s?(?![a-z0-9])")

    def find(self, text: str) -> list[str]:
        """Every occurrence in the order of the text, without overlaps."""
        text = normalize(text)
        for phrase in self._unless_in:
            text = phrase.sub(" ", text)
        return [re.sub(r"\s+", " ", found) for found in self._pattern.findall(text)]

    def distinct(self, text: str) -> list[str]:
        return list(dict.fromkeys(self.find(text)))


def number(value: int) -> str:
    """German thousands separator: 91943 becomes 91.943."""
    return f"{value:,}".replace(",", ".")


def quoted(terms: Iterable[str], shown: int = 4) -> str:
    terms = list(terms)
    text = ", ".join(f"„{term}“" for term in terms[:shown])
    return text + (" …" if len(terms) > shown else "")
