# Ausgabe (Bounded Context „Curation“)

Aus den bewerteten Repos eines Tages entsteht die `Edition` dieses Tages: je Sektion bis
zu 20 Einträge. Eine veröffentlichte Ausgabe wird nie wieder verändert. Sie ist Archiv,
Grundlage der Feeds und Quelle der Sperre.

Die HN- und Lobsters-Ausgaben folgen denselben Auswahlregeln, siehe `community.md`.

## Ablauf

```
PublishEdition.run(tag)
  1. Gibt es die Ausgabe schon?          → AlreadyPublished
  2. Momentaufnahmen des Tages laden     → keine: NothingToPublish
  3. Sammlung vollständig?               → sonst IncompleteCollection (siehe unten)
  4. Jede Momentaufnahme bewerten        Assessor.assess
  5. Kopien ausschließen                 CopyCheck.apply
  6. Ausgaben der Sperrfrist laden       EditionStore.since(tag − 30 Tage)
  7. Gegenlesen (nur mit --review)       Reviewer.review, in Runden
  8. Auswählen                           EditionCurator.curate
  9. Tageswerte speichern                DailyRecordStore.save (siehe langzeitdaten.md)
 10. Ausgabe speichern                   EditionStore.save
```

- `tag` ist der Tag, an dem die Sammlung begann. So findet die Ausgabe ihre
  Momentaufnahmen auch, wenn der Lauf über Mitternacht (UTC) geht.
- **Erst die Tageswerte, dann die Ausgabe:** Scheitert das Speichern der Tageswerte, gibt
  es noch keine Ausgabe, und der Tag lässt sich wiederholen.
- Soll eine Ausgabe während der Entwicklung neu entstehen, löscht man ihre Datei von
  Hand. Einen Schalter zum Überschreiben gibt es bewusst nicht. `EditionStore.save`
  weigert sich ebenfalls.
- **`--ignore-cooldown`** (nur für die Entwicklung) lädt keine früheren Ausgaben. Alle
  anderen Regeln gelten.

## Auswahlregeln (`EditionCurator`, `domain/curation.py`)

Je Sektion, unabhängig voneinander:

1. Ausgeschlossene Repos fallen weg.
2. **Sperre:** Ein Repo, das an Tag D in einer Ausgabe stand, egal in welcher Sektion, ist
   bis einschließlich D + 29 gesperrt und ab D + 30 wieder zulässig. Wird ein Tag neu
   erzeugt, nachdem es schon spätere Ausgaben gibt, sperren auch deren Repos.
   **Umzug und Umbenennung** (seit 20.11.2026): Ein Repo, das den Besitzer wechselt oder
   umbenannt wird, behält den Zeitpunkt seines Anlegens. Gesperrt ist deshalb auch ein Repo
   mit demselben Anlegezeitpunkt (auf die Sekunde) und demselben Besitzer oder Namen.
   Anlass: `Shahrukhalid/nexonic-download-manager` am 18.11. zog zu
   `nexonic-technologies/` um und stand am 20.11. erneut in der Liste. In allen
   Ausgaben bis dahin teilte nur dieses Paar seinen Anlegezeitpunkt. Wechseln Besitzer
   und Name zugleich, greift die Regel nicht. Die HN- und Foren-Listen kennen sie noch
   nicht.
3. **Rangfolge:** Punktzahl absteigend. Bei Gleichstand gewinnt der höhere Sterngewinn,
   danach der alphabetisch frühere Name. Gleiche Eingaben geben immer dieselbe Auswahl.
4. **Vielfalt:** der Reihe nach übernehmen, aber höchstens 4 Repos je Programmiersprache
   und 2 je Besitzer. Repos ohne erkannte Sprache bilden eine eigene Gruppe.
5. Schluss nach 20. Gibt es weniger geeignete Repos, wird die Ausgabe kürzer. Sie wird
   nie aufgefüllt.

Eine Mindestpunktzahl gibt es hier nicht. Was zu schwach ist, schließt die Bewertung aus.

## Aggregate `Edition`

`Edition(day, main, ai, stats)` prüft beim Erzeugen selbst, auch beim Laden aus dem Archiv:

- höchstens 20 Einträge je Sektion
- höchstens 4 je Sprache und 2 je Besitzer und Sektion
- kein Repo doppelt, auch nicht über Sektionen hinweg

Die Reihenfolge der Einträge ist die Rangfolge. Ein `Entry` enthält alles, was die Seite
zeigt, weil die Momentaufnahmen nach 14 Tagen gelöscht werden: Repo, Punktzahl, Signale,
Beschreibung, Homepage, Sprache, Topics, Sterne, Sternverlauf, Erstell- und Push-Datum,
Lizenz, Forks und aktive Autoren (verschiedene Personen hinter den Commits der letzten
90 Tage, ohne Bots).

`EditionStats(assessed, excluded, ai_focused)` hält fest, wie viele Repos an dem Tag
bewertet, ausgeschlossen und als AI-Thema eingestuft wurden.

## Gegenlesen (`Reviewer`, `CopilotReviewer`)

Die Regeln erkennen bekannte Muster, jede neue Kampagne rutscht zunächst durch. Deshalb
liest seit dem 15.11.2026 ein Sprachmodell die Repos gegen, die gezeigt würden. Den Rang
bestimmt es nicht. Es kann ein Repo herausnehmen oder aus der Hauptliste in die
AI-Sektion verschieben, nie umgekehrt.

| Kategorie | Bedeutung | Folge |
|---|---|---|
| `ok` | Ein echtes Softwareprojekt. Gilt auch im Zweifel. | bleibt |
| `ai_focus` | Für den Einsatz von AI gebaut: Sprachmodelle und ihre Technik, Agenten, Chatbots, Generatoren, samt Modellen, Benchmarks und Forschungs-Code. Nicht klassisches maschinelles Lernen, nicht AI als Nebenfunktion. | in die AI-Sektion |
| `malware` | Köder: gibt sich als bekannte Software, Crack oder Gratis-Version aus und führt zu einem Download statt zu Quellcode. | raus |
| `piracy` | Umgeht Kopierschutz oder Lizenzprüfungen oder verteilt geschützte Inhalte. Ein Abspielprogramm oder Emulator allein nicht. | raus |
| `scam` | Betrug, Spam, reine Werbung. | raus |
| `no_software` | Linksammlung, Kursmaterial, Konfiguration, Prompt-Sammlung, Kopie eines fremden Projekts. | raus |
| `placeholder` | Ankündigung ohne Code, automatisch erzeugter Inhalt ohne eigene Arbeit. | raus |
| `game_port` | Bringt ein fremdes Spiel auf eine andere Plattform oder baut es nach: Decompilation, Recompilation, Source-Port, PC-Port, Fan-Port, Nachbau der Engine eines bestimmten Spiels, Werkzeuge nur dafür. Nicht eigene Spiele, allgemeine Engines, Mods, Emulatoren ganzer Konsolen. | raus |

Die genauen Texte stehen in `domain/review.py` (`REVIEW_CATEGORIES`, `REVIEW_GUIDE`).

**Ablauf in Runden** (höchstens 5, `MAX_REVIEW_ROUNDS`):

1. Der Kurator wählt wie immer aus, höchstens 40 Repos.
2. Der Reviewer liest die davon, die er noch nicht gelesen hat. Er bekommt **nur diese**,
   nie die ganze Sammlung.
3. Nimmt er eines heraus oder verschiebt er eines, rückt ein anderes nach. Das wird in der
   nächsten Runde gelesen.

**Folgen:**

- **Herausgenommen:** Ausschluss `review`. Er steht in den Langzeitdaten, nicht auf der
  Seite.
- **Verschoben:** Das Repo wechselt in die AI-Sektion und bekommt das Signal
  „Gegengelesen von Copilot: AI als Thema“. Steht es schon in der AI-Sektion, zählt
  `ai_focus` wie `ok`. Trifft auch eine Ausschluss-Kategorie zu, gilt diese.
- **Gelesen und geblieben:** Signal ohne Punkte „Gegengelesen von Copilot: unauffällig“.
  Fehlt es bei einem Eintrag, wurde er nicht gelesen.
- **Nachvollziehen:** Die Langzeitdaten halten je gelesenem Repo die Kategorie fest. Die
  Begründung des Modells steht nur im Protokoll des Laufs: eine Zeile je herausgenommenem
  oder verschobenem Repo und die Summe („Gegenlesen: 43 gelesen, 2 in die AI-Sektion
  verschoben, 1 herausgenommen“). GitHub hebt Protokolle 90 Tage auf.
- **Fällt der Reviewer aus**, erscheint die Ausgabe ohne Gegenlesen. Das Protokoll nennt
  den Grund und am Ende „Gegengelesen: 0 von 40 Einträgen“.

**Regeln für das Modell:**

- **Geschmack zählt nicht.** Thema, Programmiersprache, Qualität des Codes und der
  Einsatz von AI sind als Ausschlussgrund ausdrücklich untersagt. Sonst entstünde die
  Interessensblase, die das Projekt vermeiden will.
  Einzige Ausnahme ist `game_port` (seit dem 18.11.2026): Die Regel gegen
  Konsolen-Emulatoren (`bewertung.md`) erkennt Portierungen nur, wenn sie eine Konsole
  nennen. Das Modell kennt auch die Spiele.
- **Was es sieht:** je Repo Name, Beschreibung, Topics, Sprache, Sterne, Forks, Alter von
  Repo und Besitzerkonto und die ersten 1500 Zeichen des README. 10 Repos je Aufruf.
- **Fremde Texte im Prompt:** Ein README kann versuchen, das Modell zu überreden. Der
  Prompt warnt davor. Gelingt es trotzdem, bleibt das Repo, wie die Regeln es sagen. Der
  Text des Modells erscheint nie auf der Seite, nur die festen Sätze oben.
- **Technik:** die Copilot-CLI (`copilot -p … -s --no-ask-user --disable-builtin-mcps`).
  Sie ist ein Agent, bekommt hier aber kein Werkzeug, darf nicht nachfragen und startet
  in einem leeren Verzeichnis. Das Modell wählt die CLI, über die Umgebungsvariable
  `COPILOT_MODEL` lässt es sich festlegen. Eine Gruppe, die scheitert, wird übersprungen;
  scheitern alle, fällt der Reviewer aus.
- GitHub Models ist seit dem 30.07.2026 eingestellt und keine Alternative.

## Unvollständige Sammlung

Eine Ausgabe wird nie ersetzt, und ihre Repos sind 30 Tage gesperrt. Deshalb soll sie
nicht aus einer Sammlung mit Lücken entstehen.

- `collect` hält am Ende jedes Laufs fest, wie er ausging (siehe `datensammlung.md`).
- `publish` lehnt ab (`IncompleteCollection`), wenn es für den Tag keinen Status gibt
  (der Lauf wurde abgebrochen) oder der Status fehlgeschlagene Repos nennt. Repos, die es
  nicht mehr gibt, machen eine Sammlung nicht unvollständig.
- **Bewusst übergehen:** `publish --allow-incomplete`, ebenso `daily`.
- **Im Betrieb wird übergangen** (seit 17.11.2026): Eine Ausgabe mit Lücken ist besser
  als ein Tag ohne Inhalt. Der Preis: Ein Repo, das nur wegen eines Fehlers fehlt, kann an
  dem Tag nicht erscheinen.

## Speicherformat

`data/editions/JJJJ-MM-TT.json`, versioniert, lesbar eingerückt. Das Format ist der
Vertrag mit der Veröffentlichung.

```json
{
  "format_version": 1,
  "day": "2026-11-12",
  "growth_window_days": 14,
  "stats": {"assessed": 1834, "excluded": 420, "ai_focused": 212},
  "sections": {
    "main": [
      {
        "rank": 1,
        "repo": "alice/tiny-editor",
        "url": "https://github.com/alice/tiny-editor",
        "description": "A tiny terminal text editor",
        "homepage": null,
        "language": "Rust",
        "topics": ["editor", "terminal"],
        "stars": 812,
        "stars_gained": 120,
        "star_history": [0, 0, 3, 12, 40, 35, 30],
        "created_at": "2026-10-20T12:00:00Z",
        "pushed_at": "2026-11-10T19:02:11Z",
        "license": "MIT",
        "forks": 31,
        "active_authors": 1,
        "score": 25.8,
        "signals": [
          {"kind": "momentum", "weight": 28.8, "reason": "+120 Sterne in 14 Tagen bei 812 insgesamt"},
          {"kind": "ai_files", "weight": -3.0, "reason": "Anweisungsdateien für AI-Agenten: CLAUDE.md"}
        ]
      }
    ],
    "ai": []
  }
}
```

- `star_history`: die neuen Sterne der letzten 35 Tage (oben gekürzt). `stars_gained`:
  die Summe über das Sternfenster.
- `growth_window_days`: wie viele Tage das Sternfenster hatte. In Ausgaben bis zum
  15.11.2026 fehlt das Feld, es waren 7.

## Ports

```python
class EditionStore(Protocol):
    def save(self, edition: Edition) -> None: ...      # AlreadyPublished, falls vorhanden
    def load(self, day: date) -> Edition | None: ...
    def since(self, day: date) -> list[Edition]: ...   # ab day einschließlich, nach Datum

class Reviewer(Protocol):
    def review(self, snapshots: Sequence[Snapshot]) -> dict[RepoId, Review]: ...
    # ein Repo darf in der Antwort fehlen; Ausfall: SourceUnavailable

Assess = Callable[[Snapshot], Assessment]   # die Kommandozeile übergibt Assessor().assess
```

## Kommandozeile

```
explore-gh collect [--limit N]
explore-gh publish [--day T] [--review] [--allow-incomplete] [--ignore-cooldown]
explore-gh daily   [--limit N] [--review] [--allow-incomplete] [--ignore-cooldown]
explore-gh explain owner/name [--day T]
```

`daily` sammelt und veröffentlicht für den Tag, an dem die Sammlung begann. Alle Befehle
kennen `--data-dir` (Standard: `data`). Ein eigenes Verzeichnis für Experimente hält
Testausgaben aus dem versionierten Archiv fern.
