"""The file formats: what is written can be read again, and what was written before still can."""

import gzip
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from builders import NOW, TODAY, make_edition, make_entry, make_project, make_snapshot, make_story

from github_anti_ai.adapters.json_collection_status_store import JsonCollectionStatusStore
from github_anti_ai.adapters.json_community_edition_store import JsonCommunityEditionStore
from github_anti_ai.adapters.json_daily_record_store import JsonDailyRecordStore
from github_anti_ai.adapters.json_edition_store import JsonEditionStore
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.application.ports import AlreadyPublished, CollectionStatus
from github_anti_ai.domain.community import FORUMS, HN, LOBSTERS, CommunityEdition, Origin
from github_anti_ai.domain.history import DailyRecord
from github_anti_ai.domain.model import RepoId, Section, Signal

ARCHIVE = Path(__file__).parents[2] / "data"


class TestSnapshots:
    def test_appended_snapshots_are_read_back_the_latest_per_repo(self, tmp_path):
        store = JsonSnapshotStore(tmp_path)
        store.append(TODAY, [make_snapshot("a/x", stars=1), make_snapshot("b/y")])
        store.append(TODAY, [make_snapshot("A/X", stars=2)])

        loaded = {str(s.repo).lower(): s for s in store.load(TODAY)}

        assert loaded["a/x"].stars == 2
        assert loaded["b/y"] == make_snapshot("b/y")

    def test_the_age_of_the_facts_survives(self, tmp_path):
        store = JsonSnapshotStore(tmp_path)
        store.append(TODAY, [make_snapshot(facts_at=NOW - timedelta(days=2))])

        assert store.load(TODAY)[0].facts_at == NOW - timedelta(days=2)

    def test_files_of_earlier_versions_can_still_be_read(self, tmp_path):
        line = {
            "repo": "a/x", "taken_at": "2026-11-12T06:00:00+00:00", "description": "", "homepage": None,
            "topics": [], "primary_language": "C", "created_at": "2026-11-01T00:00:00+00:00",
            "pushed_at": None, "stars": 1, "forks": 0, "open_issues": 0, "watchers": 0,
            "pull_requests": 0, "recent_issue_authors": 0, "is_fork": False, "is_archived": False,
            "is_mirror": False, "is_template": False, "license": None, "root_files": [], "readme": "",
            "recent_commits": [], "star_history": [1],
        }  # fmt: skip
        (tmp_path / "2026-11-12.jsonl.gz").write_bytes(gzip.compress(json.dumps(line).encode()))

        (snapshot,) = JsonSnapshotStore(tmp_path).load(TODAY)

        assert snapshot.facts_at == snapshot.taken_at
        assert snapshot.owner_created_at is None

    def test_prune_removes_older_days_only(self, tmp_path):
        store = JsonSnapshotStore(tmp_path)
        for days_ago in (0, 14, 15):
            store.append(TODAY - timedelta(days=days_ago), [make_snapshot()])
        (tmp_path / "notes.txt").write_text("stays")

        store.prune(before=TODAY - timedelta(days=14))

        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "2026-10-29.jsonl.gz",
            "2026-11-12.jsonl.gz",
            "notes.txt",
        ]


def test_collection_status_replaces_the_one_of_the_same_day(tmp_path):
    store = JsonCollectionStatusStore(tmp_path)
    store.save(CollectionStatus(TODAY, 3, 2, 1))
    store.save(CollectionStatus(TODAY, 3, 3, 0))

    assert store.load(TODAY) == CollectionStatus(TODAY, 3, 3, 0)
    assert store.load(TODAY - timedelta(days=1)) is None


class TestEditions:
    def test_an_edition_is_read_back_as_written(self, tmp_path):
        edition = make_edition(main=[make_entry("a/x", score=12.5)], ai=["b/y"])
        store = JsonEditionStore(tmp_path)

        store.save(edition)

        assert store.load(TODAY) == edition

    def test_a_forums_edition_keeps_origin_and_where_the_repo_was_found(self, tmp_path):
        origin = Origin("Mastodon #rust", 5, 0, "Reaktionen")
        story = make_story("https://fosstodon.org/@a/1", FORUMS, origin=origin, url="")
        project = make_project(story=story, linked_directly=False, found_in_post=True)
        edition = CommunityEdition(FORUMS, TODAY, main=(project,))
        store = JsonCommunityEditionStore(FORUMS, tmp_path)

        store.save(edition)

        assert store.load(TODAY) == edition
        stored = json.loads((tmp_path / "forums-editions/2026-11-12.json").read_text())
        assert stored["projects"][0]["story"]["origin"] == {
            "name": "Mastodon #rust", "reference_points": 5, "min_points": 0,
            "points_label": "Reaktionen",
        }  # fmt: skip
        assert stored["projects"][0]["found_in_post"] is True

    def test_a_forums_edition_keeps_the_other_stories_of_a_repo(self, tmp_path):
        lobsters = Origin("Lobsters", 10, 10)
        lemmy = Origin("Lemmy c/rust", 15, 15)
        other = make_story("https://lemmy.ml/post/1", FORUMS, origin=lemmy, points=22)
        story = make_story("https://lobste.rs/s/3", FORUMS, origin=lobsters, points=34)
        project = make_project(story=story, other_stories=(other,))
        store = JsonCommunityEditionStore(FORUMS, tmp_path)

        store.save(CommunityEdition(FORUMS, TODAY, main=(project,)))

        assert store.load(TODAY).main[0].other_stories == (other,)

    def test_a_project_without_other_stories_stores_none(self, tmp_path):
        store = JsonCommunityEditionStore(HN, tmp_path)

        store.save(CommunityEdition(HN, TODAY, main=(make_project(),)))

        stored = json.loads((tmp_path / "hn-editions/2026-11-12.json").read_text())
        assert "other_stories" not in stored["projects"][0]

    def test_an_edition_is_never_replaced(self, tmp_path):
        store = JsonEditionStore(tmp_path)
        store.save(make_edition())

        with pytest.raises(AlreadyPublished):
            store.save(make_edition(main=["a/x"]))
        assert store.load(TODAY).main == ()

    def test_the_file_states_rank_url_gain_and_growth_window(self, tmp_path):
        JsonEditionStore(tmp_path).save(make_edition(main=[make_entry("a/x", gained=150)]))

        data = json.loads((tmp_path / "2026-11-12.json").read_text())

        assert data["growth_window_days"] == 14
        entry = data["sections"]["main"][0]
        assert (entry["rank"], entry["url"], entry["stars_gained"]) == (
            1,
            "https://github.com/a/x",
            150,
        )
        assert entry["created_at"].endswith("Z")

    def test_since_lists_the_days_from_a_date_on(self, tmp_path):
        store = JsonEditionStore(tmp_path)
        for days_ago in (0, 2, 5):
            store.save(make_edition(TODAY - timedelta(days=days_ago)))

        assert [e.day for e in store.since(TODAY - timedelta(days=2))] == [
            TODAY - timedelta(days=2),
            TODAY,
        ]

    def test_the_archive_can_be_read(self):
        editions = JsonEditionStore(ARCHIVE / "editions").since(date(2000, 1, 1))

        assert editions and all(len(e.main) <= 20 for e in editions)


class TestDailyRecords:
    def record(self, repo="a/x", **changes):
        fields = dict(
            day=TODAY, repo=RepoId.parse(repo), stars=10, forks=1, stars_gained=5, score=12.3456,
            section=Section.MAIN, exclusion=None, review=None, signals=(("momentum", 12.3456),),
            rank=None, language="C", created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )  # fmt: skip
        fields.update(changes)
        return DailyRecord(**fields)

    def test_records_are_rounded_sorted_and_replaced(self, tmp_path):
        store = JsonDailyRecordStore(tmp_path)
        store.save(TODAY, [self.record("b/y")])
        store.save(TODAY, [self.record("B/z"), self.record("a/x", review="ok", rank=1)])

        loaded = store.load(TODAY)

        assert [str(r.repo) for r in loaded] == ["a/x", "B/z"]
        assert loaded[0].score == 12.35
        assert loaded[0].review == "ok"
        assert store.days() == [TODAY]

    def test_the_same_records_give_the_same_bytes(self, tmp_path):
        store = JsonDailyRecordStore(tmp_path)
        store.save(TODAY, [self.record()])
        first = (tmp_path / "2026-11-12.jsonl.gz").read_bytes()
        store.save(TODAY, [self.record()])

        assert (tmp_path / "2026-11-12.jsonl.gz").read_bytes() == first

    def test_each_line_names_day_and_format_and_review_only_if_there_is_one(self, tmp_path):
        JsonDailyRecordStore(tmp_path).save(TODAY, [self.record()])

        line = json.loads(gzip.decompress((tmp_path / "2026-11-12.jsonl.gz").read_bytes()))

        assert (line["v"], line["day"]) == (1, "2026-11-12")
        assert "review" not in line

    def test_an_unknown_format_is_refused(self, tmp_path):
        (tmp_path / "2026-11-12.jsonl.gz").write_bytes(gzip.compress(b'{"v": 2}\n'))

        with pytest.raises(ValueError):
            JsonDailyRecordStore(tmp_path).load(TODAY)

    def test_records_of_another_day_are_refused(self, tmp_path):
        with pytest.raises(ValueError):
            JsonDailyRecordStore(tmp_path).save(TODAY, [self.record(day=date(2026, 1, 1))])


class TestCommunityEditions:
    @pytest.mark.parametrize("platform", [HN, LOBSTERS])
    def test_an_edition_is_read_back_as_written(self, tmp_path, platform):
        project = make_project(story=make_story("abc", platform), reasons=("Gefunden.",))
        edition = CommunityEdition(platform, TODAY, main=(project,))
        store = JsonCommunityEditionStore(platform, tmp_path)

        store.save(edition)
        loaded = store.load(TODAY)

        assert loaded == edition
        assert loaded.main[0].reasons == ("Gefunden.",)
        assert (tmp_path / f"{platform.slug}-editions" / "2026-11-12.json").exists()

    def test_hn_and_lobsters_name_the_points_as_before(self, tmp_path):
        for platform in (HN, LOBSTERS):
            story = make_story("abc", platform)
            JsonCommunityEditionStore(platform, tmp_path).save(
                CommunityEdition(platform, TODAY, main=(make_project(story=story),))
            )

        hn = json.loads((tmp_path / "hn-editions/2026-11-12.json").read_text())["projects"][0][
            "story"
        ]
        lobsters = json.loads((tmp_path / "lobsters-editions/2026-11-12.json").read_text())[
            "projects"
        ][0]["story"]
        assert list(hn) == ["id", "title", "url", "points", "comments", "created_at"]
        assert list(lobsters) == [
            "id",
            "title",
            "url",
            "discussion_url",
            "score",
            "comments",
            "created_at",
        ]

    def test_an_edition_is_never_replaced(self, tmp_path):
        store = JsonCommunityEditionStore(HN, tmp_path)
        store.save(CommunityEdition(HN, TODAY))

        with pytest.raises(AlreadyPublished):
            store.save(CommunityEdition(HN, TODAY))

    def test_editions_before_the_ai_section_are_read_with_an_empty_one(self, tmp_path):
        directory = tmp_path / "hn-editions"
        directory.mkdir()
        old = make_project(story=make_story("1"))
        data = {
            "format_version": 1, "day": "2026-11-12",
            "projects": [{
                "story": {"id": "1", "title": "T", "url": old.story.url, "points": 5, "comments": 1,
                          "created_at": "2026-11-12T01:00:00+00:00"},
                "repository_url": old.repository_url, "project_url": old.project_url,
                "description": "", "language": "C", "license_id": "MIT", "is_fork": False,
                "is_archived": False, "has_code": True,
            }],
        }  # fmt: skip
        (directory / "2026-11-12.json").write_text(json.dumps(data))

        edition = JsonCommunityEditionStore(HN, tmp_path).load(TODAY)

        assert edition.ai == ()
        assert edition.main[0].story.discussion_url == "https://news.ycombinator.com/item?id=1"
        assert edition.main[0].reasons == ()

    @pytest.mark.parametrize("platform", [HN, LOBSTERS])
    def test_the_archive_can_be_read(self, platform):
        editions = JsonCommunityEditionStore(platform, ARCHIVE).since(date(2000, 1, 1))

        assert editions


def test_signals_keep_their_reason_in_the_edition(tmp_path):
    entry = make_entry("a/x")
    store = JsonEditionStore(tmp_path)
    store.save(make_edition(main=[entry]))

    assert store.load(TODAY).main[0].signals == (Signal("momentum", 1.0, "1.0 Punkte"),)
