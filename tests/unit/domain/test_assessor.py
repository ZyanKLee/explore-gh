import pytest
from builders import make_snapshot

from explore_gh.domain.assessor import Assessor
from explore_gh.domain.model import Section

assessor = Assessor()


def test_the_score_is_the_sum_of_all_signal_weights():
    assessment = assessor.assess(make_snapshot(description="A tiny editor for Linux"))

    assert assessment.score == pytest.approx(sum(s.weight for s in assessment.signals))
    assert {"momentum", "linux"} <= {s.kind for s in assessment.signals}


def test_momentum_comes_first():
    assert assessor.assess(make_snapshot()).signals[0].kind == "momentum"


def test_an_ordinary_repo_is_in_the_main_list_and_not_excluded():
    assessment = assessor.assess(make_snapshot())

    assert assessment.section is Section.MAIN
    assert assessment.exclusion is None


def test_an_excluded_repo_still_gets_section_and_signals():
    assessment = assessor.assess(
        make_snapshot(repo="alice/llm-chat", description="A chatbot", is_fork=True)
    )

    assert assessment.exclusion.kind == "fork"
    assert assessment.section is Section.AI
    assert assessment.signals


def test_ai_focus_signals_weigh_nothing():
    plain = assessor.assess(make_snapshot())
    ai = assessor.assess(make_snapshot(description="A tiny editor with AI"))

    assert ai.score == pytest.approx(plain.score)
