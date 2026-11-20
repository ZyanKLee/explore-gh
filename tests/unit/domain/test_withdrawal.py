from datetime import date

from builders import make_assessment

from explore_gh.domain.model import Exclusion
from explore_gh.domain.withdrawal import Withdrawal, withdrawn

GAME_DATA = Withdrawal(
    "https://github.com/Alice/Tiny-Editor/", date(2026, 11, 21), "Verteilt fremde Spieldaten"
)


def test_a_withdrawn_repo_is_excluded_with_its_reason():
    after = withdrawn(make_assessment("alice/tiny-editor"), [GAME_DATA])

    assert after.exclusion == Exclusion(
        "Zurückgezogen am 21.11.2026: Verteilt fremde Spieldaten", "withdrawn"
    )


def test_another_repo_stays_as_it_is():
    before = make_assessment("bob/editor")

    assert withdrawn(before, [GAME_DATA]) == before


def test_a_withdrawal_names_a_repo_regardless_of_case_and_a_trailing_slash():
    assert GAME_DATA.names("https://github.com/alice/tiny-editor")
    assert not GAME_DATA.names("https://github.com/alice/tiny-editor-2")
