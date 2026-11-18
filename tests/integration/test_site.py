"""The built site: pages, navigation, feeds and safety."""

import re

import pytest
from publication_samples import (
    community_edition_json,
    edition_json,
    entry_json,
    project_json,
    write_community_edition,
    write_edition,
)

from github_anti_ai.publication.site import build_site


@pytest.fixture
def site(tmp_path):
    """Builds a site from the editions written into data/ and returns a page reader."""
    data, output = tmp_path / "data", tmp_path / "output"

    def build(**options):
        build_site(data, output, **options)
        return lambda path: (output / path).read_text(encoding="utf-8")

    build.data = data
    return build


def two_days(data):
    write_edition(data, edition_json("2026-11-12"))
    write_edition(
        data,
        edition_json(
            "2026-11-13",
            main=[entry_json("carol/new-tool")],
            ai=[entry_json("dave/llm", language="Python")],
        ),
    )


def test_the_start_page_shows_the_main_list_of_the_newest_day(site):
    two_days(site.data)
    page = site()

    start = page("index.html")
    assert "Trending auf GitHub vom 13. November 2026" in start
    assert "carol/" in start and "dave/" not in start


def test_every_day_and_section_has_its_own_page(site):
    two_days(site.data)
    page = site()

    assert "alice/" in page("2026/11/12/index.html")
    assert "bob/" in page("ai/2026/11/12/index.html")
    assert "dave/" in page("ai/index.html")


def test_day_pages_link_their_neighbours_the_other_section_and_the_archive(site):
    two_days(site.data)
    page = site()

    older = page("2026/11/12/index.html")
    assert 'rel="next" href="../../../2026/11/13/"' in older
    assert 'href="../../../ai/2026/11/12/">AI-Projekte dieses Tages' in older
    assert 'href="../../../archiv/">Archiv' in older


def test_the_archive_lists_all_days_newest_first(site):
    two_days(site.data)
    archive = site()("archiv/index.html")

    assert archive.index("13. November 2026") < archive.index("12. November 2026")
    assert "1 Repo" in archive and "1 AI-Repo" in archive


def test_an_entry_explains_its_rank_in_the_page_itself(site):
    write_edition(site.data, edition_json())
    start = site()("index.html")

    assert "<details" in start
    assert "Warum Platz 1?" in start
    assert "+40,0" in start and "−3,0" in start
    assert "Anweisungsdateien für AI-Agenten: AGENTS.md" in start
    assert "+120</mark> Sterne in 14 Tagen" in start
    assert "1.834 Repos geprüft" in start


def test_text_from_strangers_is_never_read_as_html(site):
    write_edition(
        site.data, edition_json(main=[entry_json(description="<script>alert(1)</script>")])
    )
    start = site()("index.html")

    assert "<script>alert" not in start
    assert "&lt;script&gt;" in start


def test_the_site_needs_no_script_and_loads_nothing_from_other_servers(site):
    write_edition(site.data, edition_json())
    start = site()("index.html")

    assert "<script" not in start
    assert not re.search(
        r'(src|href)="https?://(?!github\.com)', start.replace('href="https://github.com', "")
    )
    assert "Ohne Tracking, ohne Skripte." in start


def links(html):
    return re.findall(r"<a\s[^>]*>", html)


def test_links_to_other_sites_open_a_new_tab_and_links_within_the_site_do_not(site):
    write_edition(site.data, edition_json(main=[entry_json(homepage="https://tiny.example")]))
    write_community_edition(site.data, "hn", community_edition_json())
    page = site()

    for path in ("index.html", "hn/index.html"):
        found = links(page(path))
        external = [link for link in found if 'href="http' in link]
        assert len(external) >= 2, path
        for link in external:
            assert 'target="_blank"' in link and 'rel="noopener noreferrer"' in link, link
        for link in set(found) - set(external):
            assert "target=" not in link, link


def test_a_counted_site_loads_plausible_on_every_page_but_never_in_a_feed(site):
    write_edition(site.data, edition_json())
    page = site(plausible_script="https://stats.example.org/js/x.js")

    assert 'src="https://stats.example.org/js/x.js"' in page("index.html")
    assert "Besuche zählt Plausible" in page("archiv/index.html")
    assert "<script" not in page("feed.xml")


def test_the_plausible_script_must_come_over_https(site):
    with pytest.raises(ValueError):
        site(plausible_script="http://stats.example.org/x.js")


def test_main_and_ai_feed_are_separate_with_one_entry_per_day(site):
    two_days(site.data)
    page = site()

    main, ai = page("feed.xml"), page("ai/feed.xml")
    assert main.count("<entry>") == 2 and ai.count("<entry>") == 2
    assert "carol/new-tool" in main and "dave/llm" not in main
    assert "dave/llm" in ai


def test_feeds_of_a_site_with_an_address_link_in_full_and_pages_stay_relative(site):
    write_edition(site.data, edition_json())
    page = site(site_url="https://example.org/explore/")

    assert 'href="https://example.org/explore/2026/11/12/"' in page("feed.xml")
    assert 'href="https://example.org/explore/ai/2026/11/12/"' in page("ai/feed.xml")
    assert 'href="./theme/css/style.css"' in page("index.html")


def test_an_empty_section_and_a_site_without_editions_say_so(site):
    page = site()
    assert "Noch keine Ausgabe" in page("index.html")
    assert "Noch keine Ausgabe" in page("hn/index.html")

    write_edition(site.data, edition_json(ai=[]))
    assert "Heute nichts gefunden" in site()("ai/index.html")


def test_every_page_links_the_favicon_and_it_is_part_of_the_site(site, tmp_path):
    write_edition(site.data, edition_json())
    page = site()

    assert 'rel="icon"' in page("index.html")
    assert (tmp_path / "output" / "theme" / "favicon.svg").exists()


class TestCommunityLists:
    @pytest.mark.parametrize("slug, name", [("hn", "HN"), ("lobsters", "Lobsters")])
    def test_each_platform_has_its_pages_archive_and_feeds(self, site, slug, name):
        def project(*args):
            data = project_json(*args)
            if slug == "lobsters":  # Lobsters calls the points "score"
                story = data["story"]
                data["story"] = {
                    **story,
                    "score": story.pop("points"),
                    "discussion_url": "https://lobste.rs/s/x",
                }
            return data

        write_community_edition(
            site.data,
            slug,
            community_edition_json(
                projects=[project()], ai_projects=[project("LLM", "https://github.com/a/llm")]
            ),
        )
        page = site()

        latest = page(f"{slug}/index.html")
        assert f"Trending auf {name} vom 12. November 2026" in latest
        assert f"Diskussion auf {name}" in latest
        assert "Warum Platz 1?" in latest
        assert "a/llm" not in latest
        assert "a/llm" in page(f"{slug}/ai/index.html")
        assert "tiny-editor" in page(f"{slug}/2026/11/12/index.html")
        assert f"{name}-Archiv" in page(f"{slug}/archiv/index.html")
        assert page(f"{slug}/feed.xml").count("<entry>") == 1
        assert "a/llm" in page(f"{slug}/ai/feed.xml")

    def test_the_weekly_forums_list_has_its_pages_and_feeds(self, site):
        data = project_json()
        data["story"] |= {
            "discussion_url": "https://lobste.rs/s/x",
            "origin": {"name": "Lobsters", "reference_points": 10, "min_points": 10,
                       "points_label": "Punkte"},
        }  # fmt: skip
        write_community_edition(
            site.data, "forums", community_edition_json("2026-11-09", projects=[data])
        )
        page = site()

        latest = page("forums/index.html")
        assert "Trending in den Foren, Woche vom 9. November 2026" in latest
        assert "321 Punkte auf Lobsters" in latest
        assert "Diskussion auf Lobsters" in latest
        assert "Diese Woche nichts gefunden" in page("forums/ai/index.html")
        assert page("forums/feed.xml").count("<entry>") == 1

    def test_the_main_navigation_names_the_three_platforms_and_marks_the_current(self, site):
        write_community_edition(site.data, "hn", community_edition_json())
        page = site()

        hn = page("hn/2026/11/12/index.html")
        assert re.search(r'href="[./]*/hn/" aria-current="page">Trending auf HN', hn)
        assert "Trending auf GitHub</a>" in hn and "Trending in den Foren</a>" in hn
        assert "Trending auf Lobsters</a>" not in hn  # its archive stays, without a link
        assert re.search(r'aria-current="page">Trending auf GitHub', page("archiv/index.html"))
