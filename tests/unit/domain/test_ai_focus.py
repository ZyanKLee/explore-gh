import pytest
from builders import make_snapshot

from explore_gh.domain.ai_focus import AiFocusClassifier
from explore_gh.domain.model import Section

classifier = AiFocusClassifier()


def focus(**overrides):
    return classifier.classify(make_snapshot(**overrides))


def readme_with(mentions: int) -> str:
    return "# Tool\n\n" + "It talks to an LLM. " * mentions


def test_an_ordinary_repo_stays_in_the_main_list_without_signals():
    result = focus()

    assert result.section is Section.MAIN
    assert result.signals == ()


def test_ai_terms_in_two_places_mean_the_ai_section():
    result = focus(repo="alice/chat-llm", description="A chatbot for your terminal")

    assert result.section is Section.AI
    assert [s.reason for s in result.signals] == [
        "Name: AI-Begriffe „llm“",
        "Beschreibung: AI-Begriffe „chatbot“",
    ]
    assert all(s.kind == "ai_focus" and s.weight == 0 for s in result.signals)


def test_one_mention_only_shows_in_the_reasons():
    result = focus(description="A video editor with AI auto captions")

    assert result.section is Section.MAIN
    assert [s.reason for s in result.signals] == ["Beschreibung: AI-Begriffe „ai“"]


def test_the_readme_counts_as_a_place_from_5_mentions():
    result = focus(description="An agent for your shell", readme=readme_with(5))

    assert result.section is Section.AI
    assert result.signals[-1].reason == "README: 5-mal AI-Begriffe („llm“)"


def test_4_mentions_in_the_readme_are_no_place():
    assert (
        focus(description="An agent for your shell", readme=readme_with(4)).section is Section.MAIN
    )


def test_two_different_ai_terms_among_the_topics_decide_alone():
    assert focus(topics=("llm", "image-generation")).section is Section.AI


def test_one_ai_term_among_the_topics_does_not():
    assert focus(topics=("llm", "editor")).section is Section.MAIN


def test_a_readme_with_50_mentions_decides_alone():
    assert focus(readme=readme_with(50)).section is Section.AI
    assert focus(readme=readme_with(49)).section is Section.MAIN


@pytest.mark.parametrize("description", ["", "The official code of ToolSpace"])
def test_without_description_and_topics_10_readme_mentions_suffice(description):
    result = focus(
        repo="alice/ToolSpace", description=description, topics=(), readme=readme_with(10)
    )

    assert result.section is Section.AI


def test_without_description_and_topics_9_readme_mentions_do_not():
    result = focus(repo="alice/ToolSpace", description="", topics=(), readme=readme_with(9))

    assert result.section is Section.MAIN


def test_a_description_of_its_own_needs_two_places():
    result = focus(description="Plan your trips", topics=(), readme=readme_with(10))

    assert result.section is Section.MAIN


@pytest.mark.parametrize(
    "description", ["Fake the user agent of a browser", "A small ssh-agent", "TPM agent"]
)
def test_old_meanings_of_agent_are_no_ai_terms(description):
    assert focus(repo="alice/agent-tools", description=description).signals == (
        focus(repo="alice/agent-tools", description="").signals
    )


@pytest.mark.parametrize(
    "term", ["machine learning", "neural network", "pytorch", "gemini", "prompt"]
)
def test_classic_machine_learning_and_ambiguous_words_are_no_ai_terms(term):
    assert focus(description=f"Uses {term}").signals == ()


def test_classify_text_works_without_a_snapshot():
    result = classifier.classify_text(
        name="llm-proxy", description="Proxy for OpenAI", topics=(), readme=""
    )

    assert result.section is Section.AI
