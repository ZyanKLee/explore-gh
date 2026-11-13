from datetime import UTC, datetime

from github_anti_ai.adapters.json_hn_edition_store import JsonHnEditionStore
from github_anti_ai.domain.hn import HnEdition, HnProjectCandidate, HnStory
from github_anti_ai.publication.site import build_site


def test_hn_projects_have_a_separate_page_archive_and_feed(tmp_path):
    story = HnStory(
        id="123",
        title="A project worth exploring",
        url="https://project.example",
        points=42,
        comments=9,
        created_at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    edition = HnEdition(
        day=story.created_at.date(),
        projects=(
            HnProjectCandidate(
                story=story,
                repository_url="https://codeberg.org/owner/project",
                project_url=story.url,
                description="A useful open source project",
                language="Rust",
                license_id="MIT",
                is_fork=False,
                is_archived=False,
                has_code=True,
            ),
        ),
    )
    hn_editions = tmp_path / "hn-editions"
    JsonHnEditionStore(hn_editions).save(edition)

    build_site(tmp_path / "editions", tmp_path / "output", hn_editions_dir=hn_editions)

    start = (tmp_path / "output/hn/index.html").read_text(encoding="utf-8")
    day = (tmp_path / "output/hn/2026/11/13/index.html").read_text(encoding="utf-8")
    archive = (tmp_path / "output/hn/archiv/index.html").read_text(encoding="utf-8")
    feed = (tmp_path / "output/hn/feed.xml").read_text(encoding="utf-8")

    assert "Trending auf HN" in start
    assert "owner/project" in start
    assert "https://news.ycombinator.com/item?id=123" in day
    assert "13. November 2026" in archive
    assert "owner/project" in feed
    assert "owner/project" not in (tmp_path / "output/index.html").read_text(encoding="utf-8")


def test_hn_ai_projects_have_their_own_pages_archive_entry_and_feed(tmp_path):
    def project(repo, story):
        return HnProjectCandidate(
            story=story, repository_url=f"https://codeberg.org/{repo}", project_url=story.url,
            description="", language="Rust", license_id="MIT", is_fork=False,
            is_archived=False, has_code=True,
        )

    story = HnStory("9", "Agent", "https://agent.example", 30, 2, datetime(2026, 11, 13, tzinfo=UTC))
    main_story = HnStory("9", "Editor", "https://editor.example", 30, 2, datetime(2026, 11, 13, tzinfo=UTC))
    edition = HnEdition(
        day=story.created_at.date(),
        projects=(project("owner/editor", main_story),),
        ai_projects=(project("owner/agent", story),),
    )
    editions = tmp_path / "hn-editions"
    JsonHnEditionStore(editions).save(edition)

    build_site(tmp_path / "editions", tmp_path / "output", hn_editions_dir=editions)

    def page(path):
        return (tmp_path / "output" / path).read_text(encoding="utf-8")

    assert "AI-Projekte auf HN" in page("hn/ai/index.html")
    assert "owner/agent" in page("hn/ai/index.html")
    assert "owner/editor" not in page("hn/ai/index.html")
    assert "https://news.ycombinator.com/item?id=9" in page("hn/ai/2026/11/13/index.html")
    assert "owner/agent" in page("hn/ai/feed.xml")
    assert "owner/agent" not in page("hn/index.html")
    assert "owner/agent" not in page("hn/2026/11/13/index.html")
    assert "owner/agent" not in page("hn/feed.xml")
    assert "hn/ai/2026/11/13/" in page("hn/archiv/index.html")
    assert "1 AI-Projekt<" in page("hn/archiv/index.html")
    assert "hn/ai/" in page("hn/index.html")



def test_hn_entry_explains_its_place(tmp_path):
    story = HnStory("5", "Tool", "https://github.com/owner/tool", 42, 9,
                    datetime(2026, 11, 13, tzinfo=UTC))
    project = HnProjectCandidate(
        story=story, repository_url="https://github.com/owner/tool", project_url=story.url,
        description="", language="Rust", license_id="MIT", is_fork=False, is_archived=False,
        has_code=True, linked_directly=True, reasons=("Die Story verlinkt das Repo direkt.",),
    )
    editions = tmp_path / "hn-editions"
    JsonHnEditionStore(editions).save(HnEdition(day=story.created_at.date(), projects=(project,)))

    build_site(tmp_path / "editions", tmp_path / "output", hn_editions_dir=editions)

    start = (tmp_path / "output/hn/index.html").read_text(encoding="utf-8")
    assert "Warum Platz 1?" in start
    assert "42 HN-Punkte" in start
    assert "Die Story verlinkt das Repo direkt." in start


def test_hn_ai_page_links_back_to_trending_of_the_same_day(tmp_path):
    story = HnStory("9", "Agent", "https://agent.example", 30, 2, datetime(2026, 11, 13, tzinfo=UTC))
    project = HnProjectCandidate(
        story=story, repository_url="https://codeberg.org/owner/agent", project_url=story.url,
        description="", language="Rust", license_id="MIT", is_fork=False,
        is_archived=False, has_code=True,
    )
    editions = tmp_path / "hn-editions"
    JsonHnEditionStore(editions).save(HnEdition(day=story.created_at.date(), ai_projects=(project,)))

    build_site(tmp_path / "editions", tmp_path / "output", hn_editions_dir=editions)

    html = (tmp_path / "output/hn/ai/index.html").read_text(encoding="utf-8")
    assert ">Trending dieses Tages</a>" in html
    assert "Hauptliste" not in html
