"""PublishEdition lets a Reviewer read the repos that would be shown, and only those."""

from builders import NOW, TODAY, FixedClock, make_snapshot
from fakes import (
    FakeReviewer,
    InMemoryCollectionStatusStore,
    InMemoryDailyRecordStore,
    InMemoryEditionStore,
    InMemorySnapshotStore,
)
from github_anti_ai.application.ports import CollectionStatus
from github_anti_ai.application.publish_edition import MAX_REVIEW_ROUNDS, PublishEdition
from github_anti_ai.domain.edition import ENTRIES_PER_SECTION
from github_anti_ai.domain.model import Assessment, Section
from github_anti_ai.domain.review import Review

MALWARE = Review("malware", "Das README führt zu einem ZIP mit Passwort.")
LANGUAGES = ["Rust", "Go", "C", "Zig", "Python", "Lua", "Nim", "OCaml", "Ruby", "Elixir"]


def by_stars(snapshot):
    return Assessment(
        snapshot=snapshot, section=Section.MAIN, score=snapshot.stars, signals=(), exclusion=None
    )


def repos(count):
    """Repos of different owners and languages, the first one scores best."""
    return [
        make_snapshot(f"user{i}/project{i}", stars=5000 - i, primary_language=LANGUAGES[i % 10])
        for i in range(count)
    ]


def publish(snapshots, reviewer):
    records = InMemoryDailyRecordStore()
    edition = PublishEdition(
        snapshot_store=InMemorySnapshotStore({TODAY: snapshots}),
        edition_store=InMemoryEditionStore(),
        collection_status_store=InMemoryCollectionStatusStore(
            [CollectionStatus(day=TODAY, discovered=1, collected=1, failed=0)]
        ),
        record_store=records,
        assess=by_stars,
        clock=FixedClock(NOW),
        reviewer=reviewer,
    ).run()
    return edition, records


def names(edition):
    return [str(entry.repo) for entry in edition.entries(Section.MAIN)]


def test_only_the_repos_that_would_be_shown_are_reviewed():
    reviewer = FakeReviewer()

    edition, _ = publish(repos(ENTRIES_PER_SECTION + 15), reviewer)

    assert sorted(reviewer.asked) == sorted(names(edition))
    assert len(reviewer.asked) == ENTRIES_PER_SECTION


def test_a_rejected_repo_is_not_shown_and_the_next_one_moves_up_after_its_own_review():
    reviewer = FakeReviewer({"user0/project0": MALWARE})

    edition, _ = publish(repos(ENTRIES_PER_SECTION + 5), reviewer)

    shown = names(edition)
    assert "user0/project0" not in shown
    assert f"user{ENTRIES_PER_SECTION}/project{ENTRIES_PER_SECTION}" in shown
    assert reviewer.rounds[1] == [f"user{ENTRIES_PER_SECTION}/project{ENTRIES_PER_SECTION}"]
    assert len(shown) == ENTRIES_PER_SECTION


def test_no_repo_is_reviewed_twice():
    reviewer = FakeReviewer({"user0/project0": MALWARE, "user20/project20": MALWARE})

    publish(repos(ENTRIES_PER_SECTION + 5), reviewer)

    assert len(reviewer.asked) == len(set(reviewer.asked))


def test_shown_repos_say_that_they_were_reviewed():
    edition, _ = publish(repos(3), FakeReviewer())

    for entry in edition.entries(Section.MAIN):
        assert [s.reason for s in entry.signals] == ["Gegengelesen von Copilot: unauffällig"]


def test_the_rejection_is_kept_in_the_records_of_the_day():
    _, records = publish(repos(3), FakeReviewer({"user1/project1": MALWARE}))

    kinds = {str(record.repo): record.exclusion for record in records.load(TODAY)}
    assert kinds == {"user0/project0": None, "user1/project1": "review", "user2/project2": None}


def test_rejected_repos_count_as_excluded_in_the_statistics():
    edition, _ = publish(repos(3), FakeReviewer({"user1/project1": MALWARE}))

    assert edition.stats.excluded == 1


def test_edition_is_published_without_review_if_the_reviewer_is_unavailable():
    reviewer = FakeReviewer({"user0/project0": MALWARE}, unavailable=True)

    edition, _ = publish(repos(3), reviewer)

    assert names(edition) == ["user0/project0", "user1/project1", "user2/project2"]
    assert all(entry.signals == () for entry in edition.entries(Section.MAIN))
    assert len(reviewer.rounds) == 1


def test_a_repo_the_reviewer_says_nothing_about_is_shown_and_not_asked_again():
    reviewer = FakeReviewer(silent=["user1/project1"])

    edition, _ = publish(repos(3), reviewer)

    assert "user1/project1" in names(edition)
    assert reviewer.asked.count("user1/project1") == 1


def test_review_stops_after_a_few_rounds_even_if_every_repo_is_rejected():
    everything = {f"user{i}/project{i}": MALWARE for i in range(200)}
    reviewer = FakeReviewer(everything)

    edition, _ = publish(repos(200), reviewer)

    assert len(reviewer.rounds) == MAX_REVIEW_ROUNDS
    # what moves up after the last round is shown, visibly without review
    assert len(names(edition)) == ENTRIES_PER_SECTION
    assert all(entry.signals == () for entry in edition.entries(Section.MAIN))


def test_without_a_reviewer_nothing_is_reviewed():
    edition, _ = publish(repos(3), None)

    assert len(names(edition)) == 3
    assert all(entry.signals == () for entry in edition.entries(Section.MAIN))


def test_a_repo_reviewed_as_ai_focused_appears_in_the_ai_section():
    snapshots = repos(ENTRIES_PER_SECTION + 5)
    ai_focused = Review("ai_focus", "Ein Verfahren für Sprachmodelle.")
    reviewer = FakeReviewer({"user3/project3": ai_focused})

    edition, records = publish(snapshots, reviewer)

    assert "user3/project3" not in names(edition)
    assert [str(entry.repo) for entry in edition.entries(Section.AI)] == ["user3/project3"]
    # the place it left is filled, and the repo that moved up was read as well
    assert len(names(edition)) == ENTRIES_PER_SECTION
    assert sorted(reviewer.asked) == sorted([*names(edition), "user3/project3"])


def test_the_category_of_each_review_is_kept_in_the_records_of_the_day():
    reviewer = FakeReviewer(
        {"user1/project1": MALWARE, "user2/project2": Review("ai_focus", "Ein LLM-Werkzeug.")},
        silent=["user3/project3"],
    )

    _, records = publish(repos(4), reviewer)

    assert {str(record.repo): record.review for record in records.load(TODAY)} == {
        "user0/project0": "ok",
        "user1/project1": "malware",
        "user2/project2": "ai_focus",
        "user3/project3": None,
    }


def test_the_log_names_what_the_review_changed_and_why(caplog):
    caplog.set_level("INFO")
    reviewer = FakeReviewer(
        {"user1/project1": MALWARE, "user2/project2": Review("ai_focus", "Ein LLM-Werkzeug.")}
    )

    publish(repos(4), reviewer)

    assert "user1/project1 herausgenommen (malware): Das README führt zu einem ZIP" in caplog.text
    assert "user2/project2 in die AI-Sektion verschoben: Ein LLM-Werkzeug." in caplog.text
    assert "user0/project0" not in caplog.text
    assert "4 gelesen, 1 in die AI-Sektion verschoben, 1 herausgenommen" in caplog.text
