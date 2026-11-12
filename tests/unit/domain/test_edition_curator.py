from datetime import timedelta

from builders import TODAY, make_assessment, make_edition
from github_anti_ai.domain.edition import (
    COOLDOWN_DAYS,
    ENTRIES_PER_SECTION,
    MAX_PER_LANGUAGE,
    MAX_PER_OWNER,
    EditionCurator,
    EditionStats,
)
from github_anti_ai.domain.model import Exclusion, Section

LANGUAGES = ["Rust", "Go", "C", "Zig", "Python", "Lua"]


def curate(assessments, past_editions=()):
    return EditionCurator().curate(TODAY, assessments, past_editions)


def names(edition, section=Section.MAIN):
    return [str(e.repo) for e in edition.entries(section)]


def candidates(count, prefix="user", section=Section.MAIN):
    """Candidates with descending scores and varied languages."""
    return [
        make_assessment(
            f"{prefix}{i}/project{i}",
            section=section,
            score=1.0 - i / 100,
            language=LANGUAGES[i % len(LANGUAGES)],
        )
        for i in range(count)
    ]


def test_edition_is_for_the_given_day():
    assert curate([]).day == TODAY


def test_best_scored_repos_come_first():
    edition = curate(
        [
            make_assessment("a/medium", score=0.5, language="Go"),
            make_assessment("b/best", score=0.9, language="Rust"),
            make_assessment("c/worst", score=0.1, language="C"),
        ]
    )

    assert names(edition) == ["b/best", "a/medium", "c/worst"]


def test_each_section_holds_at_most_the_best_twenty():
    edition = curate(candidates(ENTRIES_PER_SECTION + 5))

    assert names(edition) == [f"user{i}/project{i}" for i in range(ENTRIES_PER_SECTION)]


def test_repos_go_into_the_section_their_assessment_names():
    edition = curate(
        [
            make_assessment("alice/tiny-editor", section=Section.MAIN),
            make_assessment("bob/agent-kit", section=Section.AI),
        ]
    )

    assert names(edition, Section.MAIN) == ["alice/tiny-editor"]
    assert names(edition, Section.AI) == ["bob/agent-kit"]


def test_sections_are_filled_independently():
    edition = curate(
        candidates(ENTRIES_PER_SECTION, prefix="main")
        + candidates(ENTRIES_PER_SECTION, prefix="ai", section=Section.AI)
    )

    assert len(edition.entries(Section.MAIN)) == ENTRIES_PER_SECTION
    assert len(edition.entries(Section.AI)) == ENTRIES_PER_SECTION


def test_excluded_repos_are_never_selected():
    edition = curate(
        [
            make_assessment("alice/tiny-editor", score=0.1, language="Rust"),
            make_assessment("bob/fork", score=0.9, language="Go", exclusion=Exclusion("Fork")),
        ]
    )

    assert names(edition) == ["alice/tiny-editor"]


def test_repo_shown_within_cooldown_is_not_selected_again():
    shown = make_edition(day=TODAY - timedelta(days=COOLDOWN_DAYS - 1), main=["alice/tiny-editor"])

    edition = curate([make_assessment("alice/tiny-editor")], past_editions=[shown])

    assert names(edition) == []


def test_repo_may_return_once_the_cooldown_has_passed():
    shown = make_edition(day=TODAY - timedelta(days=COOLDOWN_DAYS), main=["alice/tiny-editor"])

    edition = curate([make_assessment("alice/tiny-editor")], past_editions=[shown])

    assert names(edition) == ["alice/tiny-editor"]


def test_cooldown_applies_regardless_of_the_section_the_repo_was_shown_in():
    shown = make_edition(day=TODAY - timedelta(days=1), ai=["alice/tiny-editor"])

    edition = curate([make_assessment("alice/tiny-editor", section=Section.MAIN)], past_editions=[shown])

    assert names(edition) == []


def test_language_limit_skips_further_repos_of_that_language_but_continues_selecting():
    rust = [
        make_assessment(f"rust{i}/project", score=0.9 - i / 100, language="Rust")
        for i in range(MAX_PER_LANGUAGE + 2)
    ]
    go = make_assessment("gopher/tool", score=0.1, language="Go")

    edition = curate(rust + [go])

    assert names(edition) == [f"rust{i}/project" for i in range(MAX_PER_LANGUAGE)] + ["gopher/tool"]


def test_repos_without_language_are_limited_like_one_language():
    unknown = [
        make_assessment(f"docs{i}/project", score=0.9 - i / 100, language=None)
        for i in range(MAX_PER_LANGUAGE + 1)
    ]

    edition = curate(unknown)

    assert len(names(edition)) == MAX_PER_LANGUAGE


def test_owner_limit_skips_further_repos_of_that_owner_but_continues_selecting():
    acme = [
        make_assessment(f"acme/tool{i}", score=0.9 - i / 100, language=LANGUAGES[i])
        for i in range(MAX_PER_OWNER + 2)
    ]
    other = make_assessment("gopher/tool", score=0.1, language="Go")

    edition = curate(acme + [other])

    assert names(edition) == [f"acme/tool{i}" for i in range(MAX_PER_OWNER)] + ["gopher/tool"]


def test_edition_states_how_many_repos_were_assessed_excluded_and_ai_focused():
    edition = curate(
        [
            make_assessment("a/gem", language="Go"),
            make_assessment("b/fork", language="C", exclusion=Exclusion("Fork")),
            make_assessment("c/agent", section=Section.AI, language="Python"),
            make_assessment("d/llm-fork", section=Section.AI, exclusion=Exclusion("Fork")),
            make_assessment("e/agent-kit", section=Section.AI, language="Rust"),
        ]
    )

    assert edition.stats == EditionStats(assessed=5, excluded=2, ai_focused=2)


def test_equal_scores_are_ranked_by_stars_gained_then_by_name():
    edition = curate(
        [
            make_assessment("b/second", score=0.5, gained=100, language="Go"),
            make_assessment("a/third", score=0.5, gained=50, language="C"),
            make_assessment("z/first", score=0.5, gained=300, language="Rust"),
            make_assessment("c/fourth", score=0.5, gained=50, language="Zig"),
        ]
    )

    assert names(edition) == ["z/first", "b/second", "a/third", "c/fourth"]


def test_edition_is_shorter_when_there_are_not_enough_candidates():
    edition = curate(candidates(3))

    assert len(edition.entries(Section.MAIN)) == 3
    assert edition.entries(Section.AI) == ()
