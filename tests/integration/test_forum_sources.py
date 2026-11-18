"""The story sources of the forums list: Lobsters, Lemmy and Mastodon, and their bundle."""

from datetime import timedelta

import httpx
import pytest
from builders import NOW, make_story
from http_fakes import FakeWeb, Sleeps

from explore_gh.adapters.forum_sources import (
    LEMMY_URL,
    LOBSTERS_URL,
    MASTODON_URL,
    ForumStories,
    LemmyCommunities,
    LobstersNewest,
    MastodonTags,
)
from explore_gh.application.ports import SourceUnavailable
from explore_gh.domain.community import (
    FORUMS,
    LOBSTERS_ORIGIN,
    lemmy_origin,
    mastodon_origin,
)

DAYS = timedelta(days=1)


# --- Lobsters ---


def lobsters_record(id, age=3 * DAYS, url="https://example.org/tool", description=""):
    return {
        "short_id": id, "short_id_url": f"https://lobste.rs/s/{id}", "title": f"Story {id}",
        "url": url, "description": description, "score": 20, "comment_count": 4,
        "created_at": (NOW - age).isoformat(),
    }  # fmt: skip


def lobsters(pages, sleeps=None):
    routes = {
        f"lobste.rs/newest/page/{n}.json": httpx.Response(200, json=page)
        for n, page in enumerate(pages, 1)
    }
    web = FakeWeb(routes)
    with web.client(base_url=LOBSTERS_URL) as client:
        source = LobstersNewest(client, sleep=sleeps if sleeps is not None else Sleeps())
        return source.discover(NOW), web


def test_lobsters_pauses_between_pages_because_it_refuses_fast_requests():
    sleeps = Sleeps()

    lobsters([[lobsters_record("a")], [lobsters_record("b", 9 * DAYS)]], sleeps)

    assert sleeps == [3.0]


def test_lobsters_reads_newest_until_the_stories_are_older_than_8_days():
    stories, web = lobsters(
        [
            [lobsters_record("a", 2 * DAYS)],
            [lobsters_record("b", 7 * DAYS), lobsters_record("c", 9 * DAYS)],
            [lobsters_record("d", 10 * DAYS)],
        ]
    )

    assert [s.id for s in stories] == ["a", "b", "c"]
    assert web.paths == ["lobste.rs/newest/page/1.json", "lobste.rs/newest/page/2.json"]
    assert stories[0].origin == LOBSTERS_ORIGIN
    assert stories[0].discussion_url == "https://lobste.rs/s/a"


def test_lobsters_keeps_a_text_story_with_links_in_its_text():
    text = '<p>I built <a href="https://codeberg.org/alice/tool">tool</a>.</p>'
    stories, _ = lobsters([[lobsters_record("a", url="", description=text)], []])

    (story,) = stories
    assert story.url == ""
    assert story.links == ("https://codeberg.org/alice/tool",)


def test_lobsters_leaves_out_a_story_without_any_link():
    assert lobsters([[lobsters_record("a", url="", description="<p>Thoughts?</p>")], []])[0] == []


# --- Lemmy ---


def lemmy_post(id, age=3 * DAYS, url=None, body=None, score=20):
    return {
        "post": {
            "id": id, "name": f"Post {id}", "url": url, "body": body,
            "ap_id": f"https://programming.dev/post/{id}",
            "published": (NOW - age).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "deleted": False, "removed": False,
        },
        "counts": {"score": score, "comments": 2},
    }  # fmt: skip


def lemmy(answers, communities=("rust",)):
    web = FakeWeb({"programming.dev/api/v3/post/list": answers})
    with web.client(base_url=LEMMY_URL) as client:
        return LemmyCommunities(client, communities).discover(NOW), web


def test_lemmy_reads_the_newest_posts_of_each_community():
    stories, web = lemmy(
        httpx.Response(200, json={"posts": [lemmy_post(1, url="https://github.com/a/b")]}),
        communities=("rust", "linux@lemmy.ml"),
    )

    assert [s.origin for s in stories] == [lemmy_origin("rust"), lemmy_origin("linux@lemmy.ml")]
    params = web.requests[0].url.params
    assert (params["community_name"], params["sort"]) == ("rust", "New")
    story = stories[0]
    assert (story.title, story.url, story.points, story.comments) == (
        "Post 1", "https://github.com/a/b", 20, 2,
    )  # fmt: skip
    assert story.discussion_url == "https://programming.dev/post/1"


def test_lemmy_reads_further_pages_until_the_posts_are_older_than_8_days():
    stories, web = lemmy(
        [
            httpx.Response(200, json={"posts": [lemmy_post(1, body="https://github.com/a/b")]}),
            httpx.Response(200, json={"posts": [lemmy_post(2, 9 * DAYS, url="https://x.org")]}),
        ]
    )

    assert [s.id for s in stories] == ["1", "2"]
    assert [r.url.params["page"] for r in web.requests] == ["1", "2"]


def test_lemmy_finds_links_in_the_text_of_the_post():
    body = "Release notes: [here](https://github.com/alice/tool/releases), thanks!"
    (story,), _ = lemmy(
        [
            httpx.Response(200, json={"posts": [lemmy_post(1, body=body)]}),
            httpx.Response(200, json={"posts": []}),
        ]
    )

    assert story.links == ("https://github.com/alice/tool/releases",)


def test_lemmy_leaves_out_removed_posts():
    post = lemmy_post(1, url="https://github.com/a/b")
    post["post"]["removed"] = True

    stories, _ = lemmy([httpx.Response(200, json={"posts": [post]}), httpx.Response(200, json={})])

    assert stories == []


# --- Mastodon ---


def toot(id, age=3 * DAYS, content='<p>See <a href="https://github.com/a/tool">tool</a></p>'):
    return {
        "id": str(id), "url": f"https://fosstodon.org/@alice/{id}", "content": content,
        "created_at": (NOW - age).isoformat(), "in_reply_to_id": None, "reblog": None,
        "favourites_count": 2, "reblogs_count": 1, "replies_count": 4,
    }  # fmt: skip


def mastodon(answers, tags=("rust",)):
    web = FakeWeb({f"fosstodon.org/api/v1/timelines/tag/{tag}": answers for tag in tags})
    with web.client(base_url=MASTODON_URL) as client:
        return MastodonTags(client, tags).discover(NOW), web


def test_mastodon_counts_favourites_and_boosts_as_points():
    (story,), _ = mastodon([httpx.Response(200, json=[toot(1)]), httpx.Response(200, json=[])])

    assert story.origin == mastodon_origin("rust")
    assert (story.points, story.comments) == (3, 4)
    assert story.discussion_url == "https://fosstodon.org/@alice/1"
    assert story.links == ("https://github.com/a/tool",)
    assert story.title == "See tool"


def test_mastodon_pages_back_with_the_id_of_the_oldest_toot():
    _, web = mastodon(
        [
            httpx.Response(200, json=[toot(9), toot(7)]),
            httpx.Response(200, json=[toot(5, 9 * DAYS)]),
        ]
    )

    assert [r.url.params.get("max_id") for r in web.requests] == [None, "7"]


@pytest.mark.parametrize("change", [{"in_reply_to_id": "3"}, {"reblog": {"id": "4"}}])
def test_mastodon_leaves_out_replies_and_boosts(change):
    stories, _ = mastodon(
        [httpx.Response(200, json=[toot(1) | change]), httpx.Response(200, json=[])]
    )

    assert stories == []


# --- The bundle ---


class Fixed:
    def __init__(self, *stories, fails=False):
        self.stories, self.fails = list(stories), fails

    def discover(self, now, limit=None):
        if self.fails:
            raise SourceUnavailable("down")
        return self.stories


def story(id, age):
    return make_story(id, platform=FORUMS, created_at=NOW - age, discussion_url=f"https://d/{id}")


def test_the_bundle_keeps_stories_that_are_1_to_8_days_old():
    bundle = ForumStories(
        [Fixed(story("young", timedelta(hours=20)), story("ok", 2 * DAYS), story("old", 9 * DAYS))]
    )

    assert [s.id for s in bundle.discover(NOW)] == ["ok"]


def test_the_bundle_lists_a_story_found_twice_once():
    bundle = ForumStories([Fixed(story("a", 2 * DAYS)), Fixed(story("a", 2 * DAYS))])

    assert len(bundle.discover(NOW)) == 1


def test_the_bundle_goes_on_when_one_source_fails(caplog):
    bundle = ForumStories([Fixed(fails=True), Fixed(story("a", 2 * DAYS))])

    with caplog.at_level("WARNING"):
        assert [s.id for s in bundle.discover(NOW)] == ["a"]
    assert "down" in caplog.text


def test_the_bundle_fails_when_every_source_fails():
    with pytest.raises(SourceUnavailable):
        ForumStories([Fixed(fails=True), Fixed(fails=True)]).discover(NOW)


def test_a_failing_lobsters_makes_the_source_unavailable():
    web = FakeWeb({"lobste.rs/newest/page/1.json": httpx.Response(503)})
    with web.client(base_url=LOBSTERS_URL) as client, pytest.raises(SourceUnavailable):
        LobstersNewest(client, sleep=Sleeps()).discover(NOW)
