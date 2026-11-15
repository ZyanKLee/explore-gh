import pytest

from builders import make_assessment
from github_anti_ai.domain.model import Exclusion
from github_anti_ai.domain.review import REVIEW_CATEGORIES, Review, reviewed


def test_a_repo_reviewed_as_fine_stays_and_says_that_it_was_reviewed():
    assessment = make_assessment(score=42.0)

    result = reviewed(assessment, Review("ok", "Ein Texteditor mit eigenem Code."))

    assert result.exclusion is None
    assert result.score == 42.0
    [signal] = result.signals
    assert (signal.kind, signal.weight) == ("review", 0)
    assert signal.reason == "Gegengelesen von Copilot: unauffällig"


@pytest.mark.parametrize(
    ("category", "label"),
    [
        ("malware", "Verdacht auf Schadsoftware"),
        ("piracy", "umgeht Kopierschutz oder verteilt fremde Inhalte"),
        ("scam", "Betrug oder Spam"),
        ("no_software", "kein eigenes Softwareprojekt"),
        ("placeholder", "Hülle ohne erkennbare Arbeit"),
    ],
)
def test_a_problematic_or_uninteresting_repo_is_excluded_with_the_reason(category, label):
    result = reviewed(make_assessment(), Review(category, "Das README verlinkt nur ein ZIP."))

    assert result.exclusion == Exclusion(
        f"Gegengelesen von Copilot: {label}. Das README verlinkt nur ein ZIP.", "review"
    )
    assert result.signals == ()


def test_a_repo_that_is_already_excluded_keeps_its_reason():
    lure = Exclusion("Köder für Schadsoftware („full version“)", "lure")

    result = reviewed(make_assessment(exclusion=lure), Review("malware", "Köder."))

    assert result.exclusion == lure


def test_every_category_but_ok_excludes():
    assert REVIEW_CATEGORIES["ok"] is None
    assert all(label for category, label in REVIEW_CATEGORIES.items() if category != "ok")


def test_an_unknown_category_is_no_review():
    with pytest.raises(ValueError):
        Review("boring", "Gefällt mir nicht.")
