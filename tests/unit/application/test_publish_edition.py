import logging
from datetime import timedelta

import pytest
from builders import TODAY, make_edition, make_snapshot, star_history
from fakes import (
    FakeReviewer,
    InMemoryDailyRecordStore,
    InMemoryEditionStore,
    InMemorySnapshotStore,
    InMemoryStatusStore,
)

from github_anti_ai.application.ports import (
    AlreadyPublished,
    CollectionStatus,
    IncompleteCollection,
    NothingToPublish,
)
from github_anti_ai.application.publish_edition import PublishEdition, reviewed_entries
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.model import Section

COMPLETE = CollectionStatus(TODAY, discovered=3, collected=3, failed=0)


class World:
    def __init__(self, *snapshots, editions=(), status=COMPLETE):
        self.snapshots = InMemorySnapshotStore({TODAY: list(snapshots)})
        self.status = InMemoryStatusStore([status] if status else [])
        self.editions = InMemoryEditionStore(editions)
        self.records = InMemoryDailyRecordStore()

    def publish(self, **options):
        return PublishEdition(
            snapshot_store=self.snapshots,
            status_store=self.status,
            edition_store=self.editions,
            record_store=self.records,
            assess=Assessor().assess,
            **options,
        ).run(TODAY)


def repo(name, gained=120, **overrides):
    """A repo that passes every rule. More new stars give a higher score."""
    return make_snapshot(name, star_history=star_history(gained), **overrides)


def names(entries):
    return [str(entry.repo) for entry in entries]


def test_publishes_the_best_repos_of_both_sections():
    world = World(
        repo("a/editor", gained=100, primary_language="Go"),
        repo("b/editor", gained=900),
        repo("c/llm-chat", description="A chatbot"),
    )

    edition = world.publish()

    assert names(edition.main) == ["b/editor", "a/editor"]
    assert names(edition.ai) == ["c/llm-chat"]
    assert world.editions.load(TODAY) == edition
    assert edition.stats.assessed == 3


def test_excludes_copies_among_the_repos_of_the_day():
    world = World(repo("a/player", description="Player"), repo("b/player", description="Player"))

    assert world.publish().main == ()


def test_refuses_a_day_that_is_published():
    world = World(repo("a/x"), editions=[make_edition(TODAY)])

    with pytest.raises(AlreadyPublished):
        world.publish()


def test_refuses_a_day_without_snapshots():
    with pytest.raises(NothingToPublish):
        World().publish()


@pytest.mark.parametrize("status", [None, CollectionStatus(TODAY, 3, 2, failed=1)])
def test_refuses_an_incomplete_collection(status):
    world = World(repo("a/x"), status=status)

    with pytest.raises(IncompleteCollection):
        world.publish()
    assert world.records.days() == []


def test_publishes_an_incomplete_collection_when_allowed():
    world = World(repo("a/x"), status=None)

    assert names(world.publish(allow_incomplete=True).main) == ["a/x"]


def test_repos_of_the_last_30_days_are_blocked():
    world = World(repo("a/x"), editions=[make_edition(TODAY - timedelta(days=3), main=["a/x"])])

    assert world.publish().main == ()


def test_ignore_cooldown_lets_them_back_in():
    world = World(repo("a/x"), editions=[make_edition(TODAY - timedelta(days=3), main=["a/x"])])

    assert names(world.publish(ignore_cooldown=True).main) == ["a/x"]


def test_keeps_a_daily_record_of_every_assessed_repo():
    world = World(repo("a/x"), repo("b/fork", is_fork=True))

    world.publish()

    records = {str(r.repo): r for r in world.records.load(TODAY)}
    assert records["a/x"].rank == 1
    assert records["b/fork"].rank is None
    assert records["b/fork"].exclusion == "fork"


class TestReview:
    def test_reads_only_the_repos_that_would_be_shown(self):
        world = World(repo("a/x"), repo("b/fork", is_fork=True))
        reviewer = FakeReviewer()

        edition = world.publish(reviewer=reviewer)

        assert reviewer.asked == ["a/x"]
        assert edition.main[0].signals[-1].reason == "Gegengelesen von Copilot: unauffällig"
        assert reviewed_entries(edition) == (1, 1)

    def test_a_repo_taken_out_makes_room_for_the_next_which_is_read_too(self, caplog):
        snapshots = [repo(f"o{i}/r", gained=1000 - i, primary_language=f"L{i}") for i in range(21)]
        world = World(*snapshots)
        reviewer = FakeReviewer({"o0/r": "malware"})

        with caplog.at_level(logging.INFO):
            edition = world.publish(reviewer=reviewer)

        assert "o0/r" not in names(edition.main)
        assert names(edition.main)[-1] == "o20/r"
        assert reviewer.rounds[1] == ["o20/r"]
        assert "Copilot: o0/r herausgenommen (malware): Begründung des Modells." in caplog.text
        records = {str(r.repo): r for r in world.records.load(TODAY)}
        assert (records["o0/r"].exclusion, records["o0/r"].review) == ("review", "malware")

    def test_ai_focus_moves_a_repo_to_the_ai_section(self):
        world = World(repo("a/x"))

        edition = world.publish(reviewer=FakeReviewer({"a/x": "ai_focus"}))

        assert names(edition.ai) == ["a/x"]
        assert world.records.load(TODAY)[0].section is Section.AI

    def test_without_an_answer_the_edition_appears_unreviewed(self):
        edition = World(repo("a/x")).publish(reviewer=FakeReviewer(unavailable=True))

        assert names(edition.main) == ["a/x"]
        assert reviewed_entries(edition) == (0, 1)

    def test_a_repo_the_reviewer_says_nothing_about_stays_unread(self):
        world = World(repo("a/x"))

        edition = world.publish(reviewer=FakeReviewer(silent=["a/x"]))

        assert names(edition.main) == ["a/x"]
        assert world.records.load(TODAY)[0].review is None
