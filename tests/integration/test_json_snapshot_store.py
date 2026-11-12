import gzip
import json
from datetime import UTC, datetime, timedelta

from builders import TODAY, make_commit, make_snapshot, star_history
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore


def rich_snapshot():
    return make_snapshot(
        homepage="https://tiny-editor.example.org",
        recent_commits=(
            make_commit(co_authors=("Claude <noreply@anthropic.com>",)),
            make_commit(
                committed_at=datetime(2026, 11, 8, 9, 30, tzinfo=UTC),
                author="dependabot[bot]",
                is_bot=True,
                headline="Bump crossterm",
            ),
        ),
        star_history=star_history(2000),
    )


def test_appended_snapshots_are_loaded_unchanged(tmp_path):
    store = JsonSnapshotStore(tmp_path)
    snapshots = [rich_snapshot(), make_snapshot("carol/empty-thing", primary_language=None, pushed_at=None)]

    store.append(TODAY, snapshots)

    assert store.load(TODAY) == snapshots


def test_snapshots_of_a_day_are_stored_as_compressed_json_lines(tmp_path):
    store = JsonSnapshotStore(tmp_path)
    store.append(TODAY, [make_snapshot()])
    store.append(TODAY, [make_snapshot("bob/rustbox")])

    path = tmp_path / "2026-11-12.jsonl.gz"
    lines = gzip.decompress(path.read_bytes()).decode().splitlines()
    assert [json.loads(line)["repo"] for line in lines] == ["alice/tiny-editor", "bob/rustbox"]


def test_day_without_snapshots_loads_as_empty(tmp_path):
    assert JsonSnapshotStore(tmp_path).load(TODAY) == []


def test_appending_to_a_day_adds_to_what_is_there(tmp_path):
    store = JsonSnapshotStore(tmp_path)

    store.append(TODAY, [make_snapshot()])
    store.append(TODAY, [make_snapshot("bob/rustbox")])

    assert [str(s.repo) for s in store.load(TODAY)] == ["alice/tiny-editor", "bob/rustbox"]


def test_latest_snapshot_of_a_repo_wins(tmp_path):
    store = JsonSnapshotStore(tmp_path)

    store.append(TODAY, [make_snapshot(stars=100), make_snapshot("bob/rustbox")])
    store.append(TODAY, [make_snapshot(stars=150)])

    loaded = store.load(TODAY)
    assert [(str(s.repo), s.stars) for s in loaded] == [
        ("alice/tiny-editor", 150),
        ("bob/rustbox", 812),
    ]


def test_store_directory_is_created_on_first_append(tmp_path):
    store = JsonSnapshotStore(tmp_path / "data" / "snapshots")

    store.append(TODAY, [make_snapshot()])

    assert store.load(TODAY) != []


def test_prune_removes_only_days_before_the_given_day(tmp_path):
    store = JsonSnapshotStore(tmp_path)
    older, cutoff = TODAY - timedelta(days=15), TODAY - timedelta(days=14)
    store.append(older, [make_snapshot()])
    store.append(cutoff, [make_snapshot()])
    (tmp_path / "notes.txt").write_text("not a snapshot")

    store.prune(before=cutoff)

    assert store.load(older) == []
    assert store.load(cutoff) != []
    assert (tmp_path / "notes.txt").exists()
