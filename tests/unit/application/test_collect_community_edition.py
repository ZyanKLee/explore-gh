from datetime import date, timedelta

import pytest
from builders import TODAY, FixedClock, make_project, make_story
from fakes import FakeResolver, FakeStorySource, InMemoryEditionStore

from explore_gh.application.collect_community_edition import CollectCommunityEdition
from explore_gh.domain.community import FORUMS, HN, LOBSTERS, CommunityEdition
from explore_gh.domain.withdrawal import Withdrawal


def collect(stories, resolver, store=None, platform=HN, limit=None):
    store = store if store is not None else InMemoryEditionStore()
    edition = CollectCommunityEdition(
        platform, stories, resolver, store, FixedClock(), limit=limit
    ).run()
    return edition, store


def project_for(story, name):
    return make_project(f"https://github.com/{name}", story=story, description=f"Tool {name}")


@pytest.mark.parametrize("platform", [HN, LOBSTERS])
def test_stores_the_edition_of_today_for_its_platform(platform):
    story = make_story("1", platform)
    edition, store = collect(
        FakeStorySource(story), FakeResolver({"1": project_for(story, "a/x")}), platform=platform
    )

    assert edition.platform is platform
    assert [p.repository_url for p in edition.main] == ["https://github.com/a/x"]
    assert store.load(TODAY) == edition


def test_stories_without_a_project_and_failing_ones_are_left_out():
    stories = [make_story("1"), make_story("2"), make_story("3")]
    resolver = FakeResolver({"1": project_for(stories[0], "a/x")}, failing={"3"})

    edition, _ = collect(FakeStorySource(*stories), resolver)

    assert len(edition.main) == 1


def test_an_existing_edition_is_kept_and_nothing_is_fetched():
    existing = CommunityEdition(HN, TODAY)
    stories = FakeStorySource(make_story("1"))

    edition, _ = collect(stories, FakeResolver(), InMemoryEditionStore([existing]))

    assert edition is existing
    assert stories.asked == 0


def test_repos_of_own_editions_of_the_last_30_days_are_blocked():
    story = make_story("1")
    shown = CommunityEdition(HN, TODAY - timedelta(days=1), main=(project_for(story, "a/x"),))

    edition, _ = collect(
        FakeStorySource(story),
        FakeResolver({"1": project_for(story, "a/x")}),
        InMemoryEditionStore([shown]),
    )

    assert edition.main == ()


def test_the_weekly_forums_edition_belongs_to_the_monday_of_the_week():
    monday = TODAY - timedelta(days=TODAY.weekday())
    story = make_story("1", FORUMS)

    edition, store = collect(
        FakeStorySource(story), FakeResolver({"1": project_for(story, "a/x")}), platform=FORUMS
    )

    assert edition.day == monday
    assert store.load(monday) == edition


def test_a_weekly_edition_of_this_week_is_kept_on_the_following_days():
    monday = TODAY - timedelta(days=TODAY.weekday())
    existing = CommunityEdition(FORUMS, monday)
    stories = FakeStorySource(make_story("1", FORUMS))

    edition, _ = collect(stories, FakeResolver(), InMemoryEditionStore([existing]), FORUMS)

    assert edition is existing
    assert stories.asked == 0


def test_a_withdrawn_project_is_left_out():
    story = make_story("1")
    withdrawal = Withdrawal("https://github.com/a/x", date(2026, 11, 1), "Raubkopie")

    edition = CollectCommunityEdition(
        HN,
        FakeStorySource(story),
        FakeResolver({"1": project_for(story, "a/x")}),
        InMemoryEditionStore(),
        FixedClock(),
        withdrawals=[withdrawal],
    ).run()

    assert edition.main == ()
