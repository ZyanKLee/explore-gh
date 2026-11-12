# Veröffentlichung (Bounded Context „Publication“)

## Aufgabe

Aus den gespeicherten Ausgaben (`data/editions/*.json`) entsteht eine statische
Website mit Archiv und Feeds. Die Veröffentlichung kennt nur das JSON-Format aus
`ausgabe.md`. Sie fragt keine API ab, bewertet nichts und wählt nichts aus.

## Aufbau

```
data/editions/*.json
   │  load_editions()        lesen, Format prüfen, nach Datum sortieren
   ▼
section_view()               je Ausgabe und Sektion ein fertiges Seitenmodell
   │                         (Texte, Zahlen, Tooltip-Zeilen, Verlaufskurve)
   ▼
Pelican                      Plugin macht aus jedem Seitenmodell einen Artikel,
   │                         das Theme rendert, Pelican schreibt Archiv und Feeds
   ▼
output/
```

Zwei Teile mit klarer Grenze:

- **Seitenmodell** (`src/github_anti_ai/publication/view.py`): reine Funktionen ohne
  Pelican. Hier steht alles, was Text und Zahlen betrifft. Schnell und einfach zu
  testen.
- **Pelican-Anbindung** (`src/github_anti_ai/publication/pelican_plugin.py` und
  `theme/` daneben): so dünn wie möglich. Das Plugin hängt pro Ausgabe zwei Artikel
  ein (Hauptliste und AI-Sektion). Das Theme setzt nur noch zusammen und denkt sich
  keine Texte aus. Plugin und Theme liegen im Python-Paket, damit der Bau sie
  unabhängig vom Arbeitsverzeichnis findet.

Gebaut wird mit `build_site(editions_dir, output_dir)`
(`src/github_anti_ai/publication/site.py`). Die Funktion ruft Pelican auf.

## Seiten

| Adresse | Inhalt |
|---|---|
| `/` | Hauptliste der neuesten Ausgabe |
| `/ai/` | AI-Sektion der neuesten Ausgabe |
| `/2026/11/12/` | Hauptliste eines Tages |
| `/ai/2026/11/12/` | AI-Sektion eines Tages |
| `/archiv/` | alle Tage, neuester zuerst, je mit Link auf beide Sektionen |
| `/feed.xml` | Atom-Feed der Hauptliste, ein Eintrag pro Tag |
| `/ai/feed.xml` | Atom-Feed der AI-Sektion, ein Eintrag pro Tag |

- Die Hauptliste zeigt nie ein Repo der AI-Sektion und umgekehrt. Das gilt auch für
  die Feeds.
- Jede Tagesseite verlinkt den Tag davor und danach sowie die andere Sektion
  desselben Tages.
- Ist eine Sektion leer, steht dort „Heute nichts gefunden.“
- Gibt es noch keine Ausgabe, entsteht eine Startseite mit dem Hinweis „Noch keine
  Ausgabe.“

## Ein Eintrag auf der Seite

- Rang, Name als Link zum Repo, Beschreibung
- Programmiersprache, Sterne, Gewinn der letzten 7 Tage („+120 in 7 Tagen“)
- Verlaufskurve der letzten 35 Tage als kleines eingebettetes SVG
- Lizenz, Forks, aktive Autoren, Alter
- Link zur Homepage, falls vorhanden
- **(i) mit Begründung:** die Punktzahl und darunter jedes Signal mit Gewicht und
  Text, in der Reihenfolge der Ausgabe. Der Tooltip erscheint beim Überfahren mit
  der Maus und bei Tastaturfokus. Sein Inhalt steht im HTML, nicht in JavaScript.

Über der Liste steht die Statistik des Tages: „1.834 Repos geprüft, 420
ausgeschlossen, 212 als AI-Thema eingestuft“.

## Texte und Zahlen (Seitenmodell)

| Was | Form |
|---|---|
| Titel | „Fundstücke vom 12. November 2026“ / „AI-Sektion vom 12. November 2026“ |
| Zahlen | deutsch mit Tausenderpunkt: `91.943` |
| Gewinn | `+120` |
| Gewichte | eine Nachkommastelle mit Komma und Vorzeichen: `+40,0`, `−3,0`, bei null `0` |
| Punktzahl | eine Nachkommastelle mit Komma: `37,0` |
| Alter | „23 Tage alt“, „1 Tag alt“, „heute erstellt“ |
| Lizenz | Kürzel wie `MIT`. Der GitHub-Platzhalter `NOASSERTION` wird weggelassen. |

## Sicherheit

Beschreibungen, Namen, Topics und Homepage-Adressen stammen von GitHub und damit von
Fremden.

- Alles wird beim Rendern maskiert (Autoescape). Ein `<script>` in einer Beschreibung
  erscheint als Text.
- Eine Homepage wird nur verlinkt, wenn sie mit `http://` oder `https://` beginnt.
- Die Seite lädt nichts von fremden Servern: keine Schriften, keine Skripte, kein
  Tracking. Stile sind eingebettet oder liegen neben der Seite. JavaScript braucht die
  Seite nicht.

## Format der Ausgaben prüfen

`load_editions` liest nur Dateien mit dem Namen `JJJJ-MM-TT.json`. Hat eine Datei
eine unbekannte `format_version`, bricht der Bau mit einer klaren Meldung ab. Eine
halb verstandene Ausgabe soll nie veröffentlicht werden.

## Kommandozeile

```
github-anti-ai site [--data-dir data] [--output output]   # Website bauen
```

`daily` baut die Website nicht. Im Betrieb folgt `site` als eigener Schritt.

## Gestaltung

Schlicht und gut lesbar: eine Spalte, Karten, helles und dunkles Farbschema nach
Systemeinstellung, auf dem Telefon ohne Querscrollen. Die genaue Gestaltung entsteht
beim Bau des Themes und ist nicht Teil der Tests.

## Offen

- **Adresse der Seite für die Feeds:** Ohne feste Adresse enthalten die Feeds nur
  relative Links und keine sauberen Kennungen. Für den Betrieb braucht `site` eine
  Option für die Adresse (z. B. `--site-url`).
- Im Browser geprüft sind bisher nur Startseite und Telefonbreite, an einer
  Beispielseite mit erfundenen Punktzahlen.

## Geplant

- Verweis auf die Fundstelle (Hacker News, Lobste.rs), sobald es diese Quellen gibt
- Betrieb auf GitHub Pages über GitHub Actions
