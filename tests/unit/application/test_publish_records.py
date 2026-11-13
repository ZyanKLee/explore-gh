"""Publishing an Edition also keeps a DailyRecord of every repo that was assessed."""

from datetime import timedelta

import pytest

from builders import NOW, TODAY, FixedClock, make_edition, make_snapshot
from fakes import (
    InMemoryCollectionStatusStore,
    InMemoryDailyRecordStore,
    InMemoryEditionStore,
    InMemorySnapshotStore,
)
from github_anti_ai.application.ports import (
    AlreadyPublished,
    CollectionStatus,
    IncompleteCollection,
)
from github_anti_ai.application.publish_edition import PublishEdition
from github_anti_ai.domain.model import Assessment, Exclusion, Section


def assess(snapshot):
    """Stars are the score. Repos of mallory are excluded, repos of dora belong to the AI section."""
    return Assessment(
        snapshot=snapshot,
        section=Section.AI if snapshot.repo.owner == "dora" else Section.MAIN,
        score=float(snapshot.stars),
        signals=(),
        exclusion=Exclusion("Köder", "lure") if snapshot.repo.owner == "mallory" else None,
    )


def publish(snapshots, *, editions=None, records=None, complete=True, day=None):
    day = day or TODAY
    records = records if records is not None else InMemoryDailyRecordStore()
    statuses = [CollectionStatus(day=day, discovered=9, collected=9, failed=0 if complete else 2)]
    PublishEdition(
        snapshot_store=InMemorySnapshotStore({day: snapshots}),
        edition_store=editions if editions is not None else InMemoryEditionStore(),
        collection_status_store=InMemoryCollectionStatusStore(statuses),
        record_store=records,
        assess=assess,
        clock=FixedClock(NOW),
    ).run(day)
    return records


def by_repo(records, day=TODAY):
    return {str(record.repo): record for record in records.load(day)}


SNAPSHOTS = [
    make_snapshot("alice/tiny-editor", stars=900),
    make_snapshot("bob/rustbox", stars=500),
    make_snapshot("dora/llm-proxy", stars=700),
    make_snapshot("mallory/lure", stars=5000),
]


def test_every_assessed_repo_gets_a_record_even_an_excluded_one():
    kept = by_repo(publish(SNAPSHOTS))

    assert set(kept) == {"alice/tiny-editor", "bob/rustbox", "dora/llm-proxy", "mallory/lure"}
    assert kept["mallory/lure"].exclusion == "lure"
    assert kept["alice/tiny-editor"].score == 900.0


def test_shown_repos_carry_their_rank_within_their_section():
    kept = by_repo(publish(SNAPSHOTS))

    assert kept["alice/tiny-editor"].rank == 1
    assert kept["bob/rustbox"].rank == 2
    assert kept["dora/llm-proxy"].rank == 1


def test_repos_that_are_not_shown_have_no_rank():
    recent = make_edition(day=TODAY - timedelta(days=10), main=["alice/tiny-editor"])

    kept = by_repo(publish(SNAPSHOTS, editions=InMemoryEditionStore([recent])))

    assert kept["mallory/lure"].rank is None  # excluded
    assert kept["alice/tiny-editor"].rank is None  # held back by the cooldown
    assert kept["bob/rustbox"].rank == 1


def test_records_belong_to_the_day_of_the_edition():
    yesterday = TODAY - timedelta(days=1)

    records = publish(SNAPSHOTS, day=yesterday)

    assert len(records.load(yesterday)) == 4
    assert records.load(TODAY) == []
    assert all(record.day == yesterday for record in records.load(yesterday))


def test_records_of_a_published_day_are_left_alone():
    records = publish([make_snapshot("carol/plotter")])
    editions = InMemoryEditionStore([make_edition(day=TODAY, main=["carol/plotter"])])

    with pytest.raises(AlreadyPublished):
        publish(SNAPSHOTS, editions=editions, records=records)

    assert set(by_repo(records)) == {"carol/plotter"}


def test_incomplete_collection_leaves_no_records():
    records = InMemoryDailyRecordStore()

    with pytest.raises(IncompleteCollection):
        publish(SNAPSHOTS, records=records, complete=False)

    assert records.load(TODAY) == []


def test_edition_is_only_saved_once_the_records_are():
    # an Edition can never be replaced. If the records fail, the day must stay open.
    class BrokenRecordStore(InMemoryDailyRecordStore):
        def save(self, day, records):
            raise OSError("Platte voll")

    editions = InMemoryEditionStore()

    with pytest.raises(OSError):
        publish(SNAPSHOTS, editions=editions, records=BrokenRecordStore())

    assert editions.load(TODAY) is None
