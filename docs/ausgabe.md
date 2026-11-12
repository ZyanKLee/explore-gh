# Ausgabe (Bounded Context „Curation“)

## Aufgabe

Aus den bewerteten Repos eines Tages entsteht die `Edition` dieses Tages: je Sektion
bis zu 20 Einträge. Eine veröffentlichte Ausgabe wird nie wieder verändert. Sie ist
Archiv, Grundlage für den RSS-Feed und Quelle der Sperre.

## Ablauf

```
PublishEdition.run()
  1. Gibt es für heute schon eine Ausgabe?  → AlreadyPublished, nichts tun
  2. Momentaufnahmen von heute laden        → keine: NothingToPublish
  3. Jede Momentaufnahme bewerten           assess(snapshot) → Assessment
  4. Ausgaben der Sperrfrist laden          EditionStore.since(tag − 30 Tage)
  5. Auswählen                              EditionCurator.curate(...)
  6. Speichern                              EditionStore.save(edition)
```

Täglicher Betrieb: zuerst `CollectSnapshots`, dann `PublishEdition`, im selben Lauf.
`PublishEdition.run(day)` nimmt den Tag der Sammlung entgegen. So findet die Ausgabe
ihre Momentaufnahmen auch dann, wenn der Lauf über Mitternacht (UTC) geht.

Soll eine Ausgabe während der Entwicklung neu entstehen, löscht man ihre Datei von
Hand. Einen Schalter zum Überschreiben gibt es bewusst nicht.

**Entwicklungsschalter `--ignore-cooldown`:** `PublishEdition(ignore_cooldown=True)`
lädt keine früheren Ausgaben. Die Sperre greift dann nicht, alle anderen Regeln
schon. Die Domäne bleibt unverändert.

## Kommandozeile

```
github-anti-ai collect [--limit N]                   # Momentaufnahmen sammeln
github-anti-ai publish [--ignore-cooldown] [--day T]  # Ausgabe erzeugen (Standard: heute)
github-anti-ai daily [--limit N] [--ignore-cooldown] # beides nacheinander
github-anti-ai explain owner/name [--day T]          # Bewertung eines Repos erklären
github-anti-ai site [--output output]                # Website bauen (siehe veroeffentlichung.md)
```

`--day JJJJ-MM-TT` wählt die Sammlung eines anderen Tages. `daily` veröffentlicht
immer für den Tag, an dem die Sammlung begonnen hat.

Optionen für alle Befehle: `--data-dir` (Standard: `data`). Ein eigenes Verzeichnis
für Experimente verhindert, dass Testausgaben im versionierten Archiv landen.

## Was „Curation“ von „Assessment“ erwartet

Die Auswahl braucht von der Bewertung (siehe `bewertung.md`) nur diese Form:

```python
Assessment(snapshot, section, score, signals, exclusion)
Signal(kind, weight, reason)   # reason ist der Tooltip-Text
Exclusion(reason, kind)
```

`PublishEdition` nimmt die Funktion `assess` als Parameter entgegen. Die Kommandozeile
übergibt `Assessor().assess`.

## Auswahlregeln (`EditionCurator`)

Pro Sektion, unabhängig voneinander:

1. Ausgeschlossene Repos (`exclusion` gesetzt) fallen weg.
2. **Sperre:** Ein Repo, das an Tag D in einer Ausgabe stand, egal in welcher Sektion,
   ist bis einschließlich D + 29 gesperrt und ab D + 30 wieder zulässig.
3. **Rangfolge:** Punktzahl absteigend. Bei Gleichstand gewinnt der höhere
   Sterngewinn, danach der alphabetisch frühere Name. Die Auswahl ist so bei gleichen
   Eingaben immer gleich.
4. **Vielfalt:** Der Reihe nach übernehmen. Ein Repo wird übersprungen, wenn seine
   Programmiersprache schon 4-mal oder sein Besitzer schon 2-mal in der Sektion steht.
   Repos ohne erkannte Sprache bilden eine eigene Gruppe mit derselben Grenze.
5. Schluss nach 20 Einträgen. Gibt es weniger geeignete Repos, wird die Ausgabe
   kürzer. Sie wird nie aufgefüllt.

Eine Mindestpunktzahl gibt es hier nicht. Was zu schwach ist, schließt `Assessment`
aus.

## Aggregate `Edition`

`Edition(day, main, ai, stats)` prüft beim Erzeugen selbst:

- höchstens 20 Einträge pro Sektion
- höchstens 4 Einträge pro Sprache und Sektion (ohne Sprache = eine Gruppe)
- höchstens 2 Einträge pro Besitzer und Sektion
- kein Repo doppelt, auch nicht über Sektionen hinweg

Die Reihenfolge der Einträge ist die Rangfolge.

Ein `Entry` enthält alles, was die Seite anzeigt. Die Momentaufnahmen werden nach 14
Tagen gelöscht, das Archiv muss aber für immer lesbar bleiben:
`repo`, `score`, `signals`, `description`, `homepage`, `primary_language`, `topics`,
`stars`, `star_history`, `created_at`, `pushed_at`, `license`, `forks`,
`active_authors` (verschiedene Personen hinter den Commits der letzten 90 Tage, ohne
Bots).

Im JSON steht `star_history` mit den neuen Sternen der letzten 35 Tage (im Beispiel
unten gekürzt) und `stars_gained` als fertige Summe der letzten 7 Tage.

`EditionStats(assessed, excluded, ai_focused)` hält fest, wie viele Repos an dem Tag
bewertet, ausgeschlossen und als AI-Thema eingestuft wurden.

## Speicherformat

Das Format ist der Vertrag mit `Publication` (Pelican-Reader).

`data/editions/YYYY-MM-DD.json`, versioniert im Git-Repo, lesbar eingerückt:

```json
{
  "format_version": 1,
  "day": "2026-11-12",
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
        "score": 0.83,
        "signals": [
          {"kind": "ai_assistance", "weight": -0.2, "reason": "CLAUDE.md im Hauptverzeichnis"}
        ]
      }
    ],
    "ai": []
  }
}
```

`EditionStore.save` weigert sich, eine vorhandene Ausgabe zu überschreiben
(`AlreadyPublished`). Das ist eine zweite Absicherung zusätzlich zur Prüfung im
Use Case.

## Ports

```python
class EditionStore(Protocol):
    def save(self, edition: Edition) -> None: ...      # AlreadyPublished, falls vorhanden
    def load(self, day: date) -> Edition | None: ...
    def since(self, day: date) -> list[Edition]: ...   # ab day einschließlich, nach Datum sortiert

Assessor = Callable[[Snapshot], Assessment]
```

## Auswirkungen auf die Datensammlung

- Die Sperre wird aus den Ausgaben abgeleitet. Die 14-tägige Aufbewahrung der
  Momentaufnahmen bleibt deshalb unabhängig von der 30-tägigen Sperre.
- Ein `Entry` übernimmt die Anzeigedaten aus der Momentaufnahme. Neue Felder braucht
  die Datensammlung dafür nicht.
- `RepoId` bekommt eine `url`. Die Seite verlinkt damit, ohne URLs selbst
  zusammenzubauen.

## Geplant

- **Unvollständige Sammlung:** `publish` soll warnen oder ablehnen, wenn die Sammlung
  des Tages fehlgeschlagene Repos enthält.
