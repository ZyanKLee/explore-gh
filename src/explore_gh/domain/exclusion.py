"""Reasons to remove a repo completely. The first matching rule gives the reason.

See docs/bewertung.md, "Ausschlüsse".
"""

import re
from collections.abc import Sequence

from explore_gh.domain.language import foreign_language
from explore_gh.domain.model import GROWTH_WINDOW_DAYS, Exclusion, Snapshot
from explore_gh.domain.preferences import CONSOLE_TERMS
from explore_gh.domain.text import TermList, labels, number

MIN_STARS_GAINED = 60
# Between the creation of the repo and its last push, both as GitHub recorded them.
# Dates of commits do not count: lures date them back.
MIN_DEVELOPMENT_DAYS = 14

COLLECTION_TERMS = TermList(
    [
        "awesome",
        "curated list",
        "interview",
        "tutorial",
        "roadmap",
        "cheatsheet",
        "cheat sheet",
        "dotfiles",
        "leetcode",
        "system prompts",
        "prompt collection",
        "prompt library",
    ]
)
# Wording of repos that pose as installers of commercial software and deliver malware.
LURE_TERMS = TermList(
    [
        "secure standalone",
        "complete standalone",
        "standalone desktop",
        "standalone setup",
        "desktop setup",
        "desktop installer",
        "pre configured",
        "pre activated",
        "full feature",
        "all features enabled",
        "full version",
    ]
)
# The README of these lures: an image as button that leads to a GitHub Pages site, where a
# PowerShell command waits to be copied. Never seen in an honest repo.
LURE_BUTTON = re.compile(
    # Markdown: [![alt](…button…)](https://owner.github.io/…)
    r"\[!\[[^\]]*\]\([^)]*button[^)]*\)\]\(https?://[^)/]*\.github\.io/"
    # HTML: <a href="https://owner.github.io/…"><img src="…button…">
    r"|<a\s[^>]*href=[\"']https?://[^\"'/]*\.github\.io/[^>]*>\s*<img\s[^>]*button",
    re.IGNORECASE,
)
# Signs of piracy and of getting around copy protection, in the labels or the README.
# The review by the language model catches more; these need no judgement.
PIRACY_TERMS = TermList(
    [
        "pro unlocked",
        "premium unlocked",
        "premium features unlocked",
        "unlocked premium",
        "unlock premium",
        "goldhen",
        "cloudstream extension",
        "stremio add on",
        "stremio addon",
        "fake psn",
    ]
)
# A jailbreak counts only together with a game console, and only in the labels: jailbreaks
# of phones are no piracy, and a README may just mention the scene.
JAILBREAK_TERMS = TermList(["jailbreak", "jailbroken"])
CRYPTO_TERMS = TermList(
    [
        "crypto",
        "cryptocurrency",
        "cryptocurrencies",
        "bitcoin",
        "ethereum",
        "solana",
        "web3",
        "defi",
        "nft",
        "blockchain",
        "memecoin",
        "altcoin",
        "stablecoin",
        "airdrop",
        "trading bot",
        "smart contract",
        "binance",
        "hyperliquid",
    ]
)


class ExclusionPolicy:
    def check(self, snapshot: Snapshot) -> Exclusion | None:
        if snapshot.is_fork:
            return Exclusion("Fork", "fork")
        if snapshot.is_archived:
            return Exclusion("Archiviert", "archived")
        if snapshot.is_mirror:
            return Exclusion("Spiegel eines anderen Repos", "mirror")
        if not snapshot.primary_language:
            return Exclusion("GitHub erkennt keine Programmiersprache", "no_code")
        if exclusion := self.check_text(
            name=snapshot.repo.name,
            description=snapshot.description,
            topics=snapshot.topics,
            readme=snapshot.readme,
        ):
            return exclusion

        developed = (snapshot.pushed_at - snapshot.created_at).days if snapshot.pushed_at else 0
        if developed < MIN_DEVELOPMENT_DAYS:
            return Exclusion(
                f"Erst {developed} Tage Entwicklung auf GitHub, nötig sind {MIN_DEVELOPMENT_DAYS}",
                "young",
            )
        gained = snapshot.star_history.gained()
        if gained < MIN_STARS_GAINED:
            return Exclusion(
                f"Nur {number(gained)} neue Sterne in {GROWTH_WINDOW_DAYS} Tagen, "
                f"nötig sind {MIN_STARS_GAINED}",
                "low_momentum",
            )
        return None

    def check_text(
        self, *, name: str, description: str, topics: Sequence[str], readme: str | None
    ) -> Exclusion | None:
        """The rules that need texts only. They apply to HN and Lobsters projects too.

        readme None means it could not be read: no reason to exclude, unlike an empty one.
        """
        text = labels(name, description, topics)
        if found := COLLECTION_TERMS.distinct(text):
            return Exclusion(f"Sammlung oder Lernmaterial („{found[0]}“)", "collection")
        if found := LURE_TERMS.distinct(text):
            return Exclusion(f"Köder für Schadsoftware („{found[0]}“)", "lure")
        if readme is not None and LURE_BUTTON.search(readme) and "powershell" in readme.lower():
            return Exclusion(
                "Köder für Schadsoftware (README führt über einen Knopf zu einem "
                "PowerShell-Befehl)",
                "lure",
            )
        if found := PIRACY_TERMS.distinct(text + " . " + (readme or "")):
            return _piracy(found[0])
        if (found := JAILBREAK_TERMS.distinct(text)) and (consoles := CONSOLE_TERMS.distinct(text)):
            return _piracy(f"{consoles[0]} {found[0]}")
        if readme is not None and not readme.strip():
            return Exclusion("Kein README", "no_readme")
        if reason := foreign_language(description, readme or ""):
            return Exclusion(reason, "language")
        if found := CRYPTO_TERMS.distinct(text):
            return Exclusion(f"Kryptowährungen („{found[0]}“)", "crypto")
        return None


def _piracy(term: str) -> Exclusion:
    return Exclusion(f"Anzeichen für Raubkopie oder Umgehung von Kopierschutz („{term}“)", "piracy")
