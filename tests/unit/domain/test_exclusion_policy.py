from datetime import timedelta

import pytest
from builders import NOW, make_snapshot, star_history

from explore_gh.domain.exclusion import ExclusionPolicy

policy = ExclusionPolicy()


def exclusion_of(**overrides):
    return policy.check(make_snapshot(**overrides))


def test_an_ordinary_repo_is_not_excluded():
    assert exclusion_of() is None


@pytest.mark.parametrize(
    "overrides, kind, reason",
    [
        ({"is_fork": True}, "fork", "Fork"),
        ({"is_archived": True}, "archived", "Archiviert"),
        ({"is_mirror": True}, "mirror", "Spiegel eines anderen Repos"),
        ({"primary_language": None}, "no_code", "GitHub erkennt keine Programmiersprache"),
    ],
)
def test_forks_archives_mirrors_and_repos_without_code_are_excluded(overrides, kind, reason):
    exclusion = exclusion_of(**overrides)

    assert (exclusion.kind, exclusion.reason) == (kind, reason)


@pytest.mark.parametrize(
    "overrides",
    [
        {"repo": "alice/awesome-rust"},
        {"description": "A curated list of editors"},
        {"topics": ("interview-preparation",)},
        {"description": "My dotfiles"},
        {"description": "System prompts of famous tools"},
    ],
)
def test_collections_and_learning_material_are_excluded(overrides):
    assert exclusion_of(**overrides).kind == "collection"


def test_the_reason_of_a_collection_names_the_term():
    assert (
        exclusion_of(description="A Rust tutorial").reason
        == "Sammlung oder Lernmaterial („tutorial“)"
    )


@pytest.mark.parametrize(
    "description",
    [
        "Adobe Acrobat Pro 2026: Secure Standalone Desktop Setup",
        "Xshell full version, pre-activated",
        "Office with all features enabled",
    ],
)
def test_lures_for_malware_are_excluded_by_their_wording(description):
    exclusion = exclusion_of(description=description)

    assert exclusion.kind == "lure"
    assert exclusion.reason.startswith("Köder für Schadsoftware („")


@pytest.mark.parametrize(
    "description", ["A standalone tool", "Setup for your editor", "An installer for fonts"]
)
def test_standalone_setup_or_installer_alone_is_no_lure(description):
    assert exclusion_of(description=description) is None


LURE_MARKDOWN = (
    "[![Download](files/button.png)](https://someone.github.io/get/)\n\n"
    "Open PowerShell and paste the command."
)
LURE_HTML = (
    '<a href="https://someone.github.io/dl"><img src="assets/download-button.svg"></a>\n'
    "Run it in powershell."
)


@pytest.mark.parametrize("readme", [LURE_MARKDOWN, LURE_HTML])
def test_the_readme_template_of_lures_is_excluded(readme):
    exclusion = exclusion_of(readme=readme)

    assert exclusion.kind == "lure"
    assert exclusion.reason == (
        "Köder für Schadsoftware (README führt über einen Knopf zu einem PowerShell-Befehl)"
    )


def test_a_button_without_powershell_is_no_lure():
    assert exclusion_of(readme=LURE_MARKDOWN.replace("PowerShell", "your shell")) is None


def test_a_repo_without_readme_is_excluded():
    assert exclusion_of(readme="  \n").reason == "Kein README"


def test_a_foreign_language_is_excluded():
    assert exclusion_of(description="终端的小工具").kind == "language"


@pytest.mark.parametrize(
    "overrides",
    [{"description": "A Bitcoin wallet"}, {"topics": ("web3",)}, {"repo": "alice/nft-tools"}],
)
def test_cryptocurrencies_are_excluded(overrides):
    assert exclusion_of(**overrides).kind == "crypto"


@pytest.mark.parametrize(
    "description", ["A cryptography library", "Token bucket", "Wallet for passes"]
)
def test_cryptography_tokens_and_wallets_are_no_cryptocurrency(description):
    assert exclusion_of(description=description) is None


def test_less_than_14_days_of_development_exclude():
    exclusion = exclusion_of(created_at=NOW - timedelta(days=13), pushed_at=NOW)

    assert exclusion.kind == "young"
    assert exclusion.reason == "Erst 13 Tage Entwicklung auf GitHub, nötig sind 14"


def test_14_days_of_development_are_enough():
    assert exclusion_of(created_at=NOW - timedelta(days=14), pushed_at=NOW) is None


def test_a_repo_never_pushed_counts_as_young():
    assert exclusion_of(pushed_at=None).kind == "young"


def test_less_than_60_new_stars_exclude():
    exclusion = exclusion_of(star_history=star_history(59))

    assert exclusion.kind == "low_momentum"
    assert exclusion.reason == "Nur 59 neue Sterne in 14 Tagen, nötig sind 60"


def test_60_new_stars_are_enough():
    assert exclusion_of(star_history=star_history(60)) is None


def test_the_first_matching_rule_gives_the_reason():
    assert exclusion_of(is_fork=True, description="awesome bitcoin").kind == "fork"


class TestCheckText:
    def test_an_unreadable_readme_is_no_reason_to_exclude(self):
        assert (
            policy.check_text(name="tiny", description="An editor", topics=(), readme=None) is None
        )

    def test_an_empty_readme_is(self):
        exclusion = policy.check_text(name="tiny", description="An editor", topics=(), readme="")

        assert exclusion.kind == "no_readme"
