# Langzeitdaten

Umgesetzt am 13.11.2026. Die Tests stehen in `tests/unit/domain/test_daily_record.py`,
`tests/unit/application/test_publish_records.py` und
`tests/integration/test_json_daily_record_store.py`. Der 13.11.2026 ist aus den
vorhandenen Momentaufnahmen und der Ausgabe nachgetragen.

## Aufgabe

`publish` bewertet jeden Tag rund 2800 Repos und wirft die Bewertungen der Repos weg,
die es nicht in die Ausgabe schaffen. Die Momentaufnahmen dazu werden nach 14 Tagen
gelöscht. Danach lässt sich nicht mehr sagen, wie ein Repo an einem Tag bewertet war.

Die Langzeitdaten halten von jeder Bewertung fest, was klein ist und sich später
auswerten lässt: Zahlen und Urteil, keine Texte.

## Zwei Schichten

| | Arbeitsdaten | Langzeitdaten |
|---|---|---|
| Inhalt | Momentaufnahmen mit README und Commits | ein Tageswert je Repo und Tag |
| Ort | `data/snapshots/`, nicht in Git | `data/history/`, in Git |
| Geschrieben von | `collect`, nach jeder Gruppe | `publish`, einmal |
| Aufbewahrung | 14 Tage | dauerhaft |
| Größe pro Tag | 17 MB | 130 KB |

Die Größe, gemessen am 13.11.2026 mit 2846 Repos: 130 KB komprimiert, also rund 47 MB
im Jahr.

## Der Tageswert (`DailyRecord`)

Eine Zeile je bewertetem Repo und Tag, auch für ausgeschlossene Repos.

| Feld | Inhalt |
|---|---|
| `day`, `repo` | Tag und Repo |
| `stars`, `forks`, `stars_gained` | Sterne, Forks, Gewinn der letzten 7 Tage |
| `score`, `section` | Punktzahl und Sektion |
| `exclusion` | Art des Ausschlusses (`lure`, `language` …) oder nichts |
| `signals` | Art und Gewicht jedes Signals, ohne den Begründungstext |
| `rank` | Platz in der Ausgabe, oder nichts, wenn das Repo nicht gezeigt wurde |
| `language`, `created_at` | Programmiersprache, Erstelldatum |

Bewusst nicht dabei:

- **README und Commits.** Sie machen 96 % einer Momentaufnahme aus.
- **Die Beschreibung.** Sie war zuerst dabei und machte 60 % der Datei aus (329 statt
  130 KB pro Tag), weil sie jeden Tag erneut gespeichert wird, obwohl sie sich selten
  ändert. Für ein späteres Textmodell zum AI-Thema reicht es, sie zu den von Hand
  beurteilten Repos zu haben.
- **Namen und E-Mail-Adressen von Personen.** Die Langzeitdaten liegen in Git und
  dürfen so etwas nie enthalten. Ein Test hält die Liste der Felder fest.
- **Begründungstexte der Signale.** Sie lassen sich aus Art, Gewicht und den Zahlen
  nachvollziehen. Für gezeigte Repos stehen sie in der Ausgabe.

## Ablauf in `publish`

```
PublishEdition.run(tag)
  1. prüfen               noch keine Ausgabe, Momentaufnahmen da, Sammlung vollständig
  2. bewerten             alle Momentaufnahmen des Tages
  3. auswählen            EditionCurator → Edition
  4. Tageswerte speichern DailyRecordStore.save(tag, tageswerte)
  5. Ausgabe speichern    EditionStore.save(edition)
```

- **Rang:** Ein gezeigtes Repo bekommt seinen Platz innerhalb seiner Sektion. Ein
  ausgeschlossenes, gesperrtes oder zu schwaches Repo hat keinen.
- **Erst die Tageswerte, dann die Ausgabe.** Eine Ausgabe wird nie ersetzt. Scheitert
  das Speichern der Tageswerte, darf es noch keine Ausgabe geben, damit der Tag
  wiederholt werden kann.
- **Wird ein Tag neu erzeugt** (Ausgabe gelöscht, `publish` erneut), ersetzen die neuen
  Tageswerte die alten.
- Lehnt `publish` ab (schon veröffentlicht, unvollständige Sammlung), bleiben die
  Tageswerte unberührt.

## Speicherung (`JsonDailyRecordStore`)

- `data/history/JJJJ-MM-TT.jsonl.gz`: eine Datei pro Tag, eine Zeile je Repo, sortiert
  nach Repo-Namen ohne Rücksicht auf Groß- und Kleinschreibung.
- **Jede Zeile steht für sich:** Sie nennt ihren Tag (`day`) und ihr Format (`v`).
  Werkzeuge wie DuckDB oder pandas können so einen ganzen Ordner auf einmal lesen.
- Punktzahl und Gewichte stehen mit zwei Nachkommastellen in der Datei.
- **Gleiche Tageswerte ergeben dieselbe Datei**, Byte für Byte. Die Dateien liegen in
  Git, ein erneutes Schreiben darf nicht wie eine Änderung aussehen.
- Eine Datei mit unbekanntem Format wird abgelehnt.
- Es gibt kein Aufräumen. Die Dateien bleiben.

```python
class DailyRecordStore(Protocol):
    def save(self, day: date, records: Sequence[DailyRecord]) -> None: ...   # ersetzt den Tag
    def load(self, day: date) -> list[DailyRecord]: ...
    def days(self) -> list[date]: ...
```

## Warum JSONL und keine Datenbank

Besprochen am 13.11.2026:

- **Git-freundlich:** eine Datei pro Tag, die nach dem Schreiben nicht mehr verändert
  wird. Eine wachsende SQLite-Datei würde Git jeden Tag komplett neu speichern.
- **Keine neue Abhängigkeit**, anders als Parquet.
- **Signale sind eine Liste.** In JSON ist das natürlich, in CSV nicht.
- **Schnell genug:** Ein Jahr mit gut einer Million Zeilen liest reines Python in 3,2
  Sekunden.
- **Nichts verbaut:** Aus JSONL lässt sich jederzeit Parquet, SQLite oder DuckDB
  erzeugen.

Der tägliche Lauf selbst liest die Langzeitdaten nicht. Was eine Regel aus der
Vergangenheit braucht, trägt die Momentaufnahme mit, so wie den Sternverlauf.

## Offen

- Der tägliche Workflow schreibt `data/history/` mit ins Repo. Gelaufen ist das noch
  nicht.

## Geplant

- Ein Befehl, der den Verlauf eines Repos über die Tage zeigt.
- Ein abgeleiteter Index (SQLite oder DuckDB), wenn Abfragen über viele Tage zu
  langsam werden. Er wird aus den Tagesdateien gebaut und kommt nicht in Git.
- Die Daten in einen eigenen Zweig verschieben, falls das Repo zu groß wird.
