import pytest

from builders import make_commit, make_snapshot
from github_anti_ai.domain.ai_assistance import AI_COMMITS_MAX_PENALTY, AiAssistanceDetector

CLAUDE = "Claude <noreply@anthropic.com>"


def detect(**overrides):
    return AiAssistanceDetector().detect(make_snapshot(**overrides))


def signal(kind, **overrides):
    found = [s for s in detect(**overrides) if s.kind == kind]
    assert len(found) <= 1
    return found[0] if found else None


def commits(ai=0, human=0, bots=0):
    return (
        tuple(make_commit(co_authors=(CLAUDE,)) for _ in range(ai))
        + tuple(make_commit() for _ in range(human))
        + tuple(make_commit(author="dependabot[bot]", is_bot=True) for _ in range(bots))
    )


def test_repo_without_ai_traces_gets_no_signal():
    assert detect() == ()


def test_commits_with_an_ai_co_author_lower_the_score_in_proportion():
    result = signal("ai_commits", recent_commits=commits(ai=3, human=1))

    assert result.weight == pytest.approx(-AI_COMMITS_MAX_PENALTY * 0.75)
    assert "75" in result.reason


def test_fully_ai_assisted_history_gets_the_full_penalty():
    result = signal("ai_commits", recent_commits=commits(ai=8))

    assert result.weight == pytest.approx(-AI_COMMITS_MAX_PENALTY)


def test_occasional_ai_assistance_is_ignored():
    assert signal("ai_commits", recent_commits=commits(ai=1, human=19)) is None


def test_ordinary_bots_neither_count_as_ai_nor_dilute_the_share():
    result = signal("ai_commits", recent_commits=commits(ai=1, human=1, bots=8))

    assert result.weight == pytest.approx(-AI_COMMITS_MAX_PENALTY * 0.5)


def test_commit_written_by_an_ai_agent_counts_like_a_co_authored_one():
    agent_commit = make_commit(author="copilot-swe-agent[bot]", is_bot=True)

    result = signal("ai_commits", recent_commits=(agent_commit, make_commit()))

    assert result.weight == pytest.approx(-AI_COMMITS_MAX_PENALTY * 0.5)


@pytest.mark.parametrize(
    "co_author",
    [
        "Claude <noreply@anthropic.com>",
        "Claude Opus 5.5 <noreply@anthropic.com>",
        "Copilot <175728472+Copilot@users.noreply.github.com>",
        "Cursor Agent <cursoragent@cursor.com>",
        "aider (gpt-5) <aider@aider.chat>",
        "Codex <codex@openai.com>",
        "Devin AI <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
        "capy-ai[bot] <230910855+capy-ai[bot]@users.noreply.github.com>",
        "google-labs-jules[bot] <161369871+google-labs-jules[bot]@users.noreply.github.com>",
    ],
)
def test_common_ai_tools_are_recognized_as_co_authors(co_author):
    result = signal("ai_commits", recent_commits=(make_commit(co_authors=(co_author,)),))

    assert result is not None


@pytest.mark.parametrize(
    "co_author",
    [
        "Carol <carol@example.org>",
        "Claudette Example <claudette@example.org>",
        "Amparo Cline-Meyer <amparo@example.org>",
        "Jules Verne <jules.verne@example.org>",
        "Devin Smith <devin@example.org>",
    ],
)
def test_people_are_not_mistaken_for_ai_tools(co_author):
    assert signal("ai_commits", recent_commits=(make_commit(co_authors=(co_author,)),)) is None


def test_repo_without_commits_gets_no_commit_signal():
    assert signal("ai_commits", recent_commits=()) is None


def test_agent_instruction_files_lower_the_score_slightly():
    result = signal("ai_files", root_files=("AGENTS.md", "Cargo.toml", "README.md", "src"))

    assert -AI_COMMITS_MAX_PENALTY / 5 < result.weight < 0
    assert "AGENTS.md" in result.reason


def test_several_instruction_files_give_one_signal_naming_them_all():
    result = signal("ai_files", root_files=(".claude", ".cursorrules", "claude.md", "src"))
    single = signal("ai_files", root_files=("CLAUDE.md", "src"))

    assert result.weight == single.weight
    for name in (".claude", ".cursorrules", "claude.md"):
        assert name in result.reason


def test_an_ai_policy_is_not_an_instruction_file():
    assert signal("ai_files", root_files=("AI_POLICY.md", "CONTRIBUTING.md", "src")) is None
