"""Where the stories of the weekly forums list come from: Lobsters, Lemmy and Mastodon.

Only the first post counts: its link and the links in its text, never replies.
See docs/community.md, "Wochenliste Foren".
"""

import html
import logging
import re
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime

import httpx

from explore_gh.application.ports import SourceUnavailable, StorySource
from explore_gh.domain.community import (
    FORUMS_MAX_STORY_AGE,
    FORUMS_MIN_STORY_AGE,
    LOBSTERS,
    LOBSTERS_ORIGIN,
    Story,
    lemmy_origin,
    mastodon_origin,
)

LOBSTERS_URL = "https://lobste.rs"
LEMMY_URL = "https://programming.dev"  # sees the communities of other instances, too
MASTODON_URL = "https://fosstodon.org"
LOBSTERS_MAX_PAGES = 12  # about 25 stories a day, 25 a page
LOBSTERS_PAUSE_SECONDS = 3.0  # Lobsters answers 429 after a few fast requests
LEMMY_MAX_PAGES = 5
LEMMY_PAGE_SIZE = 50
MASTODON_MAX_PAGES = 10
MASTODON_PAGE_SIZE = 40
MAX_TITLE_LENGTH = 120

_URL = re.compile(r"https?://[^\s<>\"'()\[\]]+")
_TAG = re.compile(r"<[^>]+>")

log = logging.getLogger(__name__)


def links_in(text: str | None) -> tuple[str, ...]:
    """The web addresses in a text, HTML or Markdown, each once, in order."""
    found = (match.rstrip(".,;:!?") for match in _URL.findall(html.unescape(text or "")))
    return tuple(dict.fromkeys(found))


def plain_text(content: str) -> str:
    """HTML as plain text, paragraphs and line breaks as spaces."""
    text = _TAG.sub(" ", re.sub(r"<br\s*/?>|</p>", " ", content))
    return " ".join(html.unescape(text).split())


def _is_web_url(value) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _too_old(created_at: datetime, now: datetime) -> bool:
    return created_at < now - FORUMS_MAX_STORY_AGE


def _get(client: httpx.Client, name: str, path: str, params: dict | None = None):
    try:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise SourceUnavailable(f"{name} {path}: {error}") from error


def _utc(value: str) -> datetime:
    """Lemmy writes UTC, older versions without a zone."""
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class LobstersNewest:
    def __init__(self, client: httpx.Client, sleep: Callable[[float], None]):
        """`client` has LOBSTERS_URL as its base. `sleep` waits between pages."""
        self._client = client
        self._sleep = sleep

    def discover(self, now: datetime, limit: int | None = None) -> list[Story]:
        """The pages of "newest" until the stories are older than 8 days."""
        stories: dict[str, Story] = {}
        for page in range(1, LOBSTERS_MAX_PAGES + 1):
            if page > 1:
                self._sleep(LOBSTERS_PAUSE_SECONDS)
            records = _get(self._client, "Lobsters", f"/newest/page/{page}.json")
            if not isinstance(records, list) or not records:
                break
            oldest = None
            for record in records:
                try:
                    story = self._story(record)
                except (KeyError, TypeError, ValueError) as error:
                    raise SourceUnavailable(f"Lobsters: ungültiger Treffer: {error}") from error
                oldest = story.created_at
                if story.url or story.links:
                    stories.setdefault(story.id, story)
            if oldest is None or _too_old(oldest, now):
                break
        found = list(stories.values())
        return found if limit is None else found[:limit]

    def _story(self, record: dict) -> Story:
        story_id = str(record["short_id"])
        return Story(
            id=story_id,
            title=record["title"],
            url=record["url"] if _is_web_url(record.get("url")) else "",
            discussion_url=record.get("short_id_url") or LOBSTERS.discussion_url(story_id),
            points=int(record.get("score") or 0),
            comments=int(record.get("comment_count") or 0),
            created_at=datetime.fromisoformat(record["created_at"]),
            origin=LOBSTERS_ORIGIN,
            links=links_in(record.get("description")),
        )


class LemmyCommunities:
    def __init__(self, client: httpx.Client, communities: Iterable[str]):
        """`client` has LEMMY_URL as its base. `communities`: `rust`, `linux@lemmy.ml`."""
        self._client = client
        self._communities = tuple(communities)

    def discover(self, now: datetime, limit: int | None = None) -> list[Story]:
        stories: list[Story] = []
        for community in self._communities:
            stories += self._community(community, now)
        return stories if limit is None else stories[:limit]

    def _community(self, community: str, now: datetime) -> list[Story]:
        """The newest posts of one community, page by page, until older than 8 days."""
        stories: dict[str, Story] = {}
        for page in range(1, LEMMY_MAX_PAGES + 1):
            params = {"community_name": community, "sort": "New", "limit": LEMMY_PAGE_SIZE,
                      "page": page}  # fmt: skip
            posts = _get(self._client, "Lemmy", "/api/v3/post/list", params).get("posts") or []
            if not posts:
                break
            oldest = None
            for record in posts:
                try:
                    story = self._story(record, community)
                except (KeyError, TypeError, ValueError) as error:
                    raise SourceUnavailable(f"Lemmy: ungültiger Beitrag: {error}") from error
                oldest = story.created_at
                post = record["post"]
                if post.get("deleted") or post.get("removed"):
                    continue
                if story.url or story.links:
                    stories.setdefault(story.id, story)
            if oldest is None or _too_old(oldest, now):
                break
        return list(stories.values())

    def _story(self, record: dict, community: str) -> Story:
        post, counts = record["post"], record["counts"]
        return Story(
            id=str(post["id"]),
            title=post["name"],
            url=post["url"] if _is_web_url(post.get("url")) else "",
            discussion_url=post["ap_id"],
            points=int(counts.get("score") or 0),
            comments=int(counts.get("comments") or 0),
            created_at=_utc(post["published"]),
            origin=lemmy_origin(community),
            links=links_in(post.get("body")),
        )


class MastodonTags:
    def __init__(self, client: httpx.Client, tags: Iterable[str]):
        """`client` has MASTODON_URL as its base. `tags` without "#"."""
        self._client = client
        self._tags = tuple(tags)

    def discover(self, now: datetime, limit: int | None = None) -> list[Story]:
        stories: list[Story] = []
        for tag in self._tags:
            stories += self._tag(tag, now)
        return stories if limit is None else stories[:limit]

    def _tag(self, tag: str, now: datetime) -> list[Story]:
        """The toots of one hashtag, page by page, until older than 8 days.

        Replies and boosts are left out: only the first post counts.
        """
        stories: dict[str, Story] = {}
        max_id = None
        for _ in range(MASTODON_MAX_PAGES):
            params = {"limit": MASTODON_PAGE_SIZE} | ({"max_id": max_id} if max_id else {})
            toots = _get(self._client, "Mastodon", f"/api/v1/timelines/tag/{tag}", params)
            if not isinstance(toots, list) or not toots:
                break
            oldest = None
            for toot in toots:
                try:
                    story = self._story(toot, tag)
                    max_id = str(toot["id"])
                except (KeyError, TypeError, ValueError) as error:
                    raise SourceUnavailable(f"Mastodon: ungültiger Toot: {error}") from error
                oldest = story.created_at
                if toot.get("in_reply_to_id") or toot.get("reblog"):
                    continue
                if story.links:
                    stories.setdefault(story.id, story)
            if oldest is None or _too_old(oldest, now):
                break
        return list(stories.values())

    def _story(self, toot: dict, tag: str) -> Story:
        content = toot.get("content") or ""
        title = " ".join(_URL.sub(" ", plain_text(content)).split())
        return Story(
            id=str(toot["url"]),  # the same toot under several tags is one story
            title=title[:MAX_TITLE_LENGTH],
            url="",
            discussion_url=toot["url"],
            points=int(toot.get("favourites_count") or 0) + int(toot.get("reblogs_count") or 0),
            comments=int(toot.get("replies_count") or 0),
            created_at=datetime.fromisoformat(toot["created_at"]),
            origin=mastodon_origin(tag),
            links=tuple(link for link in links_in(content) if "/tags/" not in link),
        )


class ForumStories:
    """All sources of the forums list together: the stories that are 1 to 8 days old."""

    def __init__(self, sources: Sequence[StorySource]):
        self._sources = sources

    def discover(self, now: datetime, limit: int | None = None) -> list[Story]:
        stories: dict[str, Story] = {}
        failures = []
        for source in self._sources:
            try:
                found = source.discover(now)
            except SourceUnavailable as error:
                log.warning("Foren: Quelle fällt aus: %s", error)
                failures.append(str(error))
                continue
            for story in found:
                age = now - story.created_at
                if FORUMS_MIN_STORY_AGE <= age <= FORUMS_MAX_STORY_AGE:
                    stories.setdefault(story.discussion_url, story)
        if failures and len(failures) == len(self._sources):
            raise SourceUnavailable("Foren: alle Quellen fallen aus: " + "; ".join(failures))
        found = list(stories.values())
        return found if limit is None else found[:limit]
