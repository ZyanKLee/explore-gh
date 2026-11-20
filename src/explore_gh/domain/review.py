"""Review: a language model reads the repos that would be shown, as a last check.

The rules stay the judge of rank. The review can take a repo out, or move it from the
main list to the AI section, never back. It exists because every new campaign of lures,
and every AI project that avoids the usual words, gets past the term lists.
See docs/ausgabe.md, "Gegenlesen".
"""

import dataclasses
from dataclasses import dataclass

from explore_gh.domain.model import Assessment, Exclusion, Section, Signal

REVIEWER_NAME = "Copilot"
AI_FOCUS_CATEGORY = "ai_focus"

# What the review can find. The label is the reason of the exclusion, None means: stays.
REVIEW_CATEGORIES: dict[str, str | None] = {
    "ok": None,
    AI_FOCUS_CATEGORY: None,
    "malware": "Verdacht auf Schadsoftware",
    "piracy": "umgeht Kopierschutz oder verteilt fremde Inhalte",
    "scam": "Betrug oder Spam",
    "no_software": "kein eigenes Softwareprojekt",
    "placeholder": "Hülle ohne erkennbare Arbeit",
    "game_port": "Portierung oder Nachbau eines fremden Spiels",
    "downloader": "lädt Medien von Video- oder Musikplattformen herunter",
    "evasion": "umgeht Schutzmaßnahmen oder Grenzen eines Dienstes",
}

# What the reviewer is told about each category.
REVIEW_GUIDE: dict[str, str] = {
    "ok": "Ein echtes Softwareprojekt. Das ist der Normalfall und gilt auch im Zweifel.",
    AI_FOCUS_CATEGORY: (
        "Ein echtes Softwareprojekt, das für den Einsatz von AI gebaut ist: "
        "Sprachmodelle (LLMs) und ihre Technik, Agenten, Chatbots, Generatoren für "
        "Bilder, Musik, Video oder Sprache, samt Modellen, Benchmarks und Forschungs-Code "
        "dafür. Nicht gemeint: klassisches maschinelles Lernen (Statistik, Bilderkennung, "
        "Zeitreihen) und Software, die AI nur als Nebenfunktion anbietet."
    ),
    "malware": (
        "Köder für Schadsoftware: gibt sich als bekannte Software, Crack, Cheat oder "
        "Gratis-Version aus und führt zu einem Download (ZIP, EXE, Passwort, externer "
        "Link, kopierter Befehl), statt Quellcode zu zeigen."
    ),
    "piracy": (
        "Dient erkennbar dazu, Kopierschutz oder Lizenzprüfungen zu umgehen oder "
        "urheberrechtlich geschützte Inhalte zu verteilen: Cracks, Keygens, "
        "Lizenzschlüssel, Listen illegaler Streams. Dazu alles, was DRM bricht: "
        "Widevine, PlayReady oder FairPlay aushebeln, Schlüssel aus einem CDM ziehen "
        "oder eigene CDMs nachbauen, verschlüsselte Streams oder E-Books "
        "entschlüsseln, auch wenn das README es Backup, Archiv oder Forschung nennt. "
        "Ebenso: Patches, die Premium- oder Pro-Funktionen fremder Apps freischalten; "
        "Jailbreak- und Exploit-Werkzeuge für Spielkonsolen und Lader für Spiele-Dumps; "
        "Player, die über Erweiterungen auf Film-, Serien- oder TV-Streams zugreifen "
        "(CloudStream-Erweiterungen, Stremio-Add-ons, Kodi-Builds); Repos, die "
        "Spieldaten, ROMs, Filme, Musik oder Bücher anderer selbst verteilen, auch über "
        "Releases. Ein Abspielprogramm oder Emulator allein gehört nicht dazu."
    ),
    "scam": "Betrug, Spam, reine Werbung oder Suchmaschinen-Köder ohne eigenes Projekt.",
    "no_software": (
        "Kein Softwareprojekt: Linksammlung, Kursmaterial, Vorbereitung auf "
        "Bewerbungsgespräche, persönliche Konfiguration, Prompt-Sammlung, Kopie des "
        "Projekts eines anderen."
    ),
    "placeholder": (
        "Leere Hülle: Ankündigung ohne Code, Platzhalter, automatisch erzeugter Inhalt "
        "ohne erkennbare eigene Arbeit."
    ),
    "game_port": (
        "Bringt ein bestehendes, fremdes Spiel auf eine andere Plattform oder baut es "
        "nach: Decompilation, statische Recompilation (Recomp), Source-Port, PC-Port "
        "eines Konsolenspiels, Fan-Port, Nachbau der Engine eines bestimmten Spiels. "
        "Auch Werkzeuge, die nur für ein solches Projekt gebaut sind. Nicht gemeint: "
        "eigene Spiele, allgemeine Spiele-Engines, Mods, Emulatoren ganzer Konsolen."
    ),
    "downloader": (
        "Lädt Videos, Musik, Bilder oder ganze Profile von Video-, Musik- oder "
        "Social-Media-Plattformen herunter (YouTube, Instagram, TikTok, Facebook, X, "
        "Twitch, SoundCloud, Spotify …): Downloader, Ripper, Oberflächen für yt-dlp, "
        'Download-Manager, die damit werben. Bricht es dazu DRM, nimm "piracy". '
        "Nicht gemeint: allgemeine Download-Manager und BitTorrent-Clients ohne diese "
        "Werbung, Mediaplayer, Werkzeuge für die eigenen Daten eines Kontos."
    ),
    "evasion": (
        "Umgeht Schutzmaßnahmen oder Grenzen eines fremden Dienstes: löst Captchas oder "
        "Bot-Schutz (Cloudflare Turnstile, Akamai, DataDome), hebelt Gratis- oder "
        "Nutzungsgrenzen aus (Geräte-ID oder Netzausgang wechseln, Konten rotieren), "
        "fälscht Aktivität eines Kontos (Spielzeit, Abzeichen, Aufrufe, Follower, "
        "Selbst-Bots), entfernt die Schutzvorkehrungen eines fremden Programms. "
        "Nicht gemeint: Werbeblocker, Umgehen von Zensur (VPN, Proxy), Sicherheits- und "
        "Testwerkzeuge für eigene oder beauftragte Systeme, Scraper ohne solche Umgehung."
    ),
}


@dataclass(frozen=True)
class Review:
    category: str
    reason: str  # one sentence of the model. Only the log of the run shows it.

    def __post_init__(self):
        if self.category not in REVIEW_CATEGORIES:
            raise ValueError(f"Unbekannte Kategorie: {self.category!r}")


def reviewed(assessment: Assessment, review: Review) -> Assessment:
    """The assessment after the review: excluded, moved to the AI section, or marked as read.

    The page only ever shows a fixed sentence, never the model's own words.
    """
    if assessment.exclusion is not None:
        return assessment
    if review.category == AI_FOCUS_CATEGORY and assessment.section is Section.MAIN:
        signal = Signal("review", 0, f"Gegengelesen von {REVIEWER_NAME}: AI als Thema")
        return dataclasses.replace(
            assessment, section=Section.AI, signals=assessment.signals + (signal,)
        )
    label = REVIEW_CATEGORIES[review.category]
    if label is None:
        signal = Signal("review", 0, f"Gegengelesen von {REVIEWER_NAME}: unauffällig")
        return dataclasses.replace(assessment, signals=assessment.signals + (signal,))
    exclusion = Exclusion(f"Gegengelesen von {REVIEWER_NAME}: {label}. {review.reason}", "review")
    return dataclasses.replace(assessment, exclusion=exclusion)
