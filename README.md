# github-anti-ai

Eine persönliche „Explore“-Seite für GitHub. Sie zeigt jeden Tag 20 aufstrebende Repos,
die überwiegend von Menschen geschrieben wurden, und getrennt davon 20 Repos zum Thema
AI. Köder für Schadsoftware, Linksammlungen, Kryptowährungen und Repos in fremden
Sprachen fliegen raus.

Das Ergebnis ist eine statische Website mit Archiv und zwei Feeds.

## Einmalig einrichten

1. **`uv` installieren**, falls noch nicht vorhanden: <https://docs.astral.sh/uv/>
2. **GitHub-Token anlegen:** auf GitHub unter *Settings → Developer settings →
   Personal access tokens → Tokens (classic)* einen Token **ohne Scopes** erzeugen.
   Er darf nur lesen, was ohnehin öffentlich ist.
3. **Token ablegen:** im Projektverzeichnis eine Datei `.env` mit dieser einen Zeile
   anlegen:

   ```
   GITHUB_TOKEN=dein_token
   ```

   Die Datei ist von Git ausgenommen. Den Token nie in einen Chat oder ins Repo
   kopieren.

Alle Befehle unten laufen im Projektverzeichnis.

## Daten aktualisieren und Seite neu bauen

Drei Schritte, in dieser Reihenfolge:

```
uv run github-anti-ai collect    # 1. Momentaufnahmen von GitHub holen
uv run github-anti-ai publish    # 2. Ausgabe des Tages erzeugen
uv run github-anti-ai site       # 3. Website bauen
```

Danach `output/index.html` im Browser öffnen.

### 1. Sammeln (`collect`)

- Dauert beim ersten Mal knapp 40 Minuten (gemessen mit 2937 Repos) und zeigt den
  Fortschritt an. An den Folgetagen sind es etwa 8 Minuten, weil der Lauf die
  Momentaufnahmen der letzten Tage weiterverwendet und nur Neues holt.
- Speichert nach jedem Block von 20 Repos. Bricht der Lauf ab, einfach denselben
  Befehl noch einmal starten: Er holt nur noch, was fehlt.
- Steht am Ende „… fehlgeschlagen, ein erneuter Lauf holt sie nach“, den Befehl
  ebenfalls noch einmal starten. Vorher weigert sich `publish`, eine Ausgabe zu
  erzeugen.
- Für einen schnellen Probelauf: `uv run github-anti-ai collect --limit 60`

### 2. Ausgabe erzeugen (`publish`)

- Bewertet alle Momentaufnahmen des Tages und wählt je 20 Repos für Hauptliste und
  AI-Sektion aus. Das dauert wenige Sekunden.
- Das Ergebnis ist eine Datei in `data/editions/`, zum Beispiel `2026-11-13.json`.
- Ist die Sammlung des Tages unvollständig oder wurde sie abgebrochen, lehnt der
  Befehl ab. `--allow-incomplete` übergeht das, wenn es wirklich sein soll.
- Eine Ausgabe wird nie überschrieben. Wer den Tag neu erzeugen will, löscht vorher
  die Datei dieses Tages.
- Ein gezeigtes Repo ist danach 30 Tage gesperrt.
- Hat das Sammeln über Mitternacht gedauert, gehören die Daten zum Tag, an dem es
  begonnen hat: `uv run github-anti-ai publish --day 2026-11-13`

### 3. Website bauen (`site`)

- Baut aus allen Ausgaben in `data/editions/` die Seite nach `output/`.
- Der Schritt fragt GitHub nicht ab und lässt sich beliebig oft wiederholen.
- Soll die Seite ins Netz, braucht der Befehl ihre Adresse, damit die Feeds
  vollständige Links bekommen: `uv run github-anti-ai site --site-url https://…`
- Mit `--plausible https://…/js/….js` zählt die Seite ihre Besuche über Plausible.
  Auf GitHub ist das eingeschaltet, lokal nicht.

### Schritt 1 und 2 in einem

```
uv run github-anti-ai daily      # sammeln und Ausgabe erzeugen
uv run github-anti-ai site
```

## Vorschau im Browser

```
uv run github-anti-ai serve
```

Baut die Seite und zeigt sie unter <http://127.0.0.1:8000>. Ändert sich eine Ausgabe
in `data/editions/` oder eine Datei des Themes, baut der Befehl neu und der Browser
lädt die Seite von selbst nach. Strg+C beendet die Vorschau. Mit `--port 8080` läuft
sie auf einem anderen Port.

Die Vorschau ist nur vom eigenen Rechner aus erreichbar.

## Nachsehen, warum ein Repo so bewertet wurde

```
uv run github-anti-ai explain owner/name
```

Zeigt Sektion, Punktzahl, Ausschlussgrund und jedes Signal mit Gewicht. Das geht auch
für Repos, die es nicht in die Ausgabe geschafft haben. Mit `--day 2026-11-13` für
einen anderen Tag. Auf der Website steht dasselbe unter „Warum Platz …?“ bei jedem Eintrag.

## Ausprobieren, ohne das Archiv anzufassen

Alle Befehle kennen `--data-dir`. Ein eigenes Verzeichnis hält Versuche vom echten
Archiv fern:

```
uv run github-anti-ai collect --data-dir data-test --limit 60
uv run github-anti-ai publish --data-dir data-test --ignore-cooldown --allow-incomplete
uv run github-anti-ai site    --data-dir data-test --output data-test/site
```

`--ignore-cooldown` schaltet die 30-Tage-Sperre ab. Verzeichnisse, die mit `data-`
beginnen, sind von Git ausgenommen.

## Wo was liegt

| Ort | Inhalt |
|---|---|
| `data/snapshots/` | Momentaufnahmen, Arbeitsdaten für 14 Tage, nicht in Git |
| `data/editions/` | die Ausgaben, eine Datei pro Tag, in Git |
| `data/history/` | Langzeitdaten: Zahlen und Urteil zu jedem bewerteten Repo, eine Datei pro Tag, in Git |
| `output/` | die gebaute Website, nicht in Git |
| `docs/` | Konzepte: Datensammlung, Bewertung, Ausgabe, Veröffentlichung |
| `AGENTS.md` | Entscheidungen, Glossar und Regeln für die Entwicklung |

Die Regeln der Bewertung und ihre Punktwerte stehen in `docs/bewertung.md`.

## Regeln ändern

Punktwerte und Begriffslisten stehen als benannte Konstanten in
`src/github_anti_ai/domain/`. Nach einer Änderung prüfen die Tests, ob alles noch
zusammenpasst:

```
uv run pytest
```

Eine Regeländerung wirkt nur auf künftige Ausgaben. Vergangene Tage werden nie neu
berechnet.

## Automatischer Betrieb auf GitHub

Ein Workflow sammelt jeden Morgen um 05:17 UTC, erzeugt die Ausgabe und schreibt sie
ins Repo. Danach startet von selbst ein zweiter, der die Seite auf GitHub Pages
veröffentlicht. Dafür braucht das Repo zweierlei:

1. **Secret `COLLECT_TOKEN`:** unter *Settings → Secrets and variables → Actions* einen
   klassischen Personal Access Token ohne Scopes eintragen.
2. **Pages:** unter *Settings → Pages* als Quelle „GitHub Actions“ wählen.

Von Hand starten: im Reiter *Actions* den Workflow „Tägliche Ausgabe“ wählen und
*Run workflow* drücken. Der Workflow „Website“ baut nur die Seite neu, etwa nach einer
Änderung am Aussehen.

Scheitert das Sammeln, gibt es an dem Tag keine Ausgabe. Die Seite bleibt, wie sie
war, und GitHub schickt eine Mail über den gescheiterten Lauf.
