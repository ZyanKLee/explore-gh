import gzip
import json
from datetime import UTC, datetime, timedelta

import pytest

from builders import TODAY
from github_anti_ai.adapters.json_daily_record_store import JsonDailyRecordStore
from github_anti_ai.domain.history import DailyRecord
from github_anti_ai.domain.model import RepoId, Section


def record(repo="alice/tiny-editor", day=TODAY, **changes):
    fields = dict(
        day=day,
        repo=RepoId.parse(repo),
        stars=812,
        forks=31,
        stars_gained=120,
        score=37.25,
        section=Section.MAIN,
        exclusion=None,
        signals=(("momentum", 40.25), ("ai_files", -3.0)),
        rank=3,
        language="Rust",
        created_at=datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
    )
    fields.update(changes)
    return DailyRecord(**fields)


RECORDS = [
    record(),
    record("Bob/rustbox", section=Section.AI, rank=None, language=None, signals=()),
    record("mallory/lure", exclusion="lure", rank=None),
]


def lines(tmp_path, name="2026-11-12.jsonl.gz"):
    return [
        json.loads(line)
        for line in gzip.decompress((tmp_path / name).read_bytes()).decode().splitlines()
    ]


def test_saved_records_are_loaded_unchanged(tmp_path):
    store = JsonDailyRecordStore(tmp_path)

    store.save(TODAY, RECORDS)

    assert sorted(store.load(TODAY), key=lambda r: str(r.repo).lower()) == sorted(
        RECORDS, key=lambda r: str(r.repo).lower()
    )


def test_a_day_is_one_compressed_file_with_one_line_per_repo(tmp_path):
    JsonDailyRecordStore(tmp_path).save(TODAY, RECORDS)

    assert [line["repo"] for line in lines(tmp_path)] == [
        "alice/tiny-editor",
        "Bob/rustbox",
        "mallory/lure",
    ]


def test_every_line_stands_on_its_own(tmp_path):
    # tools like DuckDB read many days at once: each line must say which day and format it is
    JsonDailyRecordStore(tmp_path).save(TODAY, RECORDS)

    for line in lines(tmp_path):
        assert line["day"] == "2026-11-12"
        assert line["v"] == 1


def test_day_without_records_is_empty(tmp_path):
    assert JsonDailyRecordStore(tmp_path).load(TODAY) == []


def test_saving_a_day_again_replaces_it(tmp_path):
    # happens when an Edition is deleted and published again
    store = JsonDailyRecordStore(tmp_path)
    store.save(TODAY, RECORDS)

    store.save(TODAY, [record("carol/plotter")])

    assert [str(r.repo) for r in store.load(TODAY)] == ["carol/plotter"]


def test_same_records_give_the_same_bytes(tmp_path):
    # the files live in git: writing a day again must not look like a change
    first, second = JsonDailyRecordStore(tmp_path / "a"), JsonDailyRecordStore(tmp_path / "b")

    first.save(TODAY, RECORDS)
    second.save(TODAY, list(reversed(RECORDS)))

    name = "2026-11-12.jsonl.gz"
    assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_records_must_belong_to_the_day_they_are_saved_under(tmp_path):
    with pytest.raises(ValueError):
        JsonDailyRecordStore(tmp_path).save(TODAY, [record(day=TODAY - timedelta(days=1))])


def test_days_with_records_are_listed_in_order(tmp_path):
    store = JsonDailyRecordStore(tmp_path)
    earlier = TODAY - timedelta(days=3)
    store.save(TODAY, RECORDS)
    store.save(earlier, [record(day=earlier)])
    (tmp_path / "notes.txt").write_text("not a day")

    assert store.days() == [earlier, TODAY]


def test_file_of_an_unknown_format_is_refused(tmp_path):
    store = JsonDailyRecordStore(tmp_path)
    store.save(TODAY, RECORDS)
    path = tmp_path / "2026-11-12.jsonl.gz"
    newer = [dict(line, v=2) for line in lines(tmp_path)]
    path.write_bytes(gzip.compress("\n".join(json.dumps(line) for line in newer).encode()))

    with pytest.raises(ValueError, match="2026-11-12"):
        store.load(TODAY)
