from datetime import UTC, datetime

import pytest

from builders import TODAY, make_assessment, make_edition, make_entry, star_history
from github_anti_ai.domain.edition import (
    ENTRIES_PER_SECTION,
    MAX_PER_LANGUAGE,
    MAX_PER_OWNER,
    Edition,
    EditionStats,
    Entry,
)
from github_anti_ai.domain.model import RepoId, Section, Signal

LANGUAGES = ["Rust", "Go", "C", "Zig", "Python", "Lua"]


def varied_entries(count, prefix="user"):
    """Entries whose languages never exceed the diversity limit."""
    return tuple(
        make_entry(f"{prefix}{i}/project{i}", language=LANGUAGES[i % len(LANGUAGES)])
        for i in range(count)
    )


def same_language_entries(count, language, prefix="user"):
    return tuple(make_entry(f"{prefix}{i}/project{i}", language=language) for i in range(count))


def test_entry_takes_over_what_the_page_shows_from_the_assessment():
    signal = Signal(kind="ai_assistance", weight=-0.2, reason="CLAUDE.md im Hauptverzeichnis")
    assessment = make_assessment("alice/tiny-editor", score=0.83, gained=120, signals=(signal,))

    entry = Entry.from_assessment(assessment)

    snapshot = assessment.snapshot
    assert entry.repo == RepoId.parse("alice/tiny-editor")
    assert entry.score == 0.83
    assert entry.signals == (signal,)
    assert entry.description == snapshot.description
    assert entry.homepage == snapshot.homepage
    assert entry.primary_language == "Rust"
    assert entry.topics == snapshot.topics
    assert entry.stars == snapshot.stars
    assert entry.star_history == star_history(120)
    assert entry.created_at == datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    assert entry.pushed_at == snapshot.pushed_at
    assert entry.license == "MIT"
    assert entry.forks == snapshot.forks
    assert entry.active_authors == 1


def test_edition_keeps_its_entries_in_ranking_order():
    entries = varied_entries(3)

    edition = Edition(day=TODAY, main=entries, ai=())

    assert edition.entries(Section.MAIN) == entries
    assert edition.entries(Section.AI) == ()


def test_edition_may_hold_the_full_number_of_entries_in_each_section():
    edition = Edition(
        day=TODAY,
        main=varied_entries(ENTRIES_PER_SECTION, prefix="main"),
        ai=varied_entries(ENTRIES_PER_SECTION, prefix="ai"),
    )

    assert len(edition.entries(Section.MAIN)) == ENTRIES_PER_SECTION
    assert len(edition.entries(Section.AI)) == ENTRIES_PER_SECTION


@pytest.mark.parametrize("section", ["main", "ai"])
def test_edition_with_too_many_entries_in_a_section_is_rejected(section):
    too_many = varied_entries(ENTRIES_PER_SECTION + 1)

    with pytest.raises(ValueError):
        Edition(day=TODAY, **{section: too_many})


def test_edition_with_too_many_entries_of_one_language_is_rejected():
    with pytest.raises(ValueError):
        Edition(day=TODAY, main=same_language_entries(MAX_PER_LANGUAGE + 1, "Rust"), ai=())


def test_language_limit_applies_to_each_section_separately():
    edition = Edition(
        day=TODAY,
        main=same_language_entries(MAX_PER_LANGUAGE, "Rust", prefix="main"),
        ai=same_language_entries(MAX_PER_LANGUAGE, "Rust", prefix="ai"),
    )

    assert len(edition.entries(Section.MAIN)) == MAX_PER_LANGUAGE


def test_repos_without_language_count_as_one_group_for_the_language_limit():
    with pytest.raises(ValueError):
        Edition(day=TODAY, main=same_language_entries(MAX_PER_LANGUAGE + 1, None), ai=())


def test_edition_with_too_many_repos_of_one_owner_in_a_section_is_rejected():
    same_owner = tuple(
        make_entry(f"acme/tool{i}", language=LANGUAGES[i]) for i in range(MAX_PER_OWNER + 1)
    )

    with pytest.raises(ValueError):
        Edition(day=TODAY, main=same_owner, ai=())


def test_owner_limit_ignores_case_and_applies_to_each_section_separately():
    with pytest.raises(ValueError):
        Edition(
            day=TODAY,
            main=tuple(
                make_entry(f"{owner}/tool{i}", language=LANGUAGES[i])
                for i, owner in enumerate(["acme", "ACME", "Acme"][: MAX_PER_OWNER + 1])
            ),
        )

    edition = Edition(
        day=TODAY,
        main=tuple(make_entry(f"acme/tool{i}", language=LANGUAGES[i]) for i in range(MAX_PER_OWNER)),
        ai=tuple(make_entry(f"acme/agent{i}", language=LANGUAGES[i]) for i in range(MAX_PER_OWNER)),
    )
    assert len(edition.entries(Section.AI)) == MAX_PER_OWNER


def test_edition_carries_statistics_of_the_day():
    stats = EditionStats(assessed=1834, excluded=420, ai_focused=212)

    assert Edition(day=TODAY, stats=stats).stats == stats
    assert Edition(day=TODAY).stats == EditionStats(assessed=0, excluded=0, ai_focused=0)


def test_repo_listed_twice_in_a_section_is_rejected():
    with pytest.raises(ValueError):
        Edition(day=TODAY, main=(make_entry("alice/tiny-editor"), make_entry("alice/tiny-editor")), ai=())


def test_repo_listed_in_both_sections_is_rejected():
    with pytest.raises(ValueError):
        Edition(
            day=TODAY,
            main=(make_entry("alice/tiny-editor"),),
            ai=(make_entry("Alice/Tiny-Editor"),),
        )


def test_edition_knows_which_repos_it_shows():
    edition = make_edition(main=["alice/tiny-editor"], ai=["bob/agent-kit"])

    assert edition.shows(RepoId.parse("alice/tiny-editor"))
    assert edition.shows(RepoId.parse("bob/agent-kit"))
    assert not edition.shows(RepoId.parse("carol/plotter"))
