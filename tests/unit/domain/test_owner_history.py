from datetime import timedelta

import pytest
from builders import NOW, make_snapshot

from github_anti_ai.domain.owner import OwnerHistory

history = OwnerHistory()


def signals_of(**overrides):
    return {s.kind: s for s in history.signals(make_snapshot(**overrides))}


@pytest.mark.parametrize(
    "days, points, reason",
    [
        (30, 0.25, "Besitzerkonto besteht seit 1 Monat"),
        (90, 0.75, "Besitzerkonto besteht seit 3 Monaten"),
        (400, 3.25, "Besitzerkonto besteht seit 1 Jahr"),
        (2000, 10.0, "Besitzerkonto besteht seit 5 Jahren"),
    ],
)
def test_each_month_of_the_owner_account_counts(days, points, reason):
    signal = signals_of(owner_created_at=NOW - timedelta(days=days))["owner_age"]

    assert (signal.weight, signal.reason) == (points, reason)


def test_an_account_younger_than_a_month_gets_nothing():
    assert signals_of(owner_created_at=NOW - timedelta(days=29)) == {}


def test_each_other_project_of_the_owner_counts_up_to_5():
    assert signals_of(owner_contributed_to=1)["owner_contributions"].reason == (
        "Besitzer wirkt an 1 anderen Projekt mit"
    )
    assert signals_of(owner_contributed_to=3)["owner_contributions"].weight == 3
    assert signals_of(owner_contributed_to=12)["owner_contributions"].weight == 5


def test_an_unknown_or_empty_history_gives_no_signal():
    assert signals_of(owner_created_at=None, owner_contributed_to=None) == {}
    assert signals_of(owner_contributed_to=0) == {}
