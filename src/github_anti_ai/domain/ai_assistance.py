"""Traces of code written with AI. They lower the score, they never exclude."""

import re

from github_anti_ai.domain.model import Commit, Signal, Snapshot

AI_COMMITS_MAX_PENALTY = 15.0
AI_COMMITS_MIN_SHARE = 0.10
AI_FILES_PENALTY = 3.0

# Names that people carry too ("Devin", "Jules", "Claude") only count in an unambiguous form.
_AI_NAME = re.compile(
    r"""^(
        claude(\ code)?(\ (opus|sonnet|haiku|fable|mythos)\b.*)?
      | (github\ )?copilot(\ .*)?
      | cursor(\ agent)?
      | codex(\ .*)?
      | .*\(codex\)
      | (openai\ )?(chat)?gpt\b.*
      | gemini(\ cli)?
      | aider(\ .*)?
      | devin\ ai
      | openhands(\ agent)?
      | windsurf
      | opencode
      | amp
    )$""",
    re.VERBOSE,
)
_AI_EMAIL_DOMAINS = frozenset(
    ["anthropic.com", "openai.com", "cursor.com", "aider.chat", "ampcode.com", "all-hands.dev"]
)
_AI_ACCOUNTS = frozenset(
    [
        "claude",
        "claude[bot]",
        "copilot",
        "copilot-swe-agent[bot]",
        "cursoragent",
        "cursor[bot]",
        "devin-ai-integration[bot]",
        "google-labs-jules[bot]",
        "capy-ai[bot]",
        "openhands-agent",
        "chatgpt-codex-connector[bot]",
        "opencode-agent[bot]",
        "windsurf-bot[bot]",
    ]
)
AI_INSTRUCTION_FILES = frozenset(
    [
        "claude.md",
        "agents.md",
        "gemini.md",
        ".claude",
        ".cursor",
        ".cursorrules",
        ".windsurfrules",
        ".clinerules",
        ".codex",
        ".agents",
        ".aider.conf.yml",
    ]
)

_CO_AUTHOR = re.compile(r"^\s*(?P<name>.*?)\s*(<(?P<email>[^>]*)>)?\s*$")
_GITHUB_NOREPLY = re.compile(r"^(\d+\+)?(?P<account>.+)@users\.noreply\.github\.com$")


class AiAssistanceDetector:
    def detect(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        found = [self._commits(snapshot), self._files(snapshot)]
        return tuple(signal for signal in found if signal)

    def _commits(self, snapshot: Snapshot) -> Signal | None:
        assisted = [c for c in snapshot.recent_commits if is_ai_assisted(c)]
        by_hand = [c for c in snapshot.recent_commits if not c.is_bot and not is_ai_assisted(c)]
        counted = len(assisted) + len(by_hand)  # ordinary bots are neither AI nor human
        if not counted:
            return None
        share = len(assisted) / counted
        if share < AI_COMMITS_MIN_SHARE:
            return None
        return Signal(
            "ai_commits",
            -AI_COMMITS_MAX_PENALTY * share,
            f"{share:.0%} der letzten Commits mit AI-Beteiligung ({len(assisted)} von {counted})",
        )

    def _files(self, snapshot: Snapshot) -> Signal | None:
        files = [name for name in snapshot.root_files if name.lower() in AI_INSTRUCTION_FILES]
        if not files:
            return None
        return Signal(
            "ai_files", -AI_FILES_PENALTY, "Anweisungsdateien für AI-Agenten: " + ", ".join(files)
        )


def is_ai_assisted(commit: Commit) -> bool:
    return _is_ai_account(commit.author) or any(is_ai_tool(c) for c in commit.co_authors)


def is_ai_tool(co_author: str) -> bool:
    """co_author is the value of a Co-authored-by line: 'Name <email>'."""
    match = _CO_AUTHOR.match(co_author)
    name = (match["name"] or "").lower()
    email = (match["email"] or "").lower()
    if _is_ai_account(name) or _AI_NAME.match(name):
        return True
    if noreply := _GITHUB_NOREPLY.match(email):
        return _is_ai_account(noreply["account"])
    return email.rpartition("@")[2] in _AI_EMAIL_DOMAINS


def _is_ai_account(account: str) -> bool:
    return account.lower() in _AI_ACCOUNTS
