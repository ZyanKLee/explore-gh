"""Pelican plugin: turns the stored editions into pages and feeds.

Every day of every list becomes two articles, main list and AI section, each in a category
of its own and so with a feed of its own. Each list also gets its newest pages and an archive.
Kept thin on purpose: texts and numbers come from the page models, the theme only arranges them.
"""

from dataclasses import dataclass
from datetime import UTC

from pelican import signals
from pelican.contents import Article
from pelican.urlwrappers import Category
from pelican.utils import SafeDatetime

from explore_gh.publication.community_view import (
    PLATFORMS,
    community_feed_html,
    load_community_editions,
    section_heading,
    section_url,
)
from explore_gh.publication.view import SECTION_TITLES, feed_html, load_github_days

SECTIONS = ("main", "ai")


@dataclass(frozen=True)
class PageList:
    """One list of the site: GitHub, HN or Lobsters."""

    slug: str  # marks the list in the main navigation: github, hn, lobsters
    name: str  # GitHub, HN, Lobsters
    days: list  # newest first; each day has .day and .section(name)
    article_template: str
    feed_html: object  # view -> HTML for feed readers
    headings: dict[str, str]  # by section: name of the category and title of the newest page
    prefixes: dict[str, str]  # by section: start of the addresses, also of the feed
    article_slug: str  # with {section} and {day}

    @property
    def archive_url(self) -> str:
        return f"{self.prefixes['main']}archiv/"


def _lists(settings) -> list[PageList]:
    lists = [
        PageList(
            slug="github",
            name="GitHub",
            days=list(reversed(load_github_days(settings["EDITIONS_PATH"]))),
            article_template="article",
            feed_html=feed_html,
            headings=SECTION_TITLES,
            prefixes={"main": "", "ai": "ai/"},  # the addresses of the first days stay
            article_slug="{section}-{day}",
        )
    ]
    for platform in PLATFORMS:
        path = settings.get(f"{platform.slug.upper()}_EDITIONS_PATH")
        lists.append(
            PageList(
                slug=platform.slug,
                name=platform.name,
                days=list(reversed(load_community_editions(path, platform))) if path else [],
                article_template="community-article",
                feed_html=community_feed_html,
                headings={s: section_heading(platform, s) for s in SECTIONS},
                prefixes={s: section_url(platform, s) for s in SECTIONS},
                article_slug=f"{platform.slug}-{{section}}-{{day}}",
            )
        )
    return lists


def _nav(days: list, index: int, section: str) -> dict:
    """The day before, the day after, and the other section of the same day."""
    day = days[index]
    return {
        "older": days[index + 1].section(section) if index + 1 < len(days) else None,
        "newer": days[index - 1].section(section) if index > 0 else None,
        "other": day.section("ai" if section == "main" else "main"),
    }


def add_articles(generator):
    settings = generator.settings
    lists = _lists(settings)
    for page_list in lists:
        categories = {}
        for section in SECTIONS:
            categories[section] = Category(page_list.headings[section], settings)
            categories[section].slug = page_list.prefixes[section]  # feed: {slug}feed.xml
        for index, day in enumerate(page_list.days):
            for section in SECTIONS:
                view = day.section(section)
                html = page_list.feed_html(view)
                metadata = {
                    "title": view.title,
                    "date": SafeDatetime(view.day.year, view.day.month, view.day.day, tzinfo=UTC),
                    "category": categories[section],
                    "slug": page_list.article_slug.format(
                        section=section, day=view.day.isoformat()
                    ),
                    "url": view.url,
                    "save_as": f"{view.url}index.html",
                    "template": page_list.article_template,
                    "summary": html,
                    "current": page_list.slug,
                    "view": view,
                    "nav": _nav(page_list.days, index, section),
                    "archive_url": page_list.archive_url,
                }
                generator.articles.append(
                    Article(html, metadata, settings=settings, context=generator.context)
                )
    generator.articles.sort(key=lambda article: article.date, reverse=True)
    generator.context["page_lists"] = lists


def write_list_pages(generator, writer):
    """The newest edition of each section and the archive, for every list."""
    for page_list in generator.context["page_lists"]:
        latest = (
            {
                s: {"view": page_list.days[0].section(s), "nav": _nav(page_list.days, 0, s)}
                for s in SECTIONS
            }
            if page_list.days
            else None
        )
        pages = [(page_list.prefixes[s], "latest", page_list.headings[s], s) for s in SECTIONS] + [
            (page_list.archive_url, "archive", f"{page_list.name}-Archiv", None)
        ]
        for url, kind, title, section in pages:
            writer.write_file(
                f"{url}index.html",
                generator.get_template("list-page"),
                generator.context,
                relative_urls=generator.settings["RELATIVE_URLS"],
                template_name="list-page",
                url=url,
                page_list=page_list,
                page_kind=kind,
                page_title=title,
                section=section,
                latest=latest,
                current=page_list.slug,
            )


def register():
    signals.article_generator_pretaxonomy.connect(add_articles)
    signals.article_writer_finalized.connect(write_list_pages)
