"""A DailyRecord is what stays of an Assessment for good: numbers and verdict, no texts."""

from dataclasses import fields
from datetime import UTC, datetime

from builders import TODAY, make_assessment
from github_anti_ai.domain.history import DailyRecord
from github_anti_ai.domain.model import Exclusion, RepoId, Section, Signal

SIGNALS = (
    Signal(kind="momentum", weight=40.0, reason="+120 Sterne in 7 Tagen bei 812 insgesamt"),
    Signal(kind="ai_files", weight=-3.0, reason="Anweisungsdateien für AI-Agenten: AGENTS.md"),
)


def record(rank=None, **options):
    return DailyRecord.from_assessment(TODAY, make_assessment(**options), rank=rank)


def test_record_keeps_the_numbers_of_the_day():
    kept = record(gained=120)

    assert kept.day == TODAY
    assert kept.repo == RepoId.parse("alice/tiny-editor")
    assert (kept.stars, kept.forks, kept.stars_gained) == (812, 31, 120)


def test_record_keeps_the_verdict_of_the_assessment():
    kept = record(section=Section.AI, score=37.0, signals=SIGNALS)

    assert kept.section is Section.AI
    assert kept.score == 37.0
    assert kept.exclusion is None


def test_record_keeps_kind_and_weight_of_each_signal_but_not_its_text():
    assert record(signals=SIGNALS).signals == (("momentum", 40.0), ("ai_files", -3.0))


def test_record_of_an_excluded_repo_names_the_kind_of_exclusion():
    assert record(exclusion=Exclusion("Fork", "fork")).exclusion == "fork"


def test_record_keeps_what_identifies_the_kind_of_project():
    kept = record(language="Rust")

    assert kept.language == "Rust"
    assert kept.created_at == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_record_of_a_repo_that_was_not_shown_has_no_rank():
    assert record().rank is None


def test_record_of_a_shown_repo_knows_its_rank():
    assert record(rank=3).rank == 3


def test_record_holds_neither_texts_nor_commits_nor_people():
    # The long-term data must stay small and free of names and addresses. The description
    # was in at first and made up 60 % of the file.
    assert {field.name for field in fields(DailyRecord)} == {
        "day",
        "repo",
        "stars",
        "forks",
        "stars_gained",
        "score",
        "section",
        "exclusion",
        "signals",
        "rank",
        "language",
        "created_at",
    }
