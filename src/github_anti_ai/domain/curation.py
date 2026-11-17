"""Selection rules every list shares: GitHub, HN and Lobsters. See docs/ausgabe.md."""

from collections import Counter
from collections.abc import Callable, Hashable, Iterable
from datetime import date
from typing import TypeVar

ENTRIES_PER_SECTION = 20
MAX_PER_LANGUAGE = 4
MAX_PER_OWNER = 2
COOLDOWN_DAYS = 30

Item = TypeVar("Item")


def in_cooldown(shown_on: date, day: date) -> bool:
    """Shown on day D, a repo is blocked through D + 29 and may return on D + 30.

    A day published again after later days blocks what these later days show as well.
    """
    return abs((day - shown_on).days) < COOLDOWN_DAYS


def varied(
    ranked: Iterable[Item],
    language_of: Callable[[Item], str | None],
    owner_of: Callable[[Item], Hashable],
) -> list[Item]:
    """The best of `ranked`, in order, skipping what would break the variety rule.

    Repos without a recognized language form a group of their own. The list is never filled up.
    """
    selected: list[Item] = []
    per_language: Counter = Counter()
    per_owner: Counter = Counter()
    for item in ranked:
        language, owner = language_of(item), owner_of(item)
        if per_language[language] == MAX_PER_LANGUAGE or per_owner[owner] == MAX_PER_OWNER:
            continue
        per_language[language] += 1
        per_owner[owner] += 1
        selected.append(item)
        if len(selected) == ENTRIES_PER_SECTION:
            break
    return selected


def check_section(
    items: Iterable[Item],
    language_of: Callable[[Item], str | None],
    owner_of: Callable[[Item], Hashable],
    name: str,
) -> None:
    """The invariants of one section of an edition. `name` says which one in the message."""
    items = list(items)
    if len(items) > ENTRIES_PER_SECTION:
        raise ValueError(f"{name}: mehr als {ENTRIES_PER_SECTION} Einträge")
    languages = Counter(language_of(item) for item in items)
    if languages and max(languages.values()) > MAX_PER_LANGUAGE:
        raise ValueError(f"{name}: mehr als {MAX_PER_LANGUAGE} Einträge einer Sprache")
    owners = Counter(owner_of(item) for item in items)
    if owners and max(owners.values()) > MAX_PER_OWNER:
        raise ValueError(f"{name}: mehr als {MAX_PER_OWNER} Einträge eines Besitzers")


def check_unique(keys: Iterable[Hashable], name: str) -> None:
    keys = list(keys)
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name}: ein Repo steht mehrfach in der Ausgabe")
