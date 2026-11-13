"""Resolve HN links to public repositories and inspect their OSS metadata."""

import ipaddress
import json
import socket
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx

from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.community import relates_to_story, shared_words
from github_anti_ai.domain.hn import HnProjectCandidate, HnStory
from github_anti_ai.domain.opensource import UNRECOGNIZED_LICENSE

MAX_PAGE_BYTES = 1_000_000
_LICENSE_ALIASES = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
    "other": UNRECOGNIZED_LICENSE,  # GitLab: license file found, but not identified
}
# Forges whose failures mean an outage. Any other website is only probed for a forge API,
# and an error there just means it is not a forge.
KNOWN_FORGE_HOSTS = frozenset({"github.com", "gitlab.com", "codeberg.org"})


class HnProjectResolver:
    def __init__(
        self,
        client: httpx.Client,
        *,
        github_client: httpx.Client | None = None,
        resolve_host: Callable[[str], bool] | None = None,
    ):
        self._client = client
        self._github_client = github_client or client
        self._resolve_host = resolve_host or _is_public_host

    def resolve(self, story: HnStory) -> HnProjectCandidate | None:
        project_url = story.url
        repository_url, metadata = self._inspect_repository(project_url)
        if metadata is None:
            html = self._get_html(project_url)
            if html is None:
                return None
            repository_url, metadata = self._closest_repository(story.title, project_url, html)
        if metadata is None or repository_url is None:
            return None

        license_id = _license_id(metadata.get("license"))
        return HnProjectCandidate(
            story=story,
            repository_url=repository_url,
            project_url=project_url,
            description=str(metadata.get("description") or ""),
            language=metadata.get("language") if isinstance(metadata.get("language"), str) else None,
            license_id=license_id,
            is_fork=bool(metadata.get("fork")),
            is_archived=bool(metadata.get("archived")),
            has_code=bool(metadata.get("has_code")),
        )

    def _closest_repository(
        self, title: str, page_url: str, html: str
    ) -> tuple[str | None, dict | None]:
        """The linked repo sharing the most words with the story; on a tie the first one."""
        best_words, repository_url, metadata = 0, None, None
        for link in _repository_links(html, page_url):
            if not relates_to_story(title, page_url, link):
                continue  # spares a request for the blog theme in the footer
            url, found = self._inspect_repository(link)
            if found is None or url is None:
                continue
            words = len(shared_words(title, page_url, url))
            if words > best_words:
                best_words, repository_url, metadata = words, url, found
        return repository_url, metadata

    def _inspect_repository(self, url: str) -> tuple[str | None, dict | None]:
        if not _safe_public_url(url, self._resolve_host):
            return None, None
        parsed = urlsplit(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None, None
        host = (parsed.hostname or "").lower()
        path = "/".join(parts[:2]) if host in {"github.com", "codeberg.org"} else "/".join(parts)

        if host == "github.com":
            metadata = self._json(
                f"https://api.github.com/repos/{path}", client=self._github_client
            )
            if metadata is None:
                return None, None
            repo = metadata.get("full_name", path)
            return f"https://github.com/{repo}", {
                "description": metadata.get("description"),
                "language": metadata.get("language"),
                "license": (metadata.get("license") or {}).get("spdx_id"),
                "fork": metadata.get("fork"),
                "archived": metadata.get("archived"),
                "has_code": bool(metadata.get("language")) and int(metadata.get("size") or 0) > 0,
            }

        probe = host not in KNOWN_FORGE_HOSTS
        gitlab = self._json(
            f"{parsed.scheme}://{parsed.netloc}/api/v4/projects/{quote(path, safe='')}",
            probe=probe,
        )
        if gitlab is not None and "web_url" in gitlab:
            languages = self._json(
                f"{parsed.scheme}://{parsed.netloc}/api/v4/projects/{gitlab['id']}/languages",
                probe=probe,
            ) if gitlab.get("id") is not None else None
            language = max(languages, key=languages.get) if languages else None
            return str(gitlab["web_url"]).rstrip("/"), {
                "description": gitlab.get("description"),
                "language": language,
                "license": (gitlab.get("license") or {}).get("key"),
                "fork": bool(gitlab.get("forked_from_project")),
                "archived": gitlab.get("archived"),
                "has_code": bool(language) and not gitlab.get("empty_repo", False),
            }

        gitea = self._json(f"{parsed.scheme}://{parsed.netloc}/api/v1/repos/{path}", probe=probe)
        if gitea is not None and "html_url" in gitea:
            licenses = gitea.get("license") or []
            return str(gitea["html_url"]).rstrip("/"), {
                "description": gitea.get("description"),
                "language": gitea.get("language"),
                "license": licenses[0] if isinstance(licenses, list) and licenses else licenses,
                "fork": gitea.get("fork"),
                "archived": gitea.get("archived"),
                "has_code": bool(gitea.get("language")) and int(gitea.get("size") or 0) > 0,
            }
        return None, None

    def _get_html(self, url: str) -> str | None:
        response = self._request(url)
        if response is None or response.status_code != 200:
            return None
        if len(response.content) > MAX_PAGE_BYTES:
            return None
        content_type = response.headers.get("content-type", "")
        return response.text if "html" in content_type.lower() else None

    def _json(
        self, url: str, *, client: httpx.Client | None = None, probe: bool = False
    ) -> dict | None:
        """With `probe`, any failure only means the website has no forge API."""
        try:
            response = self._request(url, client=client)
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
        if response.status_code != 200 or len(response.content) > MAX_PAGE_BYTES:
            return None
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _request(
        self, url: str, *, client: httpx.Client | None = None
    ) -> httpx.Response | None:
        for _ in range(4):
            if not _safe_public_url(url, self._resolve_host):
                return None
            try:
                response = (client or self._client).get(
                    url,
                    headers={"Accept": "application/json, text/html;q=0.9"},
                    follow_redirects=False,
                    timeout=10,
                )
            except httpx.HTTPError as error:
                raise SourceUnavailable(str(error)) from error
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                return None
            url = urljoin(url, location)
        return None


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str, str]] = []
        self._anchor: tuple[str, str] | None = None
        self._text = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self._anchor = (attributes["href"], attributes.get("rel", ""))
            self._text = ""

    def handle_data(self, data):
        if self._anchor:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor:
            href, rel = self._anchor
            self.items.append((href, rel, self._text.strip().lower()))
            self._anchor = None


def _repository_links(html: str, page_url: str) -> list[str]:
    parser = _Links()
    parser.feed(html)
    candidates = []
    for href, rel, text in parser.items:
        target = urljoin(page_url, href)
        if not _is_web_url(target):
            continue
        if "coderepository" in rel.lower().split() or any(
            word in f"{text} {urlsplit(target).hostname or ''}".lower()
            for word in ("source", "repository", "github", "gitlab", "codeberg", "gitea", "forgejo")
        ):
            candidates.append(_repository_root(target))
    return list(dict.fromkeys(candidates))


def _repository_root(url: str) -> str:
    """`github.com/a/tool/blob/main/x` and `gitlab.example/a/tool/-/tree/main` name `a/tool`."""
    parsed = urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    if (parsed.hostname or "").lower() in {"github.com", "codeberg.org"}:
        parts = parts[:2]
    for marker in ("-", "src", "tree", "blob"):
        if marker in parts:
            parts = parts[: parts.index(marker)]
    path = "/".join(parts).removesuffix(".git")
    return f"{parsed.scheme}://{parsed.netloc}/{path}".rstrip("/")


def _license_id(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("spdx_id") or value.get("key")
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    return _LICENSE_ALIASES.get(stripped.lower(), stripped)


def _is_web_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username


def _safe_public_url(url: str, resolve_host: Callable[[str], bool]) -> bool:
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
        address = ipaddress.ip_address(host)
    except ValueError:
        return resolve_host(host)
    return address.is_global


def _is_public_host(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)