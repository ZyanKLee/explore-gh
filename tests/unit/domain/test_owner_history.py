from datetime import timedelta

from builders import NOW, make_snapshot
from github_anti_ai.domain.owner import (
    OWNER_AGE_MAX_POINTS,
    OWNER_AGE_POINTS_PER_MONTH,
    OWNER_CONTRIBUTION_MAX_POINTS,
    OWNER_CONTRIBUTION_POINTS,
    OwnerHistory,
)


def signal(kind, **overrides):
    found = [s for s in OwnerHistory().signals(make_snapshot(**overrides)) if s.kind == kind]
    assert len(found) <= 1
    return found[0] if found else None


def account_aged(**age):
    return signal("owner_age", owner_created_at=NOW - timedelta(**age))


def test_every_month_of_the_owners_account_adds_to_the_score():
    found = account_aged(days=30 * 7 + 3)

    assert found.weight == 7 * OWNER_AGE_POINTS_PER_MONTH
    assert found.reason == "Besitzerkonto besteht seit 7 Monaten"


def test_an_account_of_less_than_a_month_adds_nothing():
    assert account_aged(days=29) is None


def test_an_old_account_is_named_in_years_and_its_bonus_is_capped():
    found = account_aged(days=365 * 9)

    assert found.weight == OWNER_AGE_MAX_POINTS
    assert found.reason == "Besitzerkonto besteht seit 9 Jahren"


def test_singular_wording_for_one_month_and_one_year():
    assert account_aged(days=31).reason == "Besitzerkonto besteht seit 1 Monat"
    assert account_aged(days=366).reason == "Besitzerkonto besteht seit 1 Jahr"


def test_unknown_account_age_adds_nothing():
    assert signal("owner_age", owner_created_at=None) is None


def test_every_other_project_the_owner_contributes_to_adds_to_the_score():
    found = signal("owner_contributions", owner_contributed_to=3)

    assert found.weight == 3 * OWNER_CONTRIBUTION_POINTS
    assert found.reason == "Besitzer wirkt an 3 anderen Projekten mit"


def test_bonus_for_contributions_is_capped():
    found = signal("owner_contributions", owner_contributed_to=40)

    assert found.weight == OWNER_CONTRIBUTION_MAX_POINTS


def test_singular_wording_for_one_other_project():
    found = signal("owner_contributions", owner_contributed_to=1)

    assert found.reason == "Besitzer wirkt an 1 anderen Projekt mit"


def test_no_or_unknown_contributions_add_nothing():
    assert signal("owner_contributions", owner_contributed_to=0) is None
    assert signal("owner_contributions", owner_contributed_to=None) is None
