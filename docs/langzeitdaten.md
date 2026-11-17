# Langzeitdaten

`publish` bewertet jeden Tag rund 2800 Repos, gezeigt werden 40. Die Momentaufnahmen
werden nach 14 Tagen gelöscht. Damit sich später noch sagen lässt, wie ein Repo an einem
Tag bewertet war, hält `publish` von jeder Bewertung fest, was klein ist und sich auswerten
lässt: Zahlen und Urteil, keine Texte.

## Zwei Schichten

| | Arbeitsdaten | Langzeitdaten |
|---|---|---|
| Inhalt | Momentaufnahmen mit README und Commits | ein Tageswert je Repo und Tag |
| Ort | `data/snapshots/`, nicht in Git | `data/history/`, in Git |
| Geschrieben von | `collect`, nach jeder Gruppe | `publish`, einmal |
| Aufbewahrung | 14 Tage | dauerhaft |
| Größe je Tag | rund 17 MB | rund 130 KB (rund 47 MB im Jahr) |

## Der Tageswert (`DailyRecord`)

Eine Zeile je bewertetem Repo und Tag, auch für ausgeschlossene.

| Feld | Inhalt |
|---|---|
| `day`, `repo` | Tag und Repo |
| `stars`, `forks`, `gained` | Sterne, Forks, Gewinn im Sternfenster (14 Tage, bis 15.11.2026: 7) |
| `score`, `section` | Punktzahl und Sektion |
| `exclusion` | Art des Ausschlusses (`lure`, `language`, `review` …) oder nichts |
| `review` | Kategorie des Gegenlesens (`ok`, `ai_focus`, `malware` …). Fehlt, wenn das Repo nicht gelesen wurde. |
| `signals` | Art und Gewicht jedes Signals, ohne Begründungstext |
| `rank` | Platz in der Ausgabe, oder nichts |
| `language`, `created_at` | Programmiersprache, Erstelldatum |

Bewusst nicht dabei:

- **README und Commits:** 96 % einer Momentaufnahme.
- **Die Beschreibung:** Sie war zuerst dabei und machte 60 % der Datei aus, obwohl sie sich
  selten ändert.
- **Namen und E-Mail-Adressen von Personen.** Die Daten liegen in Git. Ein Test hält die
  Liste der Felder fest.
- **Begründungstexte:** Sie folgen aus Art, Gewicht und Zahlen. Für gezeigte Repos stehen
  sie in der Ausgabe.

## Ablauf in `publish`

- Tageswerte werden **vor** der Ausgabe gespeichert. Scheitert das, gibt es noch keine
  Ausgabe und der Tag lässt sich wiederholen.
- Wird ein Tag neu erzeugt (Ausgabe gelöscht, `publish` erneut), ersetzen die neuen
  Tageswerte die alten. Lehnt `publish` ab, bleiben sie unberührt.

## Speicherung (`JsonDailyRecordStore`)

- `data/history/JJJJ-MM-TT.jsonl.gz`: eine Zeile je Repo, sortiert nach Repo-Namen ohne
  Rücksicht auf Groß- und Kleinschreibung.
- **Jede Zeile steht für sich:** Sie nennt Tag (`day`) und Format (`v`). DuckDB oder
  pandas können so einen ganzen Ordner auf einmal lesen.
- Punktzahl und Gewichte mit zwei Nachkommastellen.
- **Gleiche Tageswerte ergeben dieselbe Datei**, damit ein erneutes Schreiben in Git nicht
  wie eine Änderung aussieht. (Auf verschiedenen Rechnern kann zlib die Bytes anders
  packen, der Inhalt bleibt gleich.)
- Eine Datei mit unbekanntem Format wird abgelehnt. Aufgeräumt wird nie.

```python
class DailyRecordStore(Protocol):
    def save(self, day: date, records: Sequence[DailyRecord]) -> None: ...   # ersetzt den Tag
    def load(self, day: date) -> list[DailyRecord]: ...
    def days(self) -> list[date]: ...
```

## Warum JSONL und keine Datenbank

- **Git-freundlich:** eine Datei je Tag, die danach nicht mehr verändert wird. Eine
  wachsende SQLite-Datei würde Git jeden Tag komplett neu speichern.
- **Keine neue Abhängigkeit**, anders als Parquet.
- **Signale sind eine Liste.** In JSON natürlich, in CSV nicht.
- **Schnell genug:** Ein Jahr mit gut einer Million Zeilen liest reines Python in gut 3 Sekunden.
- **Nichts verbaut:** Daraus lässt sich jederzeit Parquet, SQLite oder DuckDB erzeugen.

Der tägliche Lauf selbst liest die Langzeitdaten nicht. Was eine Regel aus der
Vergangenheit braucht, trägt die Momentaufnahme mit, wie den Sternverlauf.

## Geplant

- Ein Befehl, der den Verlauf eines Repos über die Tage zeigt.
- Ein abgeleiteter Index (SQLite oder DuckDB), wenn Abfragen über viele Tage zu langsam
  werden. Er wird aus den Tagesdateien gebaut und kommt nicht in Git.
- Die Daten in einen eigenen Zweig verschieben, falls das Repo zu groß wird.
