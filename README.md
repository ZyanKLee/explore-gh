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

- Dauert 30 bis 45 Minuten und zeigt den Fortschritt an.
- Speichert nach jedem Block von 20 Repos. Bricht der Lauf ab, einfach denselben
  Befehl noch einmal starten: Er holt nur noch, was fehlt.
- Steht am Ende „… fehlgeschlagen, ein erneuter Lauf holt sie nach“, den Befehl
  ebenfalls noch einmal starten, bevor es weitergeht.
- Für einen schnellen Probelauf: `uv run github-anti-ai collect --limit 60`

### 2. Ausgabe erzeugen (`publish`)

- Bewertet alle Momentaufnahmen des Tages und wählt je 20 Repos für Hauptliste und
  AI-Sektion aus. Das dauert wenige Sekunden.
- Das Ergebnis ist eine Datei in `data/editions/`, zum Beispiel `2026-11-13.json`.
- Eine Ausgabe wird nie überschrieben. Wer den Tag neu erzeugen will, löscht vorher
  die Datei dieses Tages.
- Ein gezeigtes Repo ist danach 30 Tage gesperrt.
- Hat das Sammeln über Mitternacht gedauert, gehören die Daten zum Tag, an dem es
  begonnen hat: `uv run github-anti-ai publish --day 2026-11-13`

### 3. Website bauen (`site`)

- Baut aus allen Ausgaben in `data/editions/` die Seite nach `output/`.
- Der Schritt fragt GitHub nicht ab und lässt sich beliebig oft wiederholen.

### Schritt 1 und 2 in einem

```
uv run github-anti-ai daily      # sammeln und Ausgabe erzeugen
uv run github-anti-ai site
```

## Nachsehen, warum ein Repo so bewertet wurde

```
uv run github-anti-ai explain owner/name
```

Zeigt Sektion, Punktzahl, Ausschlussgrund und jedes Signal mit Gewicht. Das geht auch
für Repos, die es nicht in die Ausgabe geschafft haben. Mit `--day 2026-11-13` für
einen anderen Tag. Auf der Website steht dasselbe hinter dem kleinen (i).

## Ausprobieren, ohne das Archiv anzufassen

Alle Befehle kennen `--data-dir`. Ein eigenes Verzeichnis hält Versuche vom echten
Archiv fern:

```
uv run github-anti-ai collect --data-dir data-test --limit 60
uv run github-anti-ai publish --data-dir data-test --ignore-cooldown
uv run github-anti-ai site    --data-dir data-test --output data-test/site
```

`--ignore-cooldown` schaltet die 30-Tage-Sperre ab. Verzeichnisse, die mit `data-`
beginnen, sind von Git ausgenommen.

## Wo was liegt

| Ort | Inhalt |
|---|---|
| `data/snapshots/` | Momentaufnahmen, Arbeitsdaten für 14 Tage, nicht in Git |
| `data/editions/` | die Ausgaben, eine Datei pro Tag, in Git |
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

## Noch offen

- **Feeds:** Ohne feste Adresse der Seite enthalten sie nur relative Links. Für den
  Betrieb im Netz fehlt noch eine Option für die Adresse.
- **Automatischer Betrieb:** Geplant ist GitHub Pages mit einem täglichen Lauf über
  GitHub Actions. Bisher läuft alles von Hand auf dem eigenen Rechner.
