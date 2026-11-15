"""Decides whether a repo exists for the use of AI and therefore belongs to the AI section."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from github_anti_ai.domain.model import Section, Signal, Snapshot
from github_anti_ai.domain.text import TermList, quoted

AI_TERMS = TermList(
    [
        "ai",
        "llm",
        "gpt",
        "chatgpt",
        "openai",
        "anthropic",
        "claude",
        "deepseek",
        "copilot",
        "codex",
        "ollama",
        "llama",
        "llamaindex",
        "vllm",
        "litellm",
        "gguf",
        "vlm",
        "language model",
        "foundation model",
        "huggingface",
        "hugging face",
        "diffusers",
        "openrouter",
        "lm studio",
        "open webui",
        "gemma",
        "mistral",
        "qwen",
        "sdxl",
        "aigc",
        "langchain",
        "langgraph",
        "crewai",
        "autogen",
        "tool calling",
        "text generation",
        "mcp",
        "rag",
        "agentic",
        "agent",
        "ai agent",
        "coding agent",
        "agent skill",
        "subagent",
        "multi agent",
        "chatbot",
        "genai",
        "generative ai",
        "large language model",
        "prompt engineering",
        "system prompt",
        "vibe coding",
        "stable diffusion",
        "diffusion model",
        "comfyui",
        "midjourney",
        "text to image",
        "image generation",
        "text to video",
        "video generation",
        "text to music",
        "music generation",
    ],
    # "agent" has older meanings that have nothing to do with AI
    unless_in=[
        "user agent",
        "build agent",
        "ssh agent",
        "gpg agent",
        "tpm agent",  # ssh-tpm-agent and its relatives
        "monitoring agent",
        "agent based",
    ],
)
MIN_PLACES = 2
MIN_README_MENTIONS = 5
# Topics are the owner's own labels: several different AI terms there decide on their own.
MIN_TOPIC_TERMS = 2
# A repo without description and topics has only name and README left to show its purpose.
MIN_README_MENTIONS_ALONE = 10
# Words that say nothing about a repo's purpose: "The official code of ToolSpace".
FILLER_WORDS = frozenset(
    "a an the this is of for to and official code repo repository implementation "
    "source project application app demo paper".split()
)
# A README that talks about little else than AI decides on its own, whatever the rest says.
MIN_README_MENTIONS_DOMINANT = 50


@dataclass(frozen=True)
class AiFocus:
    section: Section
    signals: tuple[Signal, ...]  # one per place that names AI terms, all with weight 0


class AiFocusClassifier:
    def classify(self, snapshot: Snapshot) -> AiFocus:
        return self.classify_text(
            name=snapshot.repo.name,
            description=snapshot.description,
            topics=snapshot.topics,
            readme=snapshot.readme,
        )

    def classify_text(
        self, *, name: str, description: str, topics: Sequence[str], readme: str
    ) -> AiFocus:
        """The same rule for repos without Snapshot, such as HN and Lobsters projects."""
        signals = []
        for place, text in [
            ("Topics", " . ".join(topics)),
            ("Name", name),
            ("Beschreibung", description),
        ]:
            if found := AI_TERMS.distinct(text):
                signals.append(_signal(f"{place}: AI-Begriffe {quoted(found)}"))

        mentions = AI_TERMS.find(readme)
        if len(mentions) >= MIN_README_MENTIONS:
            terms = quoted(dict.fromkeys(mentions))
            signals.append(_signal(f"README: {len(mentions)}-mal AI-Begriffe ({terms})"))

        bare = _says_nothing(description, name) and not topics
        focused = (
            len(signals) >= MIN_PLACES
            or len(AI_TERMS.distinct(" . ".join(topics))) >= MIN_TOPIC_TERMS
            or len(mentions) >= MIN_README_MENTIONS_DOMINANT
            or (bare and len(mentions) >= MIN_README_MENTIONS_ALONE)
        )
        section = Section.AI if focused else Section.MAIN
        return AiFocus(section=section, signals=tuple(signals))


def _says_nothing(description: str, name: str) -> bool:
    """True for an empty description and for one that only repeats the repo's name."""
    words = set(re.findall(r"[^\W_]+", description.lower()))
    name_words = set(re.findall(r"[^\W_]+", name.lower()))
    name_words.add("".join(re.findall(r"[^\W_]+", name.lower())))
    return not (words - name_words - FILLER_WORDS)


def _signal(reason: str) -> Signal:
    return Signal(kind="ai_focus", weight=0, reason=reason)
