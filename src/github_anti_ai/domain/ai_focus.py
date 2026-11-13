"""Decides whether a repo exists for the use of AI and therefore belongs to the AI section."""

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
        "langchain",
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
        "monitoring agent",
        "agent based",
    ],
)
MIN_PLACES = 2
MIN_README_MENTIONS = 5
# A repo without description and topics has only name and README left to show its purpose.
MIN_README_MENTIONS_ALONE = 10


@dataclass(frozen=True)
class AiFocus:
    section: Section
    signals: tuple[Signal, ...]  # one per place that names AI terms, all with weight 0


class AiFocusClassifier:
    def classify(self, snapshot: Snapshot) -> AiFocus:
        signals = []
        for place, text in [
            ("Topics", " . ".join(snapshot.topics)),
            ("Name", snapshot.repo.name),
            ("Beschreibung", snapshot.description),
        ]:
            if found := AI_TERMS.distinct(text):
                signals.append(_signal(f"{place}: AI-Begriffe {quoted(found)}"))

        mentions = AI_TERMS.find(snapshot.readme)
        if len(mentions) >= MIN_README_MENTIONS:
            terms = quoted(dict.fromkeys(mentions))
            signals.append(_signal(f"README: {len(mentions)}-mal AI-Begriffe ({terms})"))

        bare = not snapshot.description.strip() and not snapshot.topics
        focused = len(signals) >= MIN_PLACES or (bare and len(mentions) >= MIN_README_MENTIONS_ALONE)
        section = Section.AI if focused else Section.MAIN
        return AiFocus(section=section, signals=tuple(signals))


def _signal(reason: str) -> Signal:
    return Signal(kind="ai_focus", weight=0, reason=reason)
