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
github-anti-ai publish [--ignore-cooldown] [--allow-incomplete] [--day T]
                                                     # Ausgabe erzeugen (Standard: heute)
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
Signal(kind, weight, reason)   # reason ist der Text der Begründung auf der Seite
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

## Community-Ausgaben (HN, Lobsters)

HN und Lobsters haben eigene Ausgaben (`HnEdition`, `LobstersEdition`) mit eigenem
Speicherformat. Die Auswahlregeln sind für beide gleich und stehen deshalb nur einmal
im Code: im gemeinsamen Kurator `CommunityCurator` (`domain/community.py`). Die
Kuratoren der Plattformen (`HnEditionCurator`, `LobstersEditionCurator`) geben ihm nur
ihre Rangfolge mit und verpacken das Ergebnis in ihre Ausgabe.

Auswahlregeln (`CommunityCurator.select`):

1. Es bleiben nur Open-Source-Projekte (siehe „Lizenz“ in `datensammlung.md`) mit
   erkanntem Code, ohne Forks und ohne archivierte Repos.
2. **Sperre:** Ein Repo, das an Tag D in einer Ausgabe derselben Plattform stand, ist
   bis einschließlich D + 29 gesperrt, wie bei GitHub (`COOLDOWN_DAYS`,
   `recently_shown`). Abgeleitet wird das aus den eigenen Ausgaben der letzten 30 Tage.
   HN und Lobsters sperren sich nicht gegenseitig, und auch nicht gegen die
   GitHub-Listen.
3. **Ein Repo nur einmal:** Verlinken mehrere Storys dasselbe Repo, zählt die Story
   mit dem besseren Rang. Gleich sind Repos, deren Adressen bis auf Groß- und
   Kleinschreibung und einen Schrägstrich am Ende übereinstimmen.
4. **Rangfolge:** von der Plattform vorgegeben.
   - HN: Punkte, dann Kommentare, dann die neuere Story.
   - Lobsters: Score, dann Kommentare, dann die neuere Story.
5. **Vielfalt:** Der Reihe nach übernehmen. Ein Projekt wird übersprungen, wenn seine
   Sprache schon 4-mal oder sein Besitzer schon 2-mal in der Ausgabe steht
   (`MAX_PER_LANGUAGE`, `MAX_PER_OWNER`, wie bei GitHub). Projekte ohne erkannte Sprache
   bilden eine eigene Gruppe. Besitzer ist der erste Teil des Pfads zusammen mit der
   Forge: `github.com/alice` und `codeberg.org/alice` sind zwei Besitzer (`owner_key`).
6. Schluss nach 20 Projekten. Die Ausgabe wird nie aufgefüllt.

`HnEdition` und `LobstersEdition` prüfen beim Erzeugen selbst, dass sie höchstens 20
Projekte enthalten, kein Repo doppelt und die Vielfaltsregel einhalten
(`check_community_edition`). Das gilt auch beim Laden aus dem Archiv.

Welches Repo zu einer Story gehört, entscheidet schon die Datensammlung (siehe
„Bezug zur Story“ in `datensammlung.md`).

### Geplant

Damit HN und Lobsters denselben Regeln folgen wie die GitHub-Listen, kommen in dieser
Reihenfolge in den gemeinsamen Kurator:

- **AI-Sektion:** derselbe `AiFocusClassifier` wie bei GitHub, aus Name,
  Beschreibung, Topics und README.
- **Ausschlüsse:** dieselbe `ExclusionPolicy`, soweit sie ohne Sternverlauf auskommt
  (Sammlungen, Köder, Kryptowährungen, kein README, Sprache).
- **„Warum Platz …?“:** wie das Repo gefunden wurde und welche Signale es hat.

Bewusst nicht vorgesehen: die Abwertung für AI-Mithilfe, weil sie Commits von allen
Forges bräuchte. Die Plattform-Vorlieben (Linux, Windows, Apple) sind noch nicht
entschieden.

## Unvollständige Sammlung

Eine Ausgabe wird nie ersetzt, und ihre Repos sind 30 Tage gesperrt. Deshalb darf sie
nicht aus einer Sammlung mit Lücken entstehen.

- `collect` hält am Ende jedes Laufs fest, wie er ausging:
  `data/snapshots/JJJJ-MM-TT.status.json` mit der Zahl der gefundenen, gesammelten und
  fehlgeschlagenen Repos. Ein späterer Lauf desselben Tages überschreibt die Datei.
- `publish` lehnt ab (`IncompleteCollection`), wenn
  - es für den Tag keinen Status gibt: Der Lauf wurde abgebrochen, oder die Daten
    stammen aus der Zeit vor dieser Regel (vor dem 13.11.2026).
  - der Status fehlgeschlagene Repos nennt.
- Repos, die es nicht mehr gibt, machen eine Sammlung nicht unvollständig.
- `daily` erzeugt damit nach einem Lauf mit Fehlern keine Ausgabe.
- **Bewusst übergehen:** `publish --allow-incomplete` und `daily --allow-incomplete`.
- Der Status wird wie die Momentaufnahmen nach 14 Tagen gelöscht.
