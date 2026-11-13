"""Reasons to remove a repo completely. The first matching rule gives the reason."""

import re
from collections.abc import Sequence

from github_anti_ai.domain.model import Exclusion, Snapshot
from github_anti_ai.domain.text import TermList, number

MIN_STARS_GAINED = 50

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
# Seen live by the hundred, all with about 100 or 1100 stars and no forks or issues.
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
_LURE_BUTTON = re.compile(
    # Markdown: [![alt](…button…)](https://owner.github.io/…)
    r"\[!\[[^\]]*\]\([^)]*button[^)]*\)\]\(https?://[^)/]*\.github\.io/"
    # HTML: <a href="https://owner.github.io/…"><img src="…button…">
    r"|<a\s[^>]*href=[\"']https?://[^\"'/]*\.github\.io/[^>]*>\s*<img\s[^>]*button",
    re.IGNORECASE,
)
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

# language detection
PROSE_MAX_CHARS = 4000
MIN_PROSE_WORDS = 40
MAX_FOREIGN_SCRIPT_SHARE = 0.20
MIN_FUNCTION_WORD_SHARE = 0.05
FUNCTION_WORDS = frozenset(
    # English
    "the of and to a in is it you that for on with as are this be at or by from an can "
    "not have has will your if but all we which when use its more no any only how also "
    "was were they their there what so do does than then into about these "
    # German
    "der die das und ist in zu den von mit für auf ein eine einer einen dem des nicht "
    "sich es auch als an werden wird kann oder wie im du er sie wir aus bei nach um wenn "
    "nur noch über hat sind dass man zum zur durch dies diese dieser keine ihn".split()
)
# The most frequent words of other languages in Latin script. A text is foreign if one of
# these lists fits better than the German and English one.
OTHER_LANGUAGES = {
    "Spanisch": "el la los las de del que y en un una para con por se es más como su al lo no",
    "Portugiesisch": "o os a as de do da dos das que e em um uma para com por não mais como é no na",
    "Französisch": "le la les de des du et en un une pour avec dans que qui est sur pas au ce vous",
    "Italienisch": "il lo la i gli le di del della che e in un una per con non è da si come più",
    "Niederländisch": "de het een van en in is dat op te voor met niet zijn je om naar ook als",
    "Türkisch": "ve bir bu için ile de da olarak daha en çok gibi veya her ne",
    "Indonesisch": "yang dan di untuk dengan dari ini itu ke pada atau tidak akan dalam bisa",
    "Vietnamesisch": "và của là có cho các một được trong không với để này khi bạn",
    "Polnisch": "i w z na do się nie to jest że o jak dla po od lub przez",
}
_OTHER_LANGUAGE_WORDS = {name: frozenset(words.split()) for name, words in OTHER_LANGUAGES.items()}

_CODE_BLOCK = re.compile(r"```.*?(```|\Z)|~~~.*?(~~~|\Z)", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_HTML = re.compile(r"<[^>]*>")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"[^\W\d_]+")
_LAST_LATIN_LETTER = "ɏ"  # end of the block "Latin Extended-B"


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

        gained = snapshot.star_history.gained()
        if gained < MIN_STARS_GAINED:
            return Exclusion(
                f"Nur {number(gained)} neue Sterne in 7 Tagen, nötig sind {MIN_STARS_GAINED}",
                "low_momentum",
            )
        return None

    def check_text(
        self, *, name: str, description: str, topics: Sequence[str], readme: str | None
    ) -> Exclusion | None:
        """The rules that need texts only, also for HN and Lobsters projects.

        readme None means it could not be read: no reason to exclude, unlike an empty one.
        """
        labels = " . ".join([name, description, *topics])
        if found := COLLECTION_TERMS.distinct(labels):
            return Exclusion(f"Sammlung oder Lernmaterial („{found[0]}“)", "collection")
        if found := LURE_TERMS.distinct(labels):
            return Exclusion(f"Köder für Schadsoftware („{found[0]}“)", "lure")
        if readme is not None and _LURE_BUTTON.search(readme) and "powershell" in readme.lower():
            return Exclusion(
                "Köder für Schadsoftware (README führt über einen Knopf zu einem "
                "PowerShell-Befehl)",
                "lure",
            )
        if readme is not None and not readme.strip():
            return Exclusion("Kein README", "no_readme")
        if reason := foreign_language(description, readme or ""):
            return Exclusion(reason, "language")
        if found := CRYPTO_TERMS.distinct(labels):
            return Exclusion(f"Kryptowährungen („{found[0]}“)", "crypto")
        return None


def prose(markdown: str) -> str:
    """The running text of a README: without code, links, images and HTML."""
    text = _CODE_BLOCK.sub(" ", markdown)
    text = _INLINE_CODE.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    return _URL.sub(" ", text)


def _foreign_script_share(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char > _LAST_LATIN_LETTER) / len(letters)


def foreign_language(description: str, readme: str) -> str | None:
    """Says why the text is neither German nor English, or None if it may be."""
    text = (description + "\n" + prose(readme))[:PROSE_MAX_CHARS]
    if (foreign := _foreign_script_share(description)) > MAX_FOREIGN_SCRIPT_SHARE:
        return (
            "Weder deutsch noch englisch: "
            f"{foreign:.0%} der Buchstaben der Beschreibung in anderer Schrift"
        )
    if (foreign := _foreign_script_share(text)) > MAX_FOREIGN_SCRIPT_SHARE:
        return f"Weder deutsch noch englisch: {foreign:.0%} der Buchstaben in anderer Schrift"

    words = [word.lower() for word in _WORD.findall(text)]
    if len(words) < MIN_PROSE_WORDS:
        return None  # too little text for a verdict
    known = sum(1 for word in words if word in FUNCTION_WORDS) / len(words)
    for vocabulary in _OTHER_LANGUAGE_WORDS.values():
        if sum(1 for word in words if word in vocabulary) / len(words) > known:
            return "Weder deutsch noch englisch: häufige Wörter einer anderen Sprache überwiegen"
    if known < MIN_FUNCTION_WORD_SHARE:
        return (
            "Weder deutsch noch englisch: "
            f"nur {known:.0%} der Wörter sind häufige deutsche oder englische Wörter"
        )
    return None
