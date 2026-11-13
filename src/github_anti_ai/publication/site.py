"""Builds the static site from the stored editions. See docs/veroeffentlichung.md."""

import tempfile
from pathlib import Path

from pelican import Pelican
from pelican.settings import read_settings

THEME = Path(__file__).with_name("theme")


def build_site(
    editions_dir: Path,
    output_dir: Path,
    site_url: str | None = None,
    plausible_script: str | None = None,
    hn_editions_dir: Path | None = None,
    lobsters_editions_dir: Path | None = None,
) -> None:
    """site_url is the public address of the site. The feeds need it for full links.

    The pages keep relative links either way, so they also work from the local disk.

    plausible_script is the address of a Plausible script that counts visits. Without it
    the pages contain no script at all and load nothing from other servers.
    """
    if plausible_script is not None and not plausible_script.startswith("https://"):
        raise ValueError("Das Plausible-Skript muss eine https-Adresse sein")
    # Pelican wants a content directory. Ours stays empty: the plugin supplies the articles.
    with tempfile.TemporaryDirectory() as no_content:
        settings = read_settings(
            override={
                "PATH": no_content,
                "OUTPUT_PATH": str(output_dir),
                "THEME": str(THEME),
                "PLUGINS": ["github_anti_ai.publication.pelican_plugin"],
                "EDITIONS_PATH": str(editions_dir),
                "HN_EDITIONS_PATH": str(hn_editions_dir) if hn_editions_dir else None,
                "LOBSTERS_EDITIONS_PATH": (
                    str(lobsters_editions_dir) if lobsters_editions_dir else None
                ),
                "SITENAME": "Fundstücke",
                "PLAUSIBLE_SCRIPT": plausible_script,
                "SITEURL": (site_url or "").rstrip("/"),
                "RELATIVE_URLS": True,
                "TIMEZONE": "UTC",
                "DEFAULT_LANG": "de",
                # text from GitHub must never be interpreted as HTML
                "JINJA_ENVIRONMENT": {"autoescape": True, "trim_blocks": True, "lstrip_blocks": True},
                "DIRECT_TEMPLATES": [
                    "index", "ai", "archiv",
                    "hn", "hn_ai", "hn_archiv",
                    "lobsters", "lobsters_ai", "lobsters_archiv",
                ],
                "AI_SAVE_AS": "ai/index.html",
                "ARCHIV_SAVE_AS": "archiv/index.html",
                "HN_SAVE_AS": "hn/index.html",
                "HN_ARCHIV_SAVE_AS": "hn/archiv/index.html",
                "HN_AI_SAVE_AS": "hn/ai/index.html",
                "LOBSTERS_SAVE_AS": "lobsters/index.html",
                "LOBSTERS_ARCHIV_SAVE_AS": "lobsters/archiv/index.html",
                "LOBSTERS_AI_SAVE_AS": "lobsters/ai/index.html",
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
