"""Builds the static site from the stored editions. See docs/veroeffentlichung.md."""

import tempfile
from pathlib import Path

from pelican import Pelican
from pelican.settings import read_settings

THEME = Path(__file__).with_name("theme")
SITE_NAME = "Fundstücke"


def build_site(
    data_dir: Path,
    output_dir: Path,
    site_url: str | None = None,
    plausible_script: str | None = None,
) -> None:
    """Reads data_dir/editions and the community editions: hn-, lobsters-, forums-editions.

    site_url is the public address of the site: the feeds need it for full links. The
    pages keep relative links either way, so they also work from the local disk.

    plausible_script is the address of a Plausible script that counts visits. Without it
    the pages contain no script at all and load nothing from other servers.
    """
    if plausible_script is not None and not plausible_script.startswith("https://"):
        raise ValueError("Das Plausible-Skript muss eine https-Adresse sein")
    data_dir = Path(data_dir)
    # Pelican wants a content directory. Ours stays empty: the plugin brings the articles.
    with tempfile.TemporaryDirectory() as no_content:
        settings = read_settings(
            override={
                "PATH": no_content,
                "OUTPUT_PATH": str(output_dir),
                "THEME": str(THEME),
                "PLUGINS": ["explore_gh.publication.pelican_plugin"],
                "EDITIONS_PATH": str(data_dir / "editions"),
                "HN_EDITIONS_PATH": str(data_dir / "hn-editions"),
                "LOBSTERS_EDITIONS_PATH": str(data_dir / "lobsters-editions"),
                "FORUMS_EDITIONS_PATH": str(data_dir / "forums-editions"),
                "WITHDRAWN_PATH": str(data_dir / "withdrawn.json"),
                "SITENAME": SITE_NAME,
                "PLAUSIBLE_SCRIPT": plausible_script,
                "SITEURL": (site_url or "").rstrip("/"),
                "RELATIVE_URLS": True,
                "TIMEZONE": "UTC",
                "DEFAULT_LANG": "de",
                # text from strangers must never be read as HTML
                "JINJA_ENVIRONMENT": {
                    "autoescape": True,
                    "trim_blocks": True,
                    "lstrip_blocks": True,
                },
                # the plugin writes the newest pages and archives of each list itself
                "DIRECT_TEMPLATES": [],
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
