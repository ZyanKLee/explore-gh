import pytest

from builders import make_snapshot
from github_anti_ai.domain.ai_focus import AiFocusClassifier
from github_anti_ai.domain.model import Section

AI_README = (
    "# toolkit\n\nA toolkit for building LLM applications. It connects any LLM to your tools "
    "through MCP, ships a RAG pipeline and works with Claude and ChatGPT out of the box.\n"
)


def classify(repo="alice/tiny-editor", **overrides):
    return AiFocusClassifier().classify(make_snapshot(repo, **overrides))


def section(repo="alice/tiny-editor", **overrides):
    return classify(repo, **overrides).section


def test_repo_that_never_mentions_ai_belongs_to_the_main_list():
    focus = classify()

    assert focus.section is Section.MAIN
    assert focus.signals == ()


def test_ai_terms_in_two_places_make_an_ai_focused_repo():
    assert section(topics=("llm", "rust"), description="A fast LLM inference server") is Section.AI


@pytest.mark.parametrize(
    "overrides",
    [
        {"topics": ("llm",)},
        {"repo": "alice/mcp-server-postgres"},
        {"description": "Video editor with AI auto captions"},
        {"readme": AI_README},
    ],
)
def test_a_single_place_is_not_enough(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")

    assert section(repo, **overrides) is Section.MAIN


def test_a_single_mention_is_still_shown_as_a_signal():
    focus = classify(description="Video editor with AI auto captions")

    [signal] = focus.signals
    assert signal.kind == "ai_focus"
    assert signal.weight == 0
    assert "Beschreibung" in signal.reason
    assert "ai" in signal.reason.lower()


def test_each_place_with_ai_terms_gives_one_signal():
    focus = classify(
        "alice/mcp-server-postgres",
        topics=("mcp", "llm", "ai-agents"),
        description="MCP server that lets Claude query Postgres",
        readme=AI_README,
    )

    assert focus.section is Section.AI
    assert len(focus.signals) == 4
    assert all(s.kind == "ai_focus" and s.weight == 0 for s in focus.signals)


def test_readme_counts_only_when_it_is_full_of_ai_terms():
    in_passing = "# editor\n\nA text editor. An optional plugin adds AI completions.\n"

    assert classify("alice/gpt-editor", readme=in_passing).section is Section.MAIN
    assert classify("alice/gpt-editor", readme=AI_README).section is Section.AI


def test_hyphens_and_underscores_separate_words():
    assert section("alice/my_llm-proxy", topics=("ai-agents",)) is Section.AI


@pytest.mark.parametrize(
    "overrides",
    [
        {"topics": ("stable-diffusion",), "description": "Text-to-image generator for the desktop"},
        {"topics": ("comfyui",), "description": "Custom nodes for image generation"},
        {"repo": "alice/music-generation-studio", "description": "Text to music in your browser"},
        {"topics": ("text-to-video",), "description": "Local video generation with diffusion models"},
    ],
)
def test_image_music_and_video_generators_are_ai_focused(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")

    assert section(repo, **overrides) is Section.AI


def test_classic_machine_learning_is_not_ai_focused():
    focus = classify(
        "alice/vision-toolkit",
        topics=("machine-learning", "deep-learning", "pytorch", "computer-vision"),
        description="Neural network training framework for image classification",
        readme="# vision-toolkit\n\n" + "Train a neural network with PyTorch. " * 10,
    )

    assert focus.section is Section.MAIN
    assert focus.signals == ()


@pytest.mark.parametrize(
    ("repo", "description", "topics"),
    [
        ("alice/starship", "The minimal, blazing-fast cross-shell prompt", ("shell", "prompt")),
        ("alice/ua-parser", "Parses any user agent string", ("user-agent",)),
        ("alice/cursor-theme", "A mouse cursor theme for Linux desktops", ("cursor",)),
        ("alice/gemini-client", "A client for the Gemini protocol", ("gemini", "smallweb")),
        ("alice/heat", "Simulates heat diffusion in solids", ("diffusion", "physics")),
        ("alice/build-agent", "A build agent for self-hosted CI", ("build-agent", "ci")),
        ("alice/keyring", "Unlocks the SSH agent and the GPG agent at login", ("ssh-agent",)),
        ("alice/flock", "Agent-based simulation of bird flocks", ("agent-based-modeling",)),
    ],
)
def test_ambiguous_words_are_not_ai_terms(repo, description, topics):
    focus = classify(repo, description=description, topics=topics)

    assert focus.section is Section.MAIN
    assert focus.signals == ()


def test_ai_terms_only_count_as_whole_words():
    focus = classify("alice/rainfall", description="Maintains a rag-free trail of paid invoices")

    # "rainfall", "trail", "maintains" and "paid" contain "ai", but only "rag" is a term
    assert len(focus.signals) == 1


def test_repo_without_description_and_topics_is_judged_by_its_readme_alone():
    # seen live: such a repo has only two places left, a single one must be enough
    bare = dict(description="", topics=())

    assert section(readme=AI_README * 2, **bare) is Section.AI
    assert section(readme=AI_README, **bare) is Section.MAIN


def test_a_readme_alone_is_not_enough_when_the_description_says_something_else():
    assert section(readme=AI_README * 2, topics=()) is Section.MAIN


@pytest.mark.parametrize(
    ("repo", "description", "topics"),
    [
        ("alice/ovnfs", "Checkouts for agents: copy-on-write copies of any folder", ("agents",)),
        ("alice/agent-terminal", "Terminals for coding agents", ()),
        ("alice/harness", "A reactive harness for agents", ("agent", "typescript")),
    ],
)
def test_agent_is_an_ai_term(repo, description, topics):
    # decided on 2026-11-13: on GitHub the word hardly means anything else any more
    assert section(repo, description=description, topics=topics) is Section.AI


def test_agent_in_a_single_place_is_shown_but_does_not_move_the_repo():
    focus = classify(description="Mirror your phone to the desktop, plus a skill for agents")

    assert focus.section is Section.MAIN
    assert len(focus.signals) == 1
