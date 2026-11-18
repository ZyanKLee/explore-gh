"""Does a repo found on a story's website belong to the story? See docs/community.md."""

import re
from urllib.parse import urlsplit

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
# Repos that hold the code of a website, never the project of a story.
WEBSITE_REPO_SUFFIXES = (".github.io", ".gitlab.io", ".codeberg.page")

_WORD = re.compile(r"[a-z0-9]+")


def shared_words(title: str, page_url: str, repository_url: str) -> set[str]:
    """The words a repo shares with the story: its title, host name and path.

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


def relates_to_story(title: str, page_url: str, repository_url: str) -> bool:
    return bool(shared_words(title, page_url, repository_url))


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
