from datetime import date, timedelta

import pytest
from publication_samples import (
    community_edition_json,
    edition_json,
    entry_json,
    project_json,
    write_json,
)

from github_anti_ai.publication.community_view import (
    FORUMS,
    HN,
    LOBSTERS,
    community_feed_html,
    load_community_editions,
)
from github_anti_ai.publication.german import age, decimal, long_date, number, weight
from github_anti_ai.publication.view import (
    feed_html,
    load_github_days,
    section_view,
    sparkline_points,
)


class TestGerman:
    def test_numbers_have_a_thousands_point(self):
        assert number(91943) == "91.943"

    @pytest.mark.parametrize("value, text", [(40, "+40,0"), (-3, "−3,0"), (0, "0"), (0.04, "+0,0")])
    def test_weights_carry_their_sign_and_a_comma(self, value, text):
        assert weight(value) == text

    def test_scores_have_one_decimal(self):
        assert (decimal(37), decimal(-2.25)) == ("37,0", "−2,2")

    def test_long_date(self):
        assert long_date(date(2026, 3, 1)) == "1. März 2026"

    @pytest.mark.parametrize(
        "days, text", [(0, "heute erstellt"), (1, "1 Tag alt"), (23, "23 Tage alt")]
    )
    def test_age(self, days, text):
        assert age(date(2026, 11, 12) - timedelta(days=days), date(2026, 11, 12)) == text


class TestGitHubView:
    def test_title_address_and_stats_of_a_section(self):
        view = section_view(edition_json(), "ai")

        assert view.title == "AI-Projekte auf GitHub vom 12. November 2026"
        assert view.url == "ai/2026/11/12/"
        assert view.stats == "1.834 Repos geprüft, 420 ausgeschlossen, 212 als AI-Thema eingestuft"
        assert [e.repo for e in view.entries] == ["bob/agent-kit"]

    def test_an_entry_shows_numbers_the_german_way(self):
        entry = section_view(edition_json(), "main").entries[0]

        assert (entry.stars, entry.gained, entry.gained_days, entry.score) == (
            "91.943",
            "+120",
            14,
            "37,0",
        )
        assert entry.age == "23 Tage alt"
        assert [line.weight for line in entry.signals] == ["+40,0", "−3,0", "0"]

    def test_older_editions_counted_the_gain_over_7_days(self):
        old = edition_json()
        del old["growth_window_days"]

        assert section_view(old, "main").entries[0].gained_days == 7

    def test_only_web_addresses_become_homepage_links_and_noassertion_is_no_license(self):
        main = [entry_json(homepage="javascript:alert(1)", license="NOASSERTION")]

        entry = section_view(edition_json(main=main), "main").entries[0]

        assert (entry.homepage, entry.license) == (None, None)

    def test_the_sparkline_puts_the_best_day_at_the_top(self):
        assert sparkline_points([0, 5, 10], 120, 24) == "0,24 60,12 120,0"
        assert sparkline_points([0, 0], 120, 24) == "0,24 120,24"

    def test_the_feed_lists_the_entries_and_escapes_them(self):
        main = [entry_json(description="<script>")]

        html = feed_html(section_view(edition_json(main=main), "main"))

        assert "&lt;script&gt;" in html
        assert "+120 in 14 Tagen" in html
        assert (
            feed_html(section_view(edition_json(main=[]), "main"))
            == "<p>Heute nichts gefunden.</p>"
        )

    def test_days_are_loaded_oldest_first_and_other_files_ignored(self, tmp_path):
        write_json(tmp_path / "2026-11-13.json", edition_json("2026-11-13"))
        write_json(tmp_path / "2026-11-12.json", edition_json("2026-11-12"))
        write_json(tmp_path / "notes.json", {})

        assert [d.day.day for d in load_github_days(tmp_path)] == [12, 13]

    def test_an_unknown_format_stops_the_build(self, tmp_path):
        write_json(tmp_path / "2026-11-12.json", edition_json(format_version=2))

        with pytest.raises(ValueError, match="format_version"):
            load_github_days(tmp_path)


class TestCommunityView:
    def test_hn_and_lobsters_name_their_points_and_discussion(self, tmp_path):
        lobsters_project = project_json()
        lobsters_project["story"] = {
            **lobsters_project["story"],
            "score": 12,
            "discussion_url": "https://lobste.rs/s/x",
        }
        del lobsters_project["story"]["points"]
        write_json(tmp_path / "hn" / "2026-11-12.json", community_edition_json())
        write_json(
            tmp_path / "lobsters" / "2026-11-12.json",
            community_edition_json(projects=[lobsters_project]),
        )

        (hn,) = load_community_editions(tmp_path / "hn", HN)
        (lobsters,) = load_community_editions(tmp_path / "lobsters", LOBSTERS)

        assert hn.main.title == "Trending auf HN vom 12. November 2026"
        assert hn.main.url == "hn/2026/11/12/"
        assert hn.ai.url == "hn/ai/2026/11/12/"
        assert hn.main.entries[0].discussion_url == "https://news.ycombinator.com/item?id=4711"
        assert (hn.main.entries[0].points, hn.main.points_label) == ("321", "HN-Punkte")
        assert lobsters.main.entries[0].discussion_url == "https://lobste.rs/s/x"
        assert lobsters.main.discussion_label == "Diskussion auf Lobsters"

    def test_the_forums_list_names_points_and_discussion_of_each_origin(self, tmp_path):
        forums_project = project_json()
        forums_project["story"] |= {
            "url": "",
            "points": 3,
            "discussion_url": "https://fosstodon.org/@a/1",
            "origin": {"name": "Mastodon #rust", "reference_points": 5, "min_points": 0,
                       "points_label": "Reaktionen"},
        }  # fmt: skip
        write_json(
            tmp_path / "2026-11-16.json",
            community_edition_json("2026-11-16", projects=[forums_project]),
        )

        (week,) = load_community_editions(tmp_path, FORUMS)

        assert week.main.title == "Trending in den Foren, Woche vom 16. November 2026"
        assert week.main.url == "forums/2026/11/16/"
        entry = week.main.entries[0]
        assert (entry.points, entry.points_label) == ("3", "Reaktionen auf Mastodon #rust")
        assert entry.discussion_label == "Diskussion auf Mastodon #rust"
        assert entry.discussion_url == "https://fosstodon.org/@a/1"
        assert week.main.empty_text == "Diese Woche nichts gefunden"

    def test_hn_entries_carry_the_labels_of_their_platform(self, tmp_path):
        write_json(tmp_path / "2026-11-12.json", community_edition_json())

        (day,) = load_community_editions(tmp_path, HN)

        entry = day.main.entries[0]
        assert (entry.points_label, entry.discussion_label) == ("HN-Punkte", "Diskussion auf HN")
        assert day.main.empty_text == "Heute nichts gefunden"

    def test_the_stats_count_projects(self, tmp_path):
        write_json(tmp_path / "2026-11-12.json", community_edition_json())

        (day,) = load_community_editions(tmp_path, HN)

        assert (day.main.stats, day.ai.stats) == ("1 Open-Source-Projekt", "0 AI-Projekte")

    def test_editions_before_the_ai_section_have_an_empty_one(self, tmp_path):
        old = community_edition_json()
        del old["ai_projects"]
        write_json(tmp_path / "2026-11-12.json", old)

        assert load_community_editions(tmp_path, HN)[0].ai.entries == []

    def test_only_web_addresses_become_links(self, tmp_path):
        write_json(
            tmp_path / "2026-11-12.json",
            community_edition_json(projects=[project_json(project_url="javascript:x")]),
        )

        assert load_community_editions(tmp_path, HN)[0].main.entries[0].project_url is None

    def test_the_feed_links_repo_and_discussion(self, tmp_path):
        write_json(tmp_path / "2026-11-12.json", community_edition_json())

        html = community_feed_html(load_community_editions(tmp_path, HN)[0].main)

        assert "https://github.com/alice/tiny-editor" in html
        assert "Diskussion auf HN" in html
