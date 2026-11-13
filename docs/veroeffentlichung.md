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
   │                         (Texte, Zahlen, Begründung, Verlaufskurve)  
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
- Ist eine Sektion leer, steht dort „Heute nichts gefunden“
- Gibt es noch keine Ausgabe, entsteht eine Startseite mit dem Hinweis „Noch keine
  Ausgabe“

## Ein Eintrag auf der Seite

- Rang, Name als Link zum Repo, Beschreibung
- Programmiersprache, Sterne, Gewinn der letzten 7 Tage („+120 in 7 Tagen“)
- Verlaufskurve der letzten 35 Tage als kleines eingebettetes SVG
- Lizenz, Forks, aktive Autoren, Alter
- Link zur Homepage, falls vorhanden
- **Begründung zum Aufklappen:** „Warum Platz 3? 89,2 Punkte“. Darunter jedes Signal
  mit Gewicht und Text, in der Reihenfolge der Ausgabe, und die Summe. Der Inhalt
  steht im HTML, nicht in JavaScript.

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
- Von sich aus lädt die Seite nichts von fremden Servern: keine Schriften, keine
  Skripte, kein Tracking. Stile und Schrift liegen neben der Seite. JavaScript braucht
  sie nicht. Einzige Ausnahme ist die Besuchszählung, wenn sie eingeschaltet ist (siehe
  unten).

## Format der Ausgaben prüfen

`load_editions` liest nur Dateien mit dem Namen `JJJJ-MM-TT.json`. Hat eine Datei
eine unbekannte `format_version`, bricht der Bau mit einer klaren Meldung ab. Eine
halb verstandene Ausgabe soll nie veröffentlicht werden.

## Kommandozeile

```
github-anti-ai site [--data-dir data] [--output output] [--site-url https://…]
```

`daily` baut die Website nicht. Im Betrieb folgt `site` als eigener Schritt.

## Gestaltung

Entwurf vom 13.11.2026, als Leinwand in Claude Design:
<https://claude.ai/artifact/7vnxersetXqxviX1vi1pQa> (privat).

- **Farben:** kühler heller Grund, kieferngrüne Tinte, dazu ein einziger Akzent:
  Textmarker-Gelb für das, was aufsteigt (der Gewinn der Woche und die Fläche unter
  der Verlaufskurve). Dunkles Schema nach Systemeinstellung.
- **Schrift:** Atkinson Hyperlegible Next, entworfen für gute Lesbarkeit. Die Datei
  liegt im Theme (`theme/static/fonts/`, 34 KB), die Seite lädt weiter nichts von
  fremden Servern.
- **Aufbau:** eine Spalte ohne Karten. Große Rangziffer links, Verlaufskurve rechts,
  auf dem Telefon untereinander.
- **Begründung:** kein Tooltip mehr, sondern ein aufklappbarer Bereich „Warum Platz
  3?“ mit einer Tabelle aller Signale und der Summe. Ein Tooltip war mit Tastatur und
  auf dem Telefon schlecht erreichbar. Der Bereich ist ein `<details>`-Element und
  braucht kein JavaScript.

### Nachschliff

Am 13.11.2026 gegen die Prüfliste „unslop“ von Damir Sokolovsky geprüft
(<https://github.com/heydamir/unslop>, CC BY 4.0). Grobe Merkmale generierter Seiten
fand sie nicht. Nachgebessert wurde:

- **Gewichte:** Nur der Tagestitel und die Rangziffer sind sehr fett (800). Alles
  andere, was hervorgehoben ist, hat 600. Die Prüfliste will höchstens 600 überall;
  die beiden Ausnahmen sind bewusst, sie sind das Erkennungsmerkmal der Seite.
- **Laufweite:** eng nur bei Tagestitel und Rangziffer.
- **Abstände** auf einem 4-Pixel-Raster.
- **Rundungen:** Schaltflächen 8 Pixel, nichts unter 4. Eine volle Rundung hat nur
  noch das Sprach-Etikett.
- **Kurze Zeilen ohne Punkt am Ende.**

### Barrierefreiheit

- **Kontrast:** Jeder Text erreicht mindestens 6,5:1 gegen seinen Grund, in beiden
  Farbschemata (gerechnet, WCAG AAA verlangt 7:1 für Fließtext, AA 4,5:1).
- **Tastatur:** Sprunglink zum Inhalt, deutlich sichtbarer Fokus, alle Bedienelemente
  mindestens 44 Pixel hoch.
- **Nicht nur Farbe:** Plus und Minus stehen als Zeichen vor dem Gewicht, die aktuelle
  Seite ist per `aria-current` und Unterstrich markiert.
- **Screenreader:** Liste als Liste, Rangziffer versteckt (die Liste zählt selbst),
  Verlaufskurve mit Beschriftung, Tabelle mit Überschrift.
- **Rücksicht:** weniger Bewegung, erzwungene Farben (Kontrastmodus) und Druck sind
  berücksichtigt.
- **Nicht geprüft:** mit einem echten Screenreader und mit einem Prüfwerkzeug wie axe.

## Vorschau (`serve`)

```
github-anti-ai serve [--data-dir data] [--output output] [--port 8000]
```

`src/github_anti_ai/publication/dev_server.py` baut die Seite, liefert sie auf
`127.0.0.1` aus und baut neu, sobald sich eine Datei in `data/editions/` oder im Theme
ändert. Geprüft wird zweimal pro Sekunde.

- **Der Browser lädt selbst nach.** Dafür fügt der Server beim Ausliefern ein kleines
  Skript in die HTML-Seiten ein, das jede Sekunde nach der Version fragt. Die gebauten
  Dateien in `output/` bleiben ohne Skript.
- **Schlägt ein Bau fehl**, meldet die Vorschau den Fehler und zeigt weiter die letzte
  funktionierende Seite.
- Pelicans eigenes `--autoreload` passt hier nicht: Es überwacht einen Inhaltsordner
  und eine Einstellungsdatei, beides gibt es bei uns nicht.

## Besuchszählung

Seit dem 13.11.2026 zählt die veröffentlichte Seite ihre Besuche mit Plausible, über
die eigene Instanz des Projektinhabers.

- `site --plausible https://…/js/….js` bindet das Skript in jede Seite ein. Ohne die
  Option bleibt die Seite frei von Skripten. Lokale Bauten und die Vorschau zählen
  deshalb nicht.
- Die Adresse des Skripts steht in den Workflows (`PLAUSIBLE_SCRIPT`), nicht im Code.
- Die Fußzeile sagt, was gilt: „Besuche zählt Plausible, ohne Cookies und ohne Angaben
  zur Person.“ oder „Ohne Tracking, ohne Skripte.“
- Die Adresse muss mit `https://` beginnen. Die Feeds enthalten nie ein Skript.

## Adresse der Seite

`site --site-url https://…` nennt die öffentliche Adresse. Die Feeds bekommen damit
vollständige Links und dauerhafte Kennungen, an denen Feed-Leser die Einträge
unterscheiden. Die Seiten selbst behalten relative Links und lassen sich weiter von
der Festplatte öffnen. Ohne die Option enthalten die Feeds nur relative Links. Das
reicht zum Ansehen, nicht zum Abonnieren.

## Offen

- Im Browser geprüft sind Startseite (hell, dunkel, Telefonbreite, aufgeklappte
  Begründung) der echten Ausgabe vom 13.11.2026, per Screenshot. Die Feeds sind in keinem Feed-Leser ausprobiert.

## Betrieb auf GitHub

Drei Workflows in `.github/workflows/`:

| Datei | Wann | Was |
|---|---|---|
| `daily.yml` | täglich 05:17 UTC, oder von Hand | sammeln, Ausgabe erzeugen, ins Repo schreiben |
| `site.yml` | nach jedem erfolgreichen täglichen Lauf, bei Änderungen am Theme oder an den Ausgaben, oder von Hand | die Seite bauen und veröffentlichen |
| `tests.yml` | bei jedem Push und Pull Request | die Tests |

### Der tägliche Lauf

1. **Tag festlegen** (UTC), bevor gesammelt wird.
2. **Momentaufnahmen der letzten Tage** aus dem Cache von GitHub Actions holen. Sie
   liegen nicht im Repo. Fehlt der Cache, holt der Lauf alles neu (etwa 40 Minuten).
3. **Sammeln**, bei Fehlern ein zweiter Versuch. Danach wandern die Momentaufnahmen
   zurück in den Cache, auch wenn der Lauf scheitert.
4. **Ausgabe erzeugen.** Ist die Sammlung unvollständig, bricht der Lauf hier ab: An
   dem Tag gibt es keine Ausgabe, die Seite bleibt, wie sie war. Gibt es die Ausgabe
   des Tages schon, wird der Schritt übersprungen.
5. **Ausgabe ins Repo schreiben** (`data/editions/`), als Commit von
   `github-actions[bot]`. Daraus leitet sich die Sperre ab.
6. **Der Workflow „Website“ startet**, sobald der Lauf erfolgreich fertig ist, und
   baut und veröffentlicht die Seite mit der Adresse von GitHub Pages für die Feeds.
   Was der Lauf ins Repo schreibt, löst von sich aus keinen Workflow aus, deshalb
   hängt „Website“ ausdrücklich an seinem Ende (`workflow_run`). Nur dieser eine
   Workflow veröffentlicht, so kann kein zweiter mit älterem Stand dazwischenkommen.

### Einmalig einrichten

- **Secret `COLLECT_TOKEN`:** ein klassischer Personal Access Token ohne Scopes, unter
  *Settings → Secrets and variables → Actions*. Der eingebaute Token erlaubt nur 1000
  Anfragen pro Stunde, ein erster Lauf braucht rund 3000.
- **Pages:** unter *Settings → Pages* als Quelle „GitHub Actions“ wählen.

### Bekannte Grenzen

- GitHub löscht Caches, die 7 Tage nicht benutzt wurden, und hält höchstens 10 GB je
  Repo. Bei täglichem Lauf bleibt der Cache erhalten. Jeder Lauf legt einen neuen an
  (rund 250 MB bei 14 Tagen), alte räumt GitHub selbst ab.
- Geplante Läufe starten bei hoher Last auf GitHub verspätet.
- Die Workflows sind noch nie gelaufen. Geprüft ist nur, dass die Dateien gültiges
  YAML sind und dass die Befehle darin lokal funktionieren.
- Die Versionen der verwendeten Actions sind am 13.11.2026 gegen die jeweils neueste
  Veröffentlichung geprüft und angehoben worden. `astral-sh/setup-uv` hat keinen
  mitwandernden Hauptversions-Tag mehr und ist deshalb auf eine genaue Version
  festgelegt (`v10.3.3`). Sie muss von Hand angehoben werden.

## Geplant

- Verweis auf die Fundstelle (Hacker News, Lobste.rs), sobald es diese Quellen gibt
