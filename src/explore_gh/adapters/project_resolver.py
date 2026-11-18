"""Follows a story's link to a public repo on GitHub, GitLab or a Gitea/Forgejo forge.

The same for HN and Lobsters. See docs/community.md, "Vom Link zum Repo".
"""

import ipaddress
import json
import socket
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx

from explore_gh.application.ports import SourceUnavailable
from explore_gh.domain.community import UNRECOGNIZED_LICENSE, CommunityProject, Story
from explore_gh.domain.story_relation import relates_to_story, shared_words

MAX_PAGE_BYTES = 1_000_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10
# Forges whose failures mean an outage. Any other host is only probed for a forge API,
# and an error there just means it is no forge.
KNOWN_FORGE_HOSTS = frozenset({"github.com", "gitlab.com", "codeberg.org"})
# Hosts whose repos have exactly two parts in their path: owner/name
TWO_PART_HOSTS = frozenset({"github.com", "codeberg.org"})
SOURCE_WORDS = ("source", "repository", "github", "gitlab", "codeberg", "gitea", "forgejo")
LICENSE_ALIASES = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "other": UNRECOGNIZED_LICENSE,  # GitLab: a license file, but not identified
}
_REDIRECTS = {301, 302, 303, 307, 308}
# Links in the text of a post are followed only to hosts that look like a forge
FORGE_HOST_WORDS = ("git", "forge", "codeberg")


def _looks_like_forge(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in KNOWN_FORGE_HOSTS or any(word in host for word in FORGE_HOST_WORDS)


@dataclass(frozen=True)
class _Readme:
    """Where the README of a repo is, and whether a 404 there proves it has none."""

    url: str
    client: httpx.Client | None = None
    accept: str = "text/plain"
    missing_on_404: bool = True


@dataclass(frozen=True)
class _ForgeRepo:
    url: str
    description: str
    language: str | None
    license_id: str | None
    is_fork: bool
    is_archived: bool
    has_code: bool
    topics: tuple[str, ...]
    readme: _Readme | None  # None: the forge says there is none


class ProjectResolver:
    def __init__(
        self,
        client: httpx.Client,
        *,
        github_client: httpx.Client | None = None,
        is_public_host: Callable[[str], bool] | None = None,
    ):
        """`github_client` carries the token. `is_public_host` replaces the DNS lookup in tests."""
        self._client = client
        self._github_client = github_client or client
        self._is_public_host = is_public_host or _resolves_to_public_addresses

    def resolve(self, story: Story) -> CommunityProject | None:
        """The story's link to a repo, else a related repo on the linked website, else a
        related repo among the links in the text of the first post."""
        repo = self._forge_repo(story.url) if story.url else None
        linked_directly = repo is not None
        if repo is None and story.url:
            html = self._html(story.url)
            if html is not None:
                repo = self._closest_repo(story.title, story.url, repository_links(html, story.url))
        found_in_post = False
        if repo is None:
            forge_links = list(
                dict.fromkeys(
                    repository_root(link) for link in story.links if _looks_like_forge(link)
                )
            )
            repo = self._closest_repo(story.title, story.url, forge_links)
            found_in_post = repo is not None
        if repo is None:
            return None
        return CommunityProject(
            story=story,
            repository_url=repo.url,
            project_url=story.url or repo.url,
            description=repo.description,
            language=repo.language,
            license_id=repo.license_id,
            is_fork=repo.is_fork,
            is_archived=repo.is_archived,
            has_code=repo.has_code,
            topics=repo.topics,
            linked_directly=linked_directly,
            found_in_post=found_in_post,
            readme=self._readme(repo.readme),
        )

    def _closest_repo(self, title: str, page_url: str, links) -> _ForgeRepo | None:
        """The linked repo sharing the most words with the story; on a tie the first one."""
        best, best_words = None, 0
        for link in links:
            if not relates_to_story(title, page_url, link):
                continue  # spares a request for the blog theme in the footer
            repo = self._forge_repo(link)
            if repo is None:
                continue
            words = len(shared_words(title, page_url, repo.url))
            if words > best_words:
                best, best_words = repo, words
        return best

    def _forge_repo(self, url: str) -> _ForgeRepo | None:
        if not self._is_safe(url):
            return None
        parsed = urlsplit(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        host = (parsed.hostname or "").lower()
        path = "/".join(parts[:2] if host in TWO_PART_HOSTS else parts)
        if host == "github.com":
            return self._github(path)
        base = f"{parsed.scheme}://{parsed.netloc}"
        probe = host not in KNOWN_FORGE_HOSTS
        return self._gitlab(base, path, probe) or self._gitea(base, path, probe)

    def _github(self, path: str) -> _ForgeRepo | None:
        data = self._json(f"https://api.github.com/repos/{path}", client=self._github_client)
        if data is None:
            return None
        full_name = data.get("full_name", path)
        return _ForgeRepo(
            url=f"https://github.com/{full_name}",
            description=str(data.get("description") or ""),
            language=_text(data.get("language")),
            license_id=license_id((data.get("license") or {}).get("spdx_id")),
            is_fork=bool(data.get("fork")),
            is_archived=bool(data.get("archived")),
            has_code=bool(data.get("language")) and int(data.get("size") or 0) > 0,
            topics=_topics(data.get("topics")),
            readme=_Readme(  # GitHub finds a README of any name
                f"https://api.github.com/repos/{full_name}/readme",
                client=self._github_client,
                accept="application/vnd.github.raw+json",
            ),
        )

    def _gitlab(self, base: str, path: str, probe: bool) -> _ForgeRepo | None:
        data = self._json(f"{base}/api/v4/projects/{quote(path, safe='')}", probe=probe)
        if data is None or "web_url" not in data:
            return None
        languages = None
        if data.get("id") is not None:
            languages = self._json(f"{base}/api/v4/projects/{data['id']}/languages", probe=probe)
        language = max(languages, key=languages.get) if languages else None
        readme_url = data.get("readme_url")
        return _ForgeRepo(
            url=str(data["web_url"]).rstrip("/"),
            description=str(data.get("description") or ""),
            language=_text(language),
            license_id=license_id((data.get("license") or {}).get("key")),
            is_fork=bool(data.get("forked_from_project")),
            is_archived=bool(data.get("archived")),
            has_code=bool(language) and not data.get("empty_repo", False),
            topics=_topics(data.get("topics")),
            readme=(
                _Readme(readme_url.replace("/-/blob/", "/-/raw/", 1))
                if isinstance(readme_url, str)
                else None
            ),
        )

    def _gitea(self, base: str, path: str, probe: bool) -> _ForgeRepo | None:
        data = self._json(f"{base}/api/v1/repos/{path}", probe=probe)
        if data is None or "html_url" not in data:
            return None
        licenses = data.get("license") or []
        return _ForgeRepo(
            url=str(data["html_url"]).rstrip("/"),
            description=str(data.get("description") or ""),
            language=_text(data.get("language")),
            license_id=license_id(
                licenses[0] if isinstance(licenses, list) and licenses else licenses
            ),
            is_fork=bool(data.get("fork")),
            is_archived=bool(data.get("archived")),
            has_code=bool(data.get("language")) and int(data.get("size") or 0) > 0,
            topics=_topics(data.get("topics")),
            # only README.md is asked for: a README of another name may exist
            readme=_Readme(f"{base}/api/v1/repos/{path}/raw/README.md", missing_on_404=False),
        )

    def _readme(self, readme: _Readme | None) -> str | None:
        """The README, "" if the repo has none, None if that is not known."""
        if readme is None:
            return ""
        try:
            response = self._get(readme.url, client=readme.client, accept=readme.accept)
        except SourceUnavailable:
            return None
        if response is not None and response.status_code == 404 and readme.missing_on_404:
            return ""
        if response is None or response.status_code != 200 or _too_big(response):
            return None
        return response.text

    def _html(self, url: str) -> str | None:
        response = self._get(url)
        if response is None or response.status_code != 200 or _too_big(response):
            return None
        content_type = response.headers.get("content-type", "")
        return response.text if "html" in content_type.lower() else None

    def _json(
        self, url: str, *, client: httpx.Client | None = None, probe: bool = False
    ) -> dict | None:
        """With `probe`, any failure only means the host has no forge API."""
        try:
            response = self._get(url, client=client)
        except SourceUnavailable:
            if probe:
                return None
            raise
        if response is None or response.status_code == 404:
            return None
        if probe and response.status_code != 200:
            return None
        if response.status_code >= 500 or response.status_code in (403, 429):
            raise SourceUnavailable(f"HTTP {response.status_code} bei {url}")
        if response.status_code != 200 or _too_big(response):
            return None
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _get(
        self,
        url: str,
        *,
        client: httpx.Client | None = None,
        accept: str = "application/json, text/html;q=0.9",
    ) -> httpx.Response | None:
        """Follows redirects by hand: every address on the way must be public."""
        for _ in range(MAX_REDIRECTS + 1):
            if not self._is_safe(url):
                return None
            try:
                response = (client or self._client).get(
                    url, headers={"Accept": accept}, follow_redirects=False, timeout=TIMEOUT_SECONDS
                )
            except httpx.HTTPError as error:
                raise SourceUnavailable(str(error)) from error
            if response.status_code not in _REDIRECTS:
                return response
            location = response.headers.get("location")
            if not location:
                return None
            url = urljoin(url, location)
        return None

    def _is_safe(self, url: str) -> bool:
        """A web address on the public internet: no local network, no odd ports."""
        if not _is_web_url(url):
            return False
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError:
            return False
        if port not in (None, 80, 443):
            return False
        host = parsed.hostname or ""
        if host == "localhost" or host.endswith((".localhost", ".local")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return self._is_public_host(host)


class _Links(HTMLParser):
    """Collects every link of a page: address, rel and text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, str]] = []
        self._anchor: tuple[str, str] | None = None
        self._text = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self._anchor = (attributes["href"], attributes.get("rel") or "")
            self._text = ""

    def handle_data(self, data):
        if self._anchor:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor:
            href, rel = self._anchor
            self.links.append((href, rel, self._text.strip().lower()))
            self._anchor = None


def repository_links(html: str, page_url: str) -> list[str]:
    """Links of a page that may lead to a repo, as repo roots, each once, in page order."""
    parser = _Links()
    parser.feed(html)
    found = []
    for href, rel, text in parser.links:
        target = urljoin(page_url, href)
        if not _is_web_url(target):
            continue
        context = f"{text} {urlsplit(target).hostname or ''}".lower()
        if "coderepository" in rel.lower().split() or any(word in context for word in SOURCE_WORDS):
            found.append(repository_root(target))
    return list(dict.fromkeys(found))


def repository_root(url: str) -> str:
    """`github.com/a/tool/blob/main/x` and `gitlab.example/a/tool/-/tree/main` name `a/tool`."""
    parsed = urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    if (parsed.hostname or "").lower() in TWO_PART_HOSTS:
        parts = parts[:2]
    for marker in ("-", "src", "tree", "blob"):
        if marker in parts:
            parts = parts[: parts.index(marker)]
    path = "/".join(parts).removesuffix(".git")
    return f"{parsed.scheme}://{parsed.netloc}/{path}".rstrip("/")


def license_id(value) -> str | None:
    """The license as an SPDX id, whatever form the forge gives it in."""
    if isinstance(value, dict):
        value = value.get("spdx_id") or value.get("key")
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return LICENSE_ALIASES.get(value.lower(), value)


def _text(value) -> str | None:
    return value if isinstance(value, str) else None


def _topics(value) -> tuple[str, ...]:
    return tuple(str(topic) for topic in value) if isinstance(value, list) else ()


def _too_big(response: httpx.Response) -> bool:
    return len(response.content) > MAX_PAGE_BYTES


def _is_web_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username


def _resolves_to_public_addresses(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
