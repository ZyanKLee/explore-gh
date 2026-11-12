"""Reasons to remove a repo completely. The first matching rule gives the reason."""

import re

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

        labels = " . ".join([snapshot.repo.name, snapshot.description, *snapshot.topics])
        if found := COLLECTION_TERMS.distinct(labels):
            return Exclusion(f"Sammlung oder Lernmaterial („{found[0]}“)", "collection")
        if not snapshot.readme.strip():
            return Exclusion("Kein README", "no_readme")
        if reason := foreign_language(snapshot.description, snapshot.readme):
            return Exclusion(reason, "language")
        if found := CRYPTO_TERMS.distinct(labels):
            return Exclusion(f"Kryptowährungen („{found[0]}“)", "crypto")

        gained = snapshot.star_history.gained()
        if gained < MIN_STARS_GAINED:
            return Exclusion(
                f"Nur {number(gained)} neue Sterne in 7 Tagen, nötig sind {MIN_STARS_GAINED}",
                "low_momentum",
            )
        return None


def prose(markdown: str) -> str:
    """The running text of a README: without code, links, images and HTML."""
    text = _CODE_BLOCK.sub(" ", markdown)
    text = _INLINE_CODE.sub(" ", text)
    text = _HTML.sub(" ", text)
    text = _IMAGE.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    return _URL.sub(" ", text)


def foreign_language(description: str, readme: str) -> str | None:
    """Says why the text is neither German nor English, or None if it may be."""
    text = (description + "\n" + prose(readme))[:PROSE_MAX_CHARS]
    letters = [char for char in text if char.isalpha()]
    if letters:
        foreign = sum(1 for char in letters if char > _LAST_LATIN_LETTER) / len(letters)
        if foreign > MAX_FOREIGN_SCRIPT_SHARE:
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
