from datetime import timedelta

from builders import TODAY
from github_anti_ai.adapters.json_collection_status_store import JsonCollectionStatusStore
from github_anti_ai.application.ports import CollectionStatus

STATUS = CollectionStatus(day=TODAY, discovered=2846, collected=2826, failed=20)


def test_saved_status_is_loaded_unchanged(tmp_path):
    store = JsonCollectionStatusStore(tmp_path)

    store.save(STATUS)

    assert store.load(TODAY) == STATUS


def test_status_lies_next_to_the_snapshots_of_the_day(tmp_path):
    JsonCollectionStatusStore(tmp_path).save(STATUS)

    assert (tmp_path / "2026-11-12.status.json").exists()


def test_a_later_status_of_the_same_day_replaces_the_earlier_one(tmp_path):
    store = JsonCollectionStatusStore(tmp_path)
    store.save(STATUS)

    store.save(CollectionStatus(day=TODAY, discovered=2846, collected=2846, failed=0))

    assert store.load(TODAY).is_complete


def test_day_without_status_has_none(tmp_path):
    assert JsonCollectionStatusStore(tmp_path).load(TODAY) is None


def test_old_statuses_are_pruned_with_the_snapshots(tmp_path):
    store = JsonCollectionStatusStore(tmp_path)
    old = TODAY - timedelta(days=20)
    store.save(CollectionStatus(day=old, discovered=1, collected=1, failed=0))
    store.save(STATUS)

    store.prune(before=TODAY - timedelta(days=14))

    assert store.load(old) is None
    assert store.load(TODAY) == STATUS
