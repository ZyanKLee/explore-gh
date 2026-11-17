import pytest
from builders import make_commit, make_snapshot

from github_anti_ai.domain.ai_assistance import AiAssistanceDetector, is_ai_assisted, is_ai_tool

detector = AiAssistanceDetector()


def signals_of(**overrides):
    return {s.kind: s for s in detector.signals(make_snapshot(**overrides))}


def commits(by_ai: int, by_hand: int, bots: int = 0):
    return (
        tuple(make_commit(co_authors=("Claude <noreply@anthropic.com>",)) for _ in range(by_ai))
        + tuple(make_commit() for _ in range(by_hand))
        + tuple(make_commit(author="dependabot[bot]", is_bot=True) for _ in range(bots))
    )


def test_ai_commits_cost_up_to_15_points_by_their_share():
    signal = signals_of(recent_commits=commits(by_ai=3, by_hand=1))["ai_commits"]

    assert signal.weight == pytest.approx(-11.25)
    assert signal.reason == "75% der letzten Commits mit AI-Beteiligung (3 von 4)"


def test_a_share_below_10_percent_costs_nothing():
    assert "ai_commits" not in signals_of(recent_commits=commits(by_ai=1, by_hand=10))


def test_ordinary_bots_count_neither_as_ai_nor_as_human():
    signal = signals_of(recent_commits=commits(by_ai=1, by_hand=1, bots=8))["ai_commits"]

    assert signal.reason.endswith("(1 von 2)")


def test_only_bots_give_no_signal():
    assert signals_of(recent_commits=commits(by_ai=0, by_hand=0, bots=3)) == {}


def test_instruction_files_for_agents_cost_3_points():
    signal = signals_of(root_files=("CLAUDE.md", ".cursorrules", "src"))["ai_files"]

    assert signal.weight == -3
    assert signal.reason == "Anweisungsdateien für AI-Agenten: CLAUDE.md, .cursorrules"


def test_an_ai_policy_is_no_instruction_file():
    assert signals_of(root_files=("AI_POLICY.md",)) == {}


@pytest.mark.parametrize(
    "co_author",
    [
        "Claude <noreply@anthropic.com>",
        "Claude Opus 5.5 <x@example.org>",
        "Copilot <175728472+Copilot@users.noreply.github.com>",
        "Devin AI <x@example.org>",
        "Someone <bot@cursor.com>",
        "Codex <x@example.org>",
        "gpt-4o <x@example.org>",
        "Aider (anthropic/claude) <x@example.org>",
    ],
)
def test_ai_tools_are_recognized_as_co_authors(co_author):
    assert is_ai_tool(co_author)


@pytest.mark.parametrize(
    "co_author",
    [
        "Claude Monet <claude@example.org>",
        "Devin Smith <devin@example.org>",
        "Jules <j@example.org>",
    ],
)
def test_people_with_the_names_of_tools_are_not(co_author):
    assert not is_ai_tool(co_author)


def test_a_commit_written_by_an_ai_account_is_ai_assisted():
    assert is_ai_assisted(make_commit(author="copilot-swe-agent[bot]", is_bot=True))
    assert not is_ai_assisted(make_commit(author="alice"))
