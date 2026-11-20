import dataclasses

from builders import TODAY, make_assessment

from explore_gh.domain.history import DailyRecord
from explore_gh.domain.model import Exclusion, Section, Signal


def test_a_daily_record_keeps_numbers_and_verdict():
    assessment = dataclasses.replace(
        make_assessment(
            "alice/tiny", section=Section.AI, gained=150, exclusion=Exclusion("x", "lure")
        ),
        signals=(Signal("momentum", 40, "…"), Signal("ai_files", -3, "…")),
    )

    record = DailyRecord.from_assessment(TODAY, assessment, rank=3, review="ok")

    assert record.day == TODAY
    assert str(record.repo) == "alice/tiny"
    assert (record.stars, record.forks, record.stars_gained) == (812, 31, 150)
    assert record.score == 37
    assert record.section is Section.AI
    assert record.exclusion == "lure"
    assert record.review == "ok"
    assert record.signals == (("momentum", 40), ("ai_files", -3))
    assert record.rank == 3
    assert record.language == "Rust"


def test_a_daily_record_holds_no_texts_and_no_people():
    fields = {field.name for field in dataclasses.fields(DailyRecord)}

    assert fields == {
        "day", "repo", "stars", "forks", "stars_gained", "score", "section", "exclusion",
        "review", "signals", "rank", "language", "created_at",
    }  # fmt: skip


def test_a_repo_not_shown_has_no_rank():
    assert DailyRecord.from_assessment(TODAY, make_assessment()).rank is None
