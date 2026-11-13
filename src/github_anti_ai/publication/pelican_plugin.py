"""Pelican plugin: turns every edition into two articles, main list and AI section.

This holds for the GitHub editions as well as for the HN and Lobsters editions.

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
from github_anti_ai.publication.community_view import (
    HN,
    LOBSTERS,
    SECTIONS,
    community_feed_html,
    load_community_editions,
    section_heading,
    section_url,
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
    _add_community_editions(generator, HN, settings.get("HN_EDITIONS_PATH"))
    _add_community_editions(generator, LOBSTERS, settings.get("LOBSTERS_EDITIONS_PATH"))


def _add_community_editions(generator, platform, editions_path):
    """Two articles per day, main list and AI section, each with its own feed."""
    if not editions_path:
        return
    categories = {}
    for section in SECTIONS:
        categories[section] = Category(section_heading(platform, section), generator.settings)
        categories[section].slug = section_url(platform, section)  # hn/feed.xml, hn/ai/feed.xml
    archive_url = f"{platform.slug}/archiv/"
    days = list(reversed(load_community_editions(editions_path, platform)))  # newest first
    for index, day in enumerate(days):
        older = days[index + 1] if index + 1 < len(days) else None
        newer = days[index - 1] if index > 0 else None
        for section in SECTIONS:
            view = day.section(section)
            generator.articles.append(
                Article(
                    community_feed_html(view),
                    {
                        "title": view.title,
                        "date": SafeDatetime(
                            view.day.year, view.day.month, view.day.day, tzinfo=UTC
                        ),
                        "category": categories[section],
                        "slug": f"{platform.slug}-{section}-{view.day.isoformat()}",
                        "url": view.url,
                        "save_as": f"{view.url}index.html",
                        "template": "community-article",
                        "community_current": platform.slug,
                        "community_view": view,
                        "community_archive_url": archive_url,
                        "community_nav": _community_nav(older, newer, day, section),
                        "summary": community_feed_html(view),
                    },
                    settings=generator.settings,
                    context=generator.context,
                )
            )
    if days:
        generator.context[f"latest_{platform.slug}"] = {
            section: {
                "view": days[0].section(section),
                "nav": _community_nav(days[1] if len(days) > 1 else None, None, days[0], section),
            }
            for section in SECTIONS
        }
    generator.context[f"{platform.slug}_edition_days"] = days
    generator.articles.sort(key=lambda article: article.date, reverse=True)


def _community_nav(older, newer, day, section):
    other = "ai" if section == "main" else "main"
    return {
        "older": older.section(section) if older else None,
        "newer": newer.section(section) if newer else None,
        "other": day.section(other),
    }


def register():
    signals.article_generator_pretaxonomy.connect(add_editions)
