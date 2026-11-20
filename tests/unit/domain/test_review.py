import pytest
from builders import make_assessment

from explore_gh.domain.model import Exclusion, Section
from explore_gh.domain.review import REVIEW_CATEGORIES, REVIEW_GUIDE, Review, reviewed


def test_ok_keeps_the_repo_and_marks_it_as_read():
    after = reviewed(make_assessment(score=10), Review("ok", "Ein Editor."))

    assert after.exclusion is None
    assert after.section is Section.MAIN
    assert after.signals[-1].reason == "Gegengelesen von Copilot: unauffällig"
    assert after.score == 10


def test_ai_focus_moves_a_repo_of_the_main_list_to_the_ai_section():
    after = reviewed(make_assessment(), Review("ai_focus", "Forschung zu LLMs."))

    assert after.section is Section.AI
    assert after.exclusion is None
    assert after.signals[-1].reason == "Gegengelesen von Copilot: AI als Thema"


def test_ai_focus_counts_as_ok_in_the_ai_section():
    after = reviewed(make_assessment(section=Section.AI), Review("ai_focus", "Ein Agent."))

    assert after.section is Section.AI
    assert after.signals[-1].reason == "Gegengelesen von Copilot: unauffällig"


@pytest.mark.parametrize(
    "category, label",
    [
        ("malware", "Verdacht auf Schadsoftware"),
        ("piracy", "umgeht Kopierschutz oder verteilt fremde Inhalte"),
        ("scam", "Betrug oder Spam"),
        ("no_software", "kein eigenes Softwareprojekt"),
        ("placeholder", "Hülle ohne erkennbare Arbeit"),
        ("game_port", "Portierung oder Nachbau eines fremden Spiels"),
        ("downloader", "lädt Medien von Video- oder Musikplattformen herunter"),
        ("evasion", "umgeht Schutzmaßnahmen oder Grenzen eines Dienstes"),
    ],
)
def test_the_other_categories_take_the_repo_out(category, label):
    after = reviewed(make_assessment(), Review(category, "Lädt eine EXE."))

    assert after.exclusion == Exclusion(
        f"Gegengelesen von Copilot: {label}. Lädt eine EXE.", "review"
    )


def test_an_excluded_repo_stays_as_it_is():
    before = make_assessment(exclusion=Exclusion("Fork", "fork"))

    assert reviewed(before, Review("malware", "x")) == before


def test_an_unknown_category_is_refused():
    with pytest.raises(ValueError):
        Review("boring", "Langweilig.")


def test_every_category_is_explained_to_the_reviewer():
    assert set(REVIEW_GUIDE) == set(REVIEW_CATEGORIES)


def test_piracy_names_the_signs_of_breaking_drm():
    guide = REVIEW_GUIDE["piracy"]

    for sign in ("DRM", "Widevine", "PlayReady", "FairPlay", "CDM", "entschlüssel"):
        assert sign in guide


def test_piracy_names_unlocks_jailbreaks_stream_addons_and_shipped_content():
    guide = REVIEW_GUIDE["piracy"]

    for sign in ("Premium", "Jailbreak", "CloudStream", "Stremio", "Spieldaten"):
        assert sign in guide


def test_evasion_names_bot_protection_limits_and_fake_activity():
    guide = REVIEW_GUIDE["evasion"]

    for sign in ("Captcha", "Turnstile", "Gratis", "Geräte-ID", "Spielzeit"):
        assert sign in guide
    assert "Werbeblocker" in guide  # what it is not
