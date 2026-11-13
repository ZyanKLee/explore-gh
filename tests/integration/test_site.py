"""Builds the whole site with Pelican from edition files and reads what comes out."""

import re

import pytest

from builders import TODAY, make_entry
from github_anti_ai.adapters.json_edition_store import JsonEditionStore
from github_anti_ai.domain.edition import Edition, EditionStats
from github_anti_ai.domain.model import Section, Signal
from github_anti_ai.publication.site import build_site
from publication_samples import edition_json, entry_json, write_edition

NEW, OLD = "2026-11-12", "2026-11-11"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    editions = tmp_path_factory.mktemp("editions")
    output = tmp_path_factory.mktemp("output")
    write_edition(
        editions,
        edition_json(
            day=OLD,
            main=[entry_json("old/gem", description="Yesterday's find")],
            ai=[entry_json("old/agent")],
        ),
    )
    write_edition(
        editions,
        edition_json(
            day=NEW,
            main=[
                entry_json("alice/tiny-editor", rank=1, homepage="https://tiny-editor.example.org"),
                entry_json("mallory/xss", rank=2, description='<script>alert("x")</script> & more',
                           homepage="javascript:alert(1)"),
            ],
            ai=[entry_json("bob/agent-kit", language="Python")],
        ),
    )
    build_site(editions, output)
    return output


def page(site, path):
    return (site / path).read_text(encoding="utf-8")


def test_start_page_shows_the_main_list_of_the_newest_edition(site):
    html = page(site, "index.html")

    assert "Trending auf GitHub vom 12. November 2026" in html
    assert "alice/tiny-editor" in html
    assert "old/gem" not in html


def test_ai_repos_never_appear_on_the_main_list(site):
    assert "bob/agent-kit" not in page(site, "index.html")
    assert "bob/agent-kit" not in page(site, "2026/11/12/index.html")


def test_ai_section_has_its_own_pages(site):
    html = page(site, "ai/index.html")

    assert "AI-Projekte auf GitHub vom 12. November 2026" in html
    assert "bob/agent-kit" in html
    assert "alice/tiny-editor" not in html
    assert "old/agent" in page(site, "ai/2026/11/11/index.html")


def test_every_day_keeps_its_own_page(site):
    assert "old/gem" in page(site, "2026/11/11/index.html")
    assert "alice/tiny-editor" in page(site, "2026/11/12/index.html")


def test_day_pages_link_to_their_neighbours_and_to_the_other_section(site):
    older, newer = page(site, "2026/11/11/index.html"), page(site, "2026/11/12/index.html")

    assert "2026/11/12/" in older
    assert "2026/11/11/" in newer
    assert "ai/2026/11/12/" in newer


def test_archive_lists_all_days_newest_first_with_both_sections(site):
    html = page(site, "archiv/index.html")

    assert html.index("12. November 2026") < html.index("11. November 2026")
    for address in ("2026/11/12/", "ai/2026/11/12/", "2026/11/11/", "ai/2026/11/11/"):
        assert address in html


def main_navigation(html):
    return re.search(r'<nav aria-label="Bereiche">(.*?)</nav>', html, re.S).group(1)


def test_main_navigation_names_only_the_three_platforms(site):
    nav = main_navigation(page(site, "index.html"))

    assert re.findall(r">([^<]+)</a>", nav) == [
        "Trending auf GitHub", "Trending auf HN", "Trending auf Lobsters",
    ]


@pytest.mark.parametrize(
    "path", ["index.html", "ai/index.html", "archiv/index.html", "2026/11/11/index.html",
             "ai/2026/11/11/index.html"],
)
def test_every_github_page_marks_trending_on_github_as_current(site, path):
    nav = main_navigation(page(site, path))

    assert re.search(r'aria-current="page">Trending auf GitHub</a>', nav)
    assert nav.count("aria-current") == 1


@pytest.mark.parametrize("path", ["index.html", "2026/11/12/index.html", "ai/index.html"])
def test_github_pages_link_the_other_section_and_the_archive_themselves(site, path):
    html = page(site, path)

    assert re.search(r'href="[./]*archiv/">Archiv</a>', html)
    other = "AI-Projekte" if not path.startswith("ai/") else "Trending"
    assert f">{other} dieses Tages</a>" in html


def test_github_archive_names_both_sections_of_each_day(site):
    html = page(site, "archiv/index.html")

    assert "GitHub-Archiv" in html
    assert re.search(r'href="[./]*2026/11/12/">2 Repos</a>', html)
    assert re.search(r'href="[./]*ai/2026/11/12/">1 AI-Repo</a>', html)


def test_entry_shows_its_facts(site):
    html = page(site, "index.html")

    for text in ("https://github.com/alice/tiny-editor", "A tiny terminal text editor", "Rust",
                 "91.943", "+120", "MIT", "https://tiny-editor.example.org"):
        assert text in html
    assert "<polyline" in html


def test_assessment_is_explained_in_the_page_itself(site):
    html = page(site, "index.html")

    assert "37,0" in html
    assert "+40,0" in html
    assert "+120 Sterne in 7 Tagen bei 91.943 insgesamt" in html
    assert "Anweisungsdateien für AI-Agenten: AGENTS.md" in html


def test_statistics_of_the_day_are_shown(site):
    assert "1.834 Repos geprüft, 420 ausgeschlossen, 212 als AI-Thema eingestuft" in page(site, "index.html")


def test_text_from_github_is_never_interpreted_as_html(site):
    html = page(site, "index.html")

    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;" in html
    assert "javascript:alert" not in html


@pytest.mark.parametrize(
    ("path", "favicon"),
    [("index.html", "./theme/favicon.svg"), ("archiv/index.html", "../theme/favicon.svg"),
     ("ai/2026/11/11/index.html", "../../../../theme/favicon.svg")],
)
def test_every_page_links_the_favicon(site, path, favicon):
    assert f'<link rel="icon" href="{favicon}" type="image/svg+xml">' in page(site, path)


def test_favicon_is_part_of_the_site(site):
    assert page(site, "theme/favicon.svg").startswith("<svg")


def test_site_needs_no_script_and_loads_nothing_from_other_servers(site):
    for path in ("index.html", "ai/index.html", "archiv/index.html", "2026/11/11/index.html"):
        html = page(site, path)
        assert "<script" not in html.replace("&lt;script", "")
        loaded = re.findall(r'<(?:link|img|iframe|source)[^>]+(?:href|src)="([^"]+)"', html)
        assert [address for address in loaded if address.startswith(("http:", "https:", "//"))] == []


def test_main_feed_and_ai_feed_are_separate(site):
    main_feed, ai_feed = page(site, "feed.xml"), page(site, "ai/feed.xml")

    assert "alice/tiny-editor" in main_feed and "old/gem" in main_feed
    assert "bob/agent-kit" not in main_feed
    assert "bob/agent-kit" in ai_feed and "old/agent" in ai_feed
    assert "alice/tiny-editor" not in ai_feed


def test_feed_has_one_entry_per_day(site):
    assert page(site, "feed.xml").count("<entry>") == 2


def test_empty_section_says_so(tmp_path):
    write_edition(tmp_path / "editions", edition_json(ai=[]))

    build_site(tmp_path / "editions", tmp_path / "output")

    assert "Heute nichts gefunden</p>" in page(tmp_path / "output", "ai/index.html")


def test_site_without_any_edition_says_so(tmp_path):
    build_site(tmp_path / "editions", tmp_path / "output")

    assert "Noch keine Ausgabe</p>" in page(tmp_path / "output", "index.html")


def test_editions_written_by_the_edition_store_can_be_published(tmp_path):
    # guards the contract between Curation and Publication
    signal = Signal(kind="momentum", weight=40.0, reason="+120 Sterne in 7 Tagen bei 812 insgesamt")
    edition = Edition(
        day=TODAY,
        main=(make_entry("alice/tiny-editor", score=40.0, signals=(signal,)),),
        ai=(make_entry("bob/agent-kit", section=Section.AI, language="Python"),),
        stats=EditionStats(assessed=10, excluded=3, ai_focused=2),
    )
    JsonEditionStore(tmp_path / "editions").save(edition)

    build_site(tmp_path / "editions", tmp_path / "output")

    html = page(tmp_path / "output", "index.html")
    assert "alice/tiny-editor" in html
    assert "+120 Sterne in 7 Tagen bei 812 insgesamt" in html
    assert "10 Repos geprüft, 3 ausgeschlossen, 2 als AI-Thema eingestuft" in html


# --- the address of the site, for the feeds -------------------------------------------

ADDRESS = "https://example.org/fundstuecke"


@pytest.fixture(scope="module")
def addressed_site(tmp_path_factory):
    editions = tmp_path_factory.mktemp("editions")
    output = tmp_path_factory.mktemp("output")
    write_edition(editions, edition_json(day=NEW, main=[entry_json("alice/tiny-editor")]))
    build_site(editions, output, site_url=ADDRESS + "/")
    return output


def test_feed_of_a_site_with_an_address_links_to_the_days_in_full(addressed_site):
    feed = page(addressed_site, "feed.xml")

    assert f'<link href="{ADDRESS}/2026/11/12/" rel="alternate"/>' in feed
    assert f'<link href="{ADDRESS}/feed.xml" rel="self"/>' in feed


def test_ai_feed_of_a_site_with_an_address_links_in_full_too(addressed_site):
    feed = page(addressed_site, "ai/feed.xml")

    assert f'<link href="{ADDRESS}/ai/2026/11/12/" rel="alternate"/>' in feed
    assert f'<link href="{ADDRESS}/ai/feed.xml" rel="self"/>' in feed


def test_feed_entries_of_a_site_with_an_address_have_ids_that_never_change(addressed_site):
    # feed readers tell entries apart by their id
    ids = re.findall(r"<id>([^<]*)</id>", page(addressed_site, "feed.xml"))

    assert ids
    assert all(i.startswith(("https://", "tag:")) for i in ids)


def test_pages_of_a_site_with_an_address_still_work_from_the_local_disk(addressed_site):
    start = page(addressed_site, "index.html")

    assert ADDRESS not in start
    assert 'href="./theme/css/style.css"' in start


# --- visitor statistics ---------------------------------------------------------------

PLAUSIBLE = "https://stats.example.org/js/pa-test.js"


@pytest.fixture(scope="module")
def counted_site(tmp_path_factory):
    editions = tmp_path_factory.mktemp("editions")
    output = tmp_path_factory.mktemp("output")
    write_edition(editions, edition_json(day=NEW, main=[entry_json("alice/tiny-editor")]))
    build_site(editions, output, plausible_script=PLAUSIBLE)
    return output


def test_site_counts_no_visits_unless_asked_to(site):
    start = page(site, "index.html")

    assert "plausible" not in start.lower()
    assert "Ohne Tracking, ohne Skripte" in start


@pytest.mark.parametrize("path", ["index.html", "ai/index.html", "archiv/index.html", "2026/11/12/index.html"])
def test_every_page_of_a_counted_site_loads_the_plausible_script(counted_site, path):
    html = page(counted_site, path)

    assert f'<script async src="{PLAUSIBLE}"></script>' in html
    assert "plausible.init()" in html


def test_a_counted_site_does_not_claim_to_be_free_of_tracking(counted_site):
    start = page(counted_site, "index.html")

    assert "Ohne Tracking" not in start
    assert "Plausible" in start


def test_feeds_of_a_counted_site_carry_no_script(counted_site):
    assert "<script" not in page(counted_site, "feed.xml")


def test_plausible_script_must_be_loaded_over_https(tmp_path):
    with pytest.raises(ValueError):
        build_site(tmp_path / "editions", tmp_path / "output", plausible_script="javascript:alert(1)")
