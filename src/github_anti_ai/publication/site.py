"""Builds the static site from the stored editions. See docs/veroeffentlichung.md."""

import tempfile
from pathlib import Path

from pelican import Pelican
from pelican.settings import read_settings

THEME = Path(__file__).with_name("theme")


def build_site(editions_dir: Path, output_dir: Path, site_url: str | None = None) -> None:
    """site_url is the public address of the site. The feeds need it for full links.

    The pages keep relative links either way, so they also work from the local disk.
    """
    # Pelican wants a content directory. Ours stays empty: the plugin supplies the articles.
    with tempfile.TemporaryDirectory() as no_content:
        settings = read_settings(
            override={
                "PATH": no_content,
                "OUTPUT_PATH": str(output_dir),
                "THEME": str(THEME),
                "PLUGINS": ["github_anti_ai.publication.pelican_plugin"],
                "EDITIONS_PATH": str(editions_dir),
                "SITENAME": "Fundstücke",
                "SITEURL": (site_url or "").rstrip("/"),
                "RELATIVE_URLS": True,
                "TIMEZONE": "UTC",
                "DEFAULT_LANG": "de",
                # text from GitHub must never be interpreted as HTML
                "JINJA_ENVIRONMENT": {"autoescape": True, "trim_blocks": True, "lstrip_blocks": True},
                "DIRECT_TEMPLATES": ["index", "ai", "archiv"],
                "AI_SAVE_AS": "ai/index.html",
                "ARCHIV_SAVE_AS": "archiv/index.html",
                "CATEGORY_FEED_ATOM": "{slug}feed.xml",
                "FEED_ALL_ATOM": None,
                "AUTHOR_FEED_ATOM": None,
                "AUTHOR_FEED_RSS": None,
                "TRANSLATION_FEED_ATOM": None,
                "CATEGORY_SAVE_AS": "",
                "CATEGORIES_SAVE_AS": "",
                "AUTHOR_SAVE_AS": "",
                "AUTHORS_SAVE_AS": "",
                "TAG_SAVE_AS": "",
                "TAGS_SAVE_AS": "",
                "ARCHIVES_SAVE_AS": "",
                "STATIC_PATHS": [],
                "PAGE_PATHS": [],
                "CACHE_CONTENT": False,
                "LOAD_CONTENT_CACHE": False,
            }
        )
        Pelican(settings).run()
