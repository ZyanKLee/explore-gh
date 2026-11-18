from datetime import timedelta

import pytest
from builders import TODAY, make_assessment, make_edition, make_entry

from explore_gh.domain.edition import Edition, EditionCurator, EditionStats, Entry
from explore_gh.domain.model import Exclusion, RepoId, Section

curator = EditionCurator()


def names(entries):
    return [str(entry.repo) for entry in entries]


class TestEdition:
    def test_refuses_more_than_20_entries_per_section(self):
        with pytest.raises(ValueError):
            make_edition(main=[make_entry(f"o{i}/r", language=f"L{i}") for i in range(21)])

    def test_refuses_more_than_4_entries_of_a_language(self):
        with pytest.raises(ValueError):
            make_edition(ai=[make_entry(f"o{i}/r") for i in range(5)])

    def test_refuses_more_than_2_repos_of_an_owner(self):
        with pytest.raises(ValueError):
            make_edition(main=[make_entry(f"alice/r{i}", language=f"L{i}") for i in range(3)])

    def test_refuses_a_repo_twice_even_across_sections(self):
        with pytest.raises(ValueError):
            make_edition(main=["alice/tiny"], ai=["Alice/Tiny"])

    def test_ranks_count_from_1_in_each_section(self):
        edition = make_edition(main=["a/x", "b/y"], ai=["c/z"])

        assert edition.ranks() == {
            RepoId.parse("a/x"): 1,
            RepoId.parse("b/y"): 2,
            RepoId.parse("c/z"): 1,
        }


class TestEntry:
    def test_takes_what_the_page_shows_from_the_assessment(self):
        entry = Entry.from_assessment(make_assessment("alice/tiny", score=42, gained=150))

        assert entry.score == 42
        assert entry.star_history.gained() == 150
        assert entry.primary_language == "Rust"
        assert entry.active_authors == 1


class TestEditionCurator:
    def test_sorts_by_score(self):
        edition = curator.curate(
            TODAY,
            [
                make_assessment("a/low", score=1, language="Go"),
                make_assessment("b/high", score=9, language="C"),
            ],
            [],
        )

        assert names(edition.main) == ["b/high", "a/low"]

    def test_on_a_tie_more_new_stars_then_the_name_win(self):
        edition = curator.curate(
            TODAY,
            [
                make_assessment("c/x", score=5, gained=100, language="Go"),
                make_assessment("b/x", score=5, gained=200, language="C"),
                make_assessment("A/x", score=5, gained=100, language="Zig"),
            ],
            [],
        )

        assert names(edition.main) == ["b/x", "A/x", "c/x"]

    def test_separates_the_sections(self):
        edition = curator.curate(
            TODAY,
            [make_assessment("a/main"), make_assessment("b/ai", section=Section.AI)],
            [],
        )

        assert names(edition.main) == ["a/main"]
        assert names(edition.ai) == ["b/ai"]

    def test_leaves_out_excluded_repos(self):
        edition = curator.curate(
            TODAY, [make_assessment("a/x", exclusion=Exclusion("Fork", "fork"))], []
        )

        assert edition.main == ()

    def test_leaves_out_repos_shown_in_the_last_30_days(self):
        past = [
            make_edition(TODAY - timedelta(days=29), main=["a/recent"]),
            make_edition(TODAY - timedelta(days=30), ai=["b/old"]),
        ]
        edition = curator.curate(
            TODAY,
            [make_assessment("a/recent", language="Go"), make_assessment("b/old", language="C")],
            past,
        )

        assert names(edition.main) == ["b/old"]

    def test_keeps_the_variety_rule(self):
        assessments = [make_assessment(f"o{i}/r", score=10 - i) for i in range(6)]

        assert len(curator.curate(TODAY, assessments, []).main) == 4

    def test_counts_the_repos_of_the_day(self):
        edition = curator.curate(
            TODAY,
            [
                make_assessment("a/x", language="Go"),
                make_assessment("b/x", section=Section.AI),
                make_assessment("c/x", section=Section.AI, exclusion=Exclusion("Fork", "fork")),
            ],
            [],
        )

        assert edition.stats == EditionStats(assessed=3, excluded=1, ai_focused=1)


def test_edition_is_the_aggregate_of_entries():
    assert isinstance(make_edition(main=["a/x"]), Edition)
