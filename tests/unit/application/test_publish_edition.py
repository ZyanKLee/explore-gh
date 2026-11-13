from datetime import timedelta

import pytest

from builders import NOW, TODAY, FixedClock, make_edition, make_snapshot
from fakes import InMemoryCollectionStatusStore, InMemoryEditionStore, InMemorySnapshotStore
from github_anti_ai.application.ports import AlreadyPublished, CollectionStatus, NothingToPublish
from github_anti_ai.application.publish_edition import PublishEdition
from github_anti_ai.domain.model import Assessment, Section


def assess_all_as(section=Section.MAIN, scores=None):
    """Stands in for the Assessment context until it exists."""
    scores = scores or {}

    def assess(snapshot):
        return Assessment(
            snapshot=snapshot,
            section=section,
            score=scores.get(str(snapshot.repo), 0.5),
            signals=(),
            exclusion=None,
        )

    return assess


def publish(snapshots, editions=None, assess=None, ignore_cooldown=False, day=None):
    snapshot_store = InMemorySnapshotStore({day or TODAY: snapshots})
    edition_store = editions if editions is not None else InMemoryEditionStore()
    use_case = PublishEdition(
        snapshot_store=snapshot_store,
        edition_store=edition_store,
        collection_status_store=InMemoryCollectionStatusStore(
            [CollectionStatus(day=day or TODAY, discovered=1, collected=1, failed=0)]
        ),
        assess=assess or assess_all_as(),
        clock=FixedClock(NOW),
        ignore_cooldown=ignore_cooldown,
    )
    return use_case.run(day), edition_store


def names(edition, section=Section.MAIN):
    return [str(e.repo) for e in edition.entries(section)]


def test_todays_snapshots_are_assessed_and_published_as_todays_edition():
    edition, store = publish(
        [make_snapshot("alice/tiny-editor"), make_snapshot("bob/rustbox")],
        assess=assess_all_as(scores={"alice/tiny-editor": 0.4, "bob/rustbox": 0.9}),
    )

    assert edition.day == TODAY
    assert names(edition) == ["bob/rustbox", "alice/tiny-editor"]
    assert store.load(TODAY) == edition


def test_edition_can_be_published_for_the_day_the_snapshots_were_collected():
    # a daily run that passes midnight must not look for snapshots of the new day
    yesterday = TODAY - timedelta(days=1)

    edition, store = publish([make_snapshot("alice/tiny-editor")], day=yesterday)

    assert edition.day == yesterday
    assert store.load(yesterday) == edition
    assert store.load(TODAY) is None


def test_assessment_decides_the_section():
    edition, _ = publish([make_snapshot("bob/agent-kit")], assess=assess_all_as(Section.AI))

    assert names(edition, Section.AI) == ["bob/agent-kit"]


def test_repos_of_recent_editions_are_held_back():
    recent = make_edition(day=TODAY - timedelta(days=10), main=["alice/tiny-editor"])

    edition, _ = publish(
        [make_snapshot("alice/tiny-editor"), make_snapshot("bob/rustbox")],
        editions=InMemoryEditionStore([recent]),
    )

    assert names(edition) == ["bob/rustbox"]


def test_cooldown_can_be_ignored_during_development():
    recent = make_edition(day=TODAY - timedelta(days=10), main=["alice/tiny-editor"])

    edition, _ = publish(
        [make_snapshot("alice/tiny-editor"), make_snapshot("bob/rustbox")],
        editions=InMemoryEditionStore([recent]),
        ignore_cooldown=True,
    )

    assert set(names(edition)) == {"alice/tiny-editor", "bob/rustbox"}


def test_published_edition_is_never_replaced():
    published = make_edition(day=TODAY, main=["carol/plotter"])
    store = InMemoryEditionStore([published])

    with pytest.raises(AlreadyPublished):
        publish([make_snapshot("alice/tiny-editor")], editions=store)

    assert store.load(TODAY) == published


def test_nothing_is_published_without_snapshots_of_today():
    store = InMemoryEditionStore()

    with pytest.raises(NothingToPublish):
        publish([], editions=store)

    assert store.load(TODAY) is None
