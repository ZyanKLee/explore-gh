import pytest

from builders import make_commit, make_snapshot, star_history
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.model import Section

CLAUDE = "Claude <noreply@anthropic.com>"


def assess(repo="alice/tiny-editor", **overrides):
    return Assessor().assess(make_snapshot(repo, **overrides))


def kinds(assessment):
    return {signal.kind for signal in assessment.signals}


def test_score_is_the_sum_of_all_signal_weights():
    assessment = assess(
        root_files=("AGENTS.md", "src"),
        recent_commits=(make_commit(co_authors=(CLAUDE,)), make_commit(author="bob")),
    )

    assert len(assessment.signals) >= 4
    assert assessment.score == pytest.approx(sum(s.weight for s in assessment.signals))


def test_assessment_keeps_the_snapshot_it_judged():
    snapshot = make_snapshot()

    assert Assessor().assess(snapshot).snapshot == snapshot


def test_every_assessment_has_a_momentum_signal():
    assert "momentum" in kinds(assess())


def test_ordinary_repo_goes_to_the_main_list_without_exclusion():
    assessment = assess()

    assert assessment.section is Section.MAIN
    assert assessment.exclusion is None


def test_ai_focused_repo_goes_to_the_ai_section_and_says_why():
    assessment = assess(topics=("llm",), description="A fast LLM inference server")

    assert assessment.section is Section.AI
    assert "ai_focus" in kinds(assessment)


def test_ai_focus_does_not_change_the_score():
    plain = assess(description="A fast inference server")
    focused = assess(topics=("llm",), description="A fast LLM inference server")

    assert focused.score == pytest.approx(plain.score)


def test_ai_assistance_lowers_the_score_but_never_excludes():
    by_hand = assess(recent_commits=(make_commit(), make_commit()))
    assisted = assess(recent_commits=(make_commit(co_authors=(CLAUDE,)),) * 2)

    assert assisted.score < by_hand.score
    assert assisted.exclusion is None


def test_excluded_repo_is_still_assessed_in_full():
    assessment = assess(is_fork=True, topics=("llm",), description="A fast LLM inference server")

    assert assessment.exclusion.kind == "fork"
    assert assessment.section is Section.AI
    assert "momentum" in kinds(assessment)
    assert assessment.score == pytest.approx(sum(s.weight for s in assessment.signals))


def test_stars_without_echo_score_below_an_honest_repo_with_half_the_gain():
    lure = assess(
        stars=100, star_history=star_history(100), forks=0, recent_issue_authors=0, pull_requests=0
    )
    honest = assess(stars=50, star_history=star_history(50), forks=5)

    assert lure.score < honest.score


def test_assessor_can_be_plugged_into_the_publishing_use_case():
    # PublishEdition expects a function from Snapshot to Assessment
    assessor = Assessor()

    assert assessor.assess(make_snapshot()).repo == make_snapshot().repo
