"""Pelican plugin: turns every edition into two articles, main list and AI section.

Kept thin on purpose. Texts and numbers come from view.py, the theme only arranges them.
"""

from datetime import UTC

from pelican import signals
from pelican.contents import Article
from pelican.urlwrappers import Category
from pelican.utils import SafeDatetime

from github_anti_ai.publication.view import (
    SECTION_TITLES,
    feed_html,
    load_editions,
    long_date,
    section_view,
)
from github_anti_ai.publication.hn_view import hn_feed_html, load_hn_editions
from github_anti_ai.publication.lobsters_view import (
    load_lobsters_editions,
    lobsters_feed_html,
)

# CATEGORY_FEED_ATOM is "{slug}feed.xml": the main list gets /feed.xml, the AI section /ai/feed.xml
FEED_SLUGS = {"main": "", "ai": "ai/"}


def add_editions(generator):
    settings = generator.settings
    editions = load_editions(settings["EDITIONS_PATH"])
    categories = {}
    for section, title in SECTION_TITLES.items():
        categories[section] = Category(title, settings)
        categories[section].slug = FEED_SLUGS[section]

    days = [
        {section: section_view(edition, section) for section in SECTION_TITLES}
        for edition in editions
    ]
    for index, views in enumerate(days):
        older = days[index - 1] if index > 0 else None
        newer = days[index + 1] if index + 1 < len(days) else None
        for section, view in views.items():
            other = views["ai" if section == "main" else "main"]
            view_day = view.day
            metadata = {
                "title": view.title,
                "date": SafeDatetime(view_day.year, view_day.month, view_day.day, tzinfo=UTC),
                "category": categories[section],
                "slug": f"{section}-{view_day.isoformat()}",
                "url": view.url,
                "save_as": f"{view.url}index.html",
                "summary": feed_html(view),
                "view": view,
                "nav": {
                    "older": older[section] if older else None,
                    "newer": newer[section] if newer else None,
                    "other": other,
                },
            }
            generator.articles.append(
                Article(feed_html(view), metadata, settings=settings, context=generator.context)
            )
    generator.articles.sort(key=lambda article: article.date, reverse=True)

    newest_first = list(reversed(days))
    generator.context["edition_days"] = [
        {"date": long_date(views["main"].day), "main": views["main"], "ai": views["ai"]}
        for views in newest_first
    ]
    generator.context["latest"] = {
        section: {
            "view": views[section],
            "nav": {
                "older": newest_first[1][section] if len(newest_first) > 1 else None,
                "newer": None,
                "other": views["ai" if section == "main" else "main"],
            },
        }
        for views in newest_first[:1]
        for section in SECTION_TITLES
    }
    _add_hn_editions(generator)
    _add_lobsters_editions(generator)


def _add_hn_editions(generator):
    editions_path = generator.settings.get("HN_EDITIONS_PATH")
    if not editions_path:
        return
    editions = load_hn_editions(editions_path)
    category = Category("Trending auf HN", generator.settings)
    category.slug = "hn/"
    days = list(reversed(editions))
    for index, view in enumerate(days):
        older = days[index + 1] if index + 1 < len(days) else None
        newer = days[index - 1] if index > 0 else None
        generator.articles.append(
            Article(
                hn_feed_html(view),
                {
                    "title": view.title,
                    "date": SafeDatetime(view.day.year, view.day.month, view.day.day, tzinfo=UTC),
                    "category": category,
                    "slug": f"hn-{view.day.isoformat()}",
                    "url": view.url,
                    "save_as": f"{view.url}index.html",
                    "template": "hn-article",
                    "hn_view": view,
                    "hn_nav": {"older": older, "newer": newer},
                    "summary": hn_feed_html(view),
                },
                settings=generator.settings,
                context=generator.context,
            )
        )
    if days:
        generator.context["latest_hn"] = days[0]
        generator.context["hn_edition_days"] = days
    generator.articles.sort(key=lambda article: article.date, reverse=True)


def _add_lobsters_editions(generator):
    editions_path = generator.settings.get("LOBSTERS_EDITIONS_PATH")
    if not editions_path:
        return
    editions = load_lobsters_editions(editions_path)
    category = Category("Trending auf Lobsters", generator.settings)
    category.slug = "lobsters/"
    days = list(reversed(editions))
    for index, view in enumerate(days):
        older = days[index + 1] if index + 1 < len(days) else None
        newer = days[index - 1] if index > 0 else None
        generator.articles.append(
            Article(
                lobsters_feed_html(view),
                {
                    "title": view.title,
                    "date": SafeDatetime(view.day.year, view.day.month, view.day.day, tzinfo=UTC),
                    "category": category,
                    "slug": f"lobsters-{view.day.isoformat()}",
                    "url": view.url,
                    "save_as": f"{view.url}index.html",
                    "template": "lobsters-article",
                    "lobsters_view": view,
                    "lobsters_nav": {"older": older, "newer": newer},
                    "summary": lobsters_feed_html(view),
                },
                settings=generator.settings,
                context=generator.context,
            )
        )
    if days:
        generator.context["latest_lobsters"] = days[0]
        generator.context["lobsters_edition_days"] = days
    generator.articles.sort(key=lambda article: article.date, reverse=True)


def register():
    signals.article_generator_pretaxonomy.connect(add_editions)
