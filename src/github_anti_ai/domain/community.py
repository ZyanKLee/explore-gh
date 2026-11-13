"""Rules shared by the community project lists (HN, Lobsters). See docs/ausgabe.md."""

import re
from collections import Counter
from collections.abc import Callable, Collection, Iterable
from datetime import date
from typing import Protocol, TypeVar
from urllib.parse import urlsplit

from github_anti_ai.domain.edition import COOLDOWN_DAYS, MAX_PER_LANGUAGE, MAX_PER_OWNER

PROJECTS_PER_EDITION = 20

# Bezug zur Story, see docs/datensammlung.md
MIN_WORD_LENGTH = 3
# A repo name like `yk` counts in full, although it is shorter than a word.
MIN_FULL_NAME_LENGTH = 2
GENERIC_WORDS = frozenset({
    "www", "blog", "blogs", "news", "docs", "doc", "wiki", "home", "site", "web", "page",
    "pages", "post", "posts", "com", "org", "net", "dev", "app", "html", "htm",
    "github", "gitlab", "codeberg", "sourcehut", "gitea", "forgejo",
    "the", "and", "for", "with", "from", "your", "you", "how", "why", "what", "new",
    "open", "source", "code", "project", "projects", "using", "use",
})  # fmt: skip
WEBSITE_REPO_SUFFIXES = (".github.io", ".gitlab.io", ".codeberg.page")
_WORD = re.compile(r"[a-z0-9]+")


class CommunityProject(Protocol):
    """What the shared rules need to know about an HN or Lobsters project."""

    @property
    def repository_url(self) -> str: ...
    @property
    def is_open_source(self) -> bool: ...
    @property
    def has_code(self) -> bool: ...
    @property
    def is_fork(self) -> bool: ...
    @property
    def is_archived(self) -> bool: ...
    @property
    def language(self) -> str | None: ...


Project = TypeVar("Project", bound=CommunityProject)


class CommunityEdition(Protocol):
    """A past HN or Lobsters edition, as far as the cooldown looks at it."""

    @property
    def day(self) -> date: ...
    @property
    def projects(self) -> tuple[CommunityProject, ...]: ...


class CommunityCurator:
    def select(
        self,
        candidates: Iterable[Project],
        rank: Callable[[Project], tuple],
        cooled_down: Collection[str] = frozenset(),
    ) -> tuple[Project, ...]:
        """The projects of one community edition. `rank` sorts the best project first.

        `cooled_down` holds the repository keys under cooldown, see `recently_shown`.
        """
        best: dict[str, Project] = {}
        for candidate in candidates:
            key = repository_key(candidate.repository_url)
            if not _eligible(candidate) or key in cooled_down:
                continue
            if key not in best or rank(candidate) < rank(best[key]):
                best[key] = candidate
        return _varied(sorted(best.values(), key=rank))


def check_community_edition(projects: Iterable[CommunityProject], platform: str) -> None:
    """The rules every HN or Lobsters edition keeps; `platform` names it in the message."""
    projects = list(projects)
    if len(projects) > PROJECTS_PER_EDITION:
        raise ValueError(f"{platform}-Ausgabe: mehr als {PROJECTS_PER_EDITION} Projekte")
    keys = [repository_key(project.repository_url) for project in projects]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Ein Repo steht mehrfach in der {platform}-Ausgabe")
    languages = Counter(project.language for project in projects)
    if languages and max(languages.values()) > MAX_PER_LANGUAGE:
        raise ValueError(
            f"{platform}-Ausgabe: mehr als {MAX_PER_LANGUAGE} Projekte einer Sprache"
        )
    owners = Counter(owner_key(project.repository_url) for project in projects)
    if owners and max(owners.values()) > MAX_PER_OWNER:
        raise ValueError(f"{platform}-Ausgabe: mehr als {MAX_PER_OWNER} Repos eines Besitzers")


def owner_key(url: str) -> str:
    """Forge and first part of the path: `github.com/alice` is not `codeberg.org/alice`."""
    parsed = urlsplit(url)
    owner = next((part for part in parsed.path.split("/") if part), "")
    return f"{parsed.hostname or ''}/{owner}".casefold()


def _varied(ranked: list[Project]) -> tuple[Project, ...]:
    """In ranking order, skipping a project whose language or owner is already full."""
    selected: list[Project] = []
    per_language: Counter[str | None] = Counter()
    per_owner: Counter[str] = Counter()
    for project in ranked:
        owner = owner_key(project.repository_url)
        if per_language[project.language] == MAX_PER_LANGUAGE or per_owner[owner] == MAX_PER_OWNER:
            continue
        per_language[project.language] += 1
        per_owner[owner] += 1
        selected.append(project)
        if len(selected) == PROJECTS_PER_EDITION:
            break
    return tuple(selected)


def recently_shown(day: date, past_editions: Iterable[CommunityEdition]) -> set[str]:
    """Repository keys under cooldown on `day`: shown on day D, blocked through D + 29."""
    return {
        repository_key(project.repository_url)
        for edition in past_editions
        if 0 <= (day - edition.day).days < COOLDOWN_DAYS
        for project in edition.projects
    }


def repository_key(url: str) -> str:
    """Two repository addresses with the same key name the same repo."""
    return url.rstrip("/").casefold()


def relates_to_story(title: str, page_url: str, repository_url: str) -> bool:
    """Whether a repo found on the story's website shares a word with the story."""
    return bool(shared_words(title, page_url, repository_url))


def shared_words(title: str, page_url: str, repository_url: str) -> set[str]:
    """The words a repo found on the story's website has in common with the story.

    The more words, the closer the repo is to the story. A website repo shares none.
    """
    parts = [part for part in urlsplit(repository_url).path.split("/") if part]
    if len(parts) < 2:
        return set()
    owner, name = parts[0], parts[-1]
    if name.casefold().endswith(WEBSITE_REPO_SUFFIXES):
        return set()
    page = urlsplit(page_url)
    host = page.hostname or ""
    repo_words = _meaningful(_words(owner) | _words(name) | _joined(owner) | _joined(name))
    full_name = "".join(_WORD.findall(name.casefold()))
    if len(full_name) >= MIN_FULL_NAME_LENGTH and _ordinary(full_name):
        repo_words.add(full_name)
    story_words = _words(title) | _words(host) | _joined(host) | _words(page.path)
    return repo_words & story_words


def _eligible(project: CommunityProject) -> bool:
    return (
        project.is_open_source
        and project.has_code
        and not project.is_fork
        and not project.is_archived
    )


def _words(text: str) -> set[str]:
    """`rust-lang` gives `rust` and `lang`."""
    return set(_WORD.findall(text.casefold()))


def _joined(text: str) -> set[str]:
    """Each dotted part without separators: `blog.rust-lang.org` gives `rustlang` and more."""
    return {"".join(_WORD.findall(part)) for part in text.casefold().split(".")}


def _meaningful(words: set[str]) -> set[str]:
    return {word for word in words if len(word) >= MIN_WORD_LENGTH and _ordinary(word)}


def _ordinary(word: str) -> bool:
    return not word.isdigit() and word not in GENERIC_WORDS
