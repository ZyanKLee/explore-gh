"""Review: a language model reads the repos that would be shown, as a last check.

The rules stay the judge of rank. The review can take a repo out or move it from the main
list to the AI section, and it says why. It exists because every new campaign of lures,
and every AI project that avoids the usual words, gets past the lists of terms.
"""

import dataclasses
from dataclasses import dataclass

from github_anti_ai.domain.model import Assessment, Exclusion, Section, Signal

REVIEWER_NAME = "Copilot"

AI_FOCUS_CATEGORY = "ai_focus"

# What the review can find. The label is the reason on the page, None means: stays.
REVIEW_CATEGORIES: dict[str, str | None] = {
    "ok": None,
    AI_FOCUS_CATEGORY: None,
    "malware": "Verdacht auf Schadsoftware",
    "piracy": "umgeht Kopierschutz oder verteilt fremde Inhalte",
    "scam": "Betrug oder Spam",
    "no_software": "kein eigenes Softwareprojekt",
    "placeholder": "Hülle ohne erkennbare Arbeit",
}

# What the reviewer is told about each category. In German: the reasons it writes
# appear on the page.
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
        "Lizenzschlüssel, Listen illegaler Streams. Ein Abspielprogramm oder Emulator "
        "allein gehört nicht dazu."
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
}


@dataclass(frozen=True)
class Review:
    category: str
    reason: str  # one sentence, shown on the page

    def __post_init__(self):
        if self.category not in REVIEW_CATEGORIES:
            raise ValueError(f"Unbekannte Kategorie: {self.category!r}")


def reviewed(assessment: Assessment, review: Review) -> Assessment:
    """The assessment after the review: excluded with the reason, moved to the AI
    section with the reason, or marked as read."""
    if assessment.exclusion is not None:
        return assessment
    if review.category == AI_FOCUS_CATEGORY and assessment.section is Section.MAIN:
        # a fixed sentence: the model's own words never appear on the page
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
