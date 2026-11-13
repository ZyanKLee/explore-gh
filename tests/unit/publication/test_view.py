from datetime import date

import pytest

from github_anti_ai.publication.view import load_editions, section_view, sparkline_points
from publication_samples import edition_json, entry_json, write_edition


def main_view(**entry_overrides):
    return section_view(edition_json(main=[entry_json(**entry_overrides)]), "main")


def first_entry(**entry_overrides):
    return main_view(**entry_overrides).entries[0]


def test_main_list_and_ai_section_get_their_own_title_and_address():
    edition = edition_json()

    main, ai = section_view(edition, "main"), section_view(edition, "ai")

    assert main.day == date(2026, 11, 12)
    assert main.title == "Trending auf GitHub vom 12. November 2026"
    assert ai.title == "AI-Projekte auf GitHub vom 12. November 2026"
    assert main.url == "2026/11/12/"
    assert ai.url == "ai/2026/11/12/"


def test_each_section_lists_only_its_own_repos_in_ranking_order():
    edition = edition_json(
        main=[entry_json("a/first", rank=1), entry_json("b/second", rank=2)],
        ai=[entry_json("c/agent", rank=1)],
    )

    assert [e.repo for e in section_view(edition, "main").entries] == ["a/first", "b/second"]
    assert [e.repo for e in section_view(edition, "ai").entries] == ["c/agent"]


def test_empty_section_has_no_entries():
    assert section_view(edition_json(ai=[]), "ai").entries == []


def test_statistics_of_the_day_are_put_into_words():
    assert main_view().stats == "1.834 Repos geprüft, 420 ausgeschlossen, 212 als AI-Thema eingestuft"


def test_entry_links_to_the_repo():
    entry = first_entry()

    assert entry.repo == "alice/tiny-editor"
    assert entry.url == "https://github.com/alice/tiny-editor"
    assert entry.rank == 1
    assert entry.description == "A tiny terminal text editor"


def test_numbers_are_written_the_german_way():
    entry = first_entry()

    assert entry.stars == "91.943"
    assert entry.gained == "+120"
    assert entry.forks == "31"


def test_score_and_weights_carry_sign_and_decimal_comma():
    entry = first_entry()

    assert entry.score == "37,0"
    assert [(line.weight, line.reason) for line in entry.signals] == [
        ("+40,0", "+120 Sterne in 7 Tagen bei 91.943 insgesamt"),
        ("−3,0", "Anweisungsdateien für AI-Agenten: AGENTS.md"),
        ("0", "Beschreibung nennt „AI“"),
    ]


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("2026-10-20T12:00:00Z", "23 Tage alt"),
        ("2026-11-11T08:00:00Z", "1 Tag alt"),
        ("2026-11-12T03:00:00Z", "heute erstellt"),
    ],
)
def test_age_is_counted_in_days_up_to_the_day_of_the_edition(created_at, expected):
    assert first_entry(created_at=created_at).age == expected


def test_missing_optional_facts_are_left_out():
    entry = first_entry(language=None, license=None, homepage=None, description="")

    assert entry.language is None
    assert entry.license is None
    assert entry.homepage is None
    assert entry.description == ""


def test_placeholder_for_an_unrecognized_license_is_not_shown_as_a_license():
    # GitHub reports NOASSERTION when there is a license file it cannot identify
    assert first_entry(license="NOASSERTION").license is None
    assert first_entry(license="MIT").license == "MIT"


@pytest.mark.parametrize("homepage", ["https://tiny-editor.example.org", "http://example.org/x"])
def test_web_homepages_are_linked(homepage):
    assert first_entry(homepage=homepage).homepage == homepage


@pytest.mark.parametrize(
    "homepage", ["javascript:alert(1)", "data:text/html,<script>1</script>", "ftp://example.org", ""]
)
def test_anything_but_a_web_address_is_not_linked_as_homepage(homepage):
    assert first_entry(homepage=homepage).homepage is None


def test_star_history_becomes_a_curve_with_one_point_per_day():
    points = first_entry().sparkline.split()

    assert len(points) == 35
    assert all(len(point.split(",")) == 2 for point in points)


def test_curve_spans_the_drawing_area_from_bottom_to_top():
    points = sparkline_points([0, 5, 10], width=100, height=20).split()

    assert points == ["0,20", "50,10", "100,0"]


def test_curve_of_a_history_without_stars_is_a_flat_line_at_the_bottom():
    assert sparkline_points([0, 0, 0], width=100, height=20).split() == ["0,20", "50,20", "100,20"]


def test_editions_are_loaded_in_date_order(tmp_path):
    for day in ("2026-11-12", "2026-11-10", "2026-11-11"):
        write_edition(tmp_path, edition_json(day=day))
    (tmp_path / "README.md").write_text("not an edition")
    (tmp_path / "notes.json").write_text("{}")

    assert [e["day"] for e in load_editions(tmp_path)] == ["2026-11-10", "2026-11-11", "2026-11-12"]


def test_missing_editions_directory_means_no_editions(tmp_path):
    assert load_editions(tmp_path / "nothing-here") == []


def test_edition_in_an_unknown_format_stops_the_build(tmp_path):
    write_edition(tmp_path, edition_json(format_version=2))

    with pytest.raises(ValueError, match="format_version"):
        load_editions(tmp_path)
