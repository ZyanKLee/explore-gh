# Veröffentlichung (Bounded Context „Publication“)

Aus den gespeicherten Ausgaben (`data/editions/`, `data/hn-editions/`,
`data/lobsters-editions/`) entsteht eine statische Website mit Archiven und Feeds je
Liste und Sektion. Die Veröffentlichung kennt nur das JSON-Format dieser Dateien. Sie
fragt keine API ab, bewertet nichts und wählt nichts aus.

## Aufbau

```
data/editions/*.json            GitHub-Ausgaben
data/hn-editions/*.json         HN-Ausgaben
data/forums-editions/*.json     Foren-Ausgaben, eine je Woche (Datum des Montags)
data/lobsters-editions/*.json   Lobsters-Ausgaben bis 17.11.2026 (Archiv)
   │  lesen, Format prüfen, nach Datum sortieren
   ▼
Seitenmodell                    je Tag und Sektion fertige Texte und Zahlen
   │                            (view.py, community_view.py, german.py)
   ▼
Pelican-Plugin                  je Tag und Sektion ein Artikel (Tagesseite, Feed-Eintrag),
   │                            je Liste die neuesten Seiten und das Archiv
   ▼
Theme → output/
```

- **Seitenmodell:** reine Funktionen ohne Pelican. Hier steht alles, was Text und Zahlen
  betrifft. HN, Foren und Lobsters unterscheiden sich nur in einer `Platform` (Name, Adresse,
  Bezeichnung der Punkte, Diskussion, täglich oder wöchentlich). In den Foren nennt jeder
  Eintrag seine Herkunft: „34 Punkte auf Lobsters“, „Diskussion auf Lemmy c/rust“.
- **Pelican-Anbindung** (`pelican_plugin.py`, `site.py`, `theme/`): so dünn wie möglich.
  Das Plugin beschreibt die drei Listen in einer Tabelle (`PageList`) und erzeugt für jede
  dieselben Seiten. Das Theme setzt nur zusammen und denkt sich keine Texte aus. Plugin
  und Theme liegen im Python-Paket.
- Gebaut wird mit `build_site(data_dir, output_dir)`.

## Seiten

| Adresse | Inhalt |
|---|---|
| `/` | Trending auf GitHub, neueste Ausgabe (Hauptliste) |
| `/ai/` | AI-Projekte auf GitHub, neueste Ausgabe |
| `/2026/11/12/`, `/ai/2026/11/12/` | eine Sektion eines Tages |
| `/archiv/` | alle Tage, neuester zuerst, je mit Link auf beide Sektionen |
| `/feed.xml`, `/ai/feed.xml` | Atom-Feeds, ein Eintrag je Tag |
| `/hn/`, `/hn/ai/`, `/hn/2026/11/13/`, `/hn/ai/2026/11/13/`, `/hn/archiv/` | dasselbe für HN |
| `/hn/feed.xml`, `/hn/ai/feed.xml` | Feeds der HN-Liste |
| `/forums/…` | dasselbe für die Foren, eine Seite je Woche („Woche vom 23. November 2026“) |
| `/lobsters/…` | das Archiv der täglichen Lobsters-Liste, ohne Link in der Navigation |

- Die Hauptliste zeigt nie ein Repo der AI-Sektion und umgekehrt, auch in den Feeds.
- Die Hauptnavigation nennt GitHub, HN und die Foren. Alle Seiten einer Plattform markieren
  sie als aktuelle Seite.
- Jede Tagesseite verlinkt den Tag davor und danach, die andere Sektion desselben Tages
  und das Archiv ihrer Plattform.
- Die Adressen der GitHub-Seiten und -Feeds bleiben, wie sie sind, damit Abos weiterlaufen.
- Leere Sektion: „Heute nichts gefunden“, in den Foren „Diese Woche nichts gefunden“. Noch keine Ausgabe: „Noch keine Ausgabe“.

## Ein Eintrag

**GitHub:** Rang, Name als Link, Beschreibung; Sprache, Sterne, Forks, aktive Autoren,
Alter, Lizenz, Homepage; Verlaufskurve der letzten 35 Tage als eingebettetes SVG mit
„+120 Sterne in 14 Tagen“ (die Zahl der Tage nennt die Ausgabe selbst); aufklappbar
„Warum Platz 3? 89,2 Punkte“ mit jedem Signal, Gewicht und Summe. Über der Liste die
Statistik des Tages („1.834 Repos geprüft, 420 ausgeschlossen, 212 als AI-Thema eingestuft“).

**HN, Foren:** Rang, Titel der Story als Link zum Repo, Beschreibung; Sprache, Lizenz,
Punkte, Kommentare, Projektseite, Diskussion; aufklappbar die Begründung (siehe
`community.md`).

## Texte und Zahlen

| Was | Form |
|---|---|
| Titel | „Trending auf GitHub vom 12. November 2026“, „AI-Projekte auf HN vom …“ |
| Zahlen | deutsch mit Tausenderpunkt: `91.943` |
| Gewinn | `+120` |
| Gewichte | eine Nachkommastelle, Komma, Vorzeichen: `+40,0`, `−3,0`, bei null `0` |
| Punktzahl | `37,0` |
| Alter | „23 Tage alt“, „1 Tag alt“, „heute erstellt“ |
| Lizenz | SPDX-Kürzel. `NOASSERTION` wird weggelassen. |

## Sicherheit

Beschreibungen, Namen, Topics und Adressen stammen von Fremden.

- Alles wird beim Rendern maskiert (Autoescape).
- Eine Adresse wird nur verlinkt, wenn sie mit `http://` oder `https://` beginnt.
- Links zu fremden Seiten öffnen einen neuen Tab (`target="_blank"`), die Seite bleibt
  offen. Sie tragen `rel="noopener noreferrer"`: Die fremde Seite kann den Tab der Liste
  nicht steuern und erfährt nicht, woher der Besuch kommt. Links innerhalb der Seite und
  in den Feeds bleiben ohne `target`.
- Die Seite lädt nichts von fremden Servern: keine Schriften, keine Skripte, kein
  Tracking. Stile und Schrift liegen neben der Seite. JavaScript braucht sie nicht.
  Einzige Ausnahme ist die Besuchszählung, wenn sie eingeschaltet ist.
- Eine Datei mit unbekanntem `format_version` bricht den Bau ab. Eine halb verstandene
  Ausgabe soll nie erscheinen. Gelesen werden nur Dateien namens `JJJJ-MM-TT.json`.

## Adresse und Besuchszählung

- `site --site-url https://…` nennt die öffentliche Adresse. Die Feeds bekommen damit
  vollständige Links und dauerhafte Kennungen. Die Seiten selbst behalten relative Links
  und lassen sich weiter von der Festplatte öffnen.
- `site --plausible https://…/js/….js` bindet Plausible in jede Seite ein (nur mit
  `https://`). Ohne die Option bleibt die Seite frei von Skripten; lokale Bauten und die
  Vorschau zählen nicht. Die Fußzeile sagt, was gilt. Die Feeds enthalten nie ein Skript.
  Die Adresse des Skripts steht im Workflow, nicht im Code.

## Gestaltung

Entwurf vom 13.11.2026 in Claude Design: <https://claude.ai/artifact/7vnxersetXqxviX1vi1pQa>
(privat).

- **Farben:** kühler heller Grund, kieferngrüne Tinte, ein einziger Akzent: Textmarker-Gelb
  für das, was aufsteigt. Dunkles Schema nach Systemeinstellung.
- **Schrift:** Atkinson Hyperlegible Next (34 KB, im Theme).
- **Favicon:** ein geschliffener Stein in Kieferngrün mit gelber Fläche.
- **Aufbau:** eine Spalte ohne Karten. Große Rangziffer links, Verlaufskurve rechts, auf
  dem Telefon untereinander.
- **Begründung:** ein aufklappbares `<details>`-Element statt eines Tooltips, das mit
  Tastatur und auf dem Telefon schlecht erreichbar war.
- **Nachschliff** gegen die Prüfliste „unslop“ (<https://github.com/heydamir/unslop>):
  sehr fett (800) nur Tagestitel und Rangziffer, Abstände auf einem 4-Pixel-Raster,
  Rundungen ab 4 Pixel.
- **Barrierefreiheit:** Kontrast mindestens 6,5:1 in beiden Schemata, Sprunglink zum
  Inhalt, sichtbarer Fokus, Bedienelemente mindestens 44 Pixel hoch, Plus und Minus als
  Zeichen, `aria-current` für die aktuelle Seite, Liste als Liste, Kurve mit Beschriftung,
  Rücksicht auf weniger Bewegung, Kontrastmodus und Druck. Nicht geprüft mit echtem
  Screenreader.

## Vorschau (`serve`)

```
github-anti-ai serve [--data-dir data] [--output output] [--port 8000]
```

Baut die Seite, liefert sie auf `127.0.0.1` aus und baut neu, sobald sich eine Ausgabe
oder das Theme ändert (zweimal pro Sekunde geprüft). Der Browser lädt von selbst nach:
Der Server fügt beim Ausliefern ein kleines Skript ein, die Dateien in `output/` bleiben
ohne. Scheitert ein Bau, zeigt die Vorschau weiter die letzte funktionierende Seite.

## Betrieb auf GitHub

| Workflow | Wann | Was |
|---|---|---|
| `daily.yml` | täglich 02:43 UTC, oder von Hand | GitHub- und HN-Ausgabe erzeugen, montags die Foren-Ausgabe, und alles gemeinsam ins Repo schreiben |
| `site.yml` | nach jedem nicht abgebrochenen täglichen Lauf, bei Änderungen an Theme oder Ausgaben, oder von Hand | Seite bauen und auf GitHub Pages veröffentlichen |
| `tests.yml` | bei jedem Push und Pull Request | die Tests und der Stil (ruff, Version fest im Workflow) |

### Der tägliche Lauf

Ein Job erzeugt nacheinander alle drei Ausgaben. **Scheitert ein Schritt, laufen die
folgenden trotzdem** (`if: !cancelled()`); was fertig wurde, kommt ins Repo und auf die
Seite. Der Lauf endet dann rot, damit der Fehler auffällt.

1. **Tag festlegen** (UTC), bevor gesammelt wird.
2. **Momentaufnahmen der letzten Tage** aus dem Cache von GitHub Actions holen. Fehlt er,
   holt der Lauf alles neu (etwa 40 Minuten).
3. **Sammeln**, bei Fehlern ein zweiter Versuch. Danach wandern die Momentaufnahmen in den
   Cache, auch nach einem Fehlschlag.
4. **Copilot-CLI installieren.** Scheitert das, fehlt nur das Gegenlesen.
5. **GitHub-Ausgabe** mit `publish --review --allow-incomplete`, außer es gibt sie schon.
   Der Schritt bekommt den eingebauten Token des Laufs, weil die Copilot-CLI keine
   klassischen Tokens annimmt.
6. **HN- und Foren-Ausgabe** (`collect-hn`, `collect-forums`). Die Foren-Ausgabe gehört
   zum Montag; an den übrigen Tagen gibt es sie schon, oder der Lauf holt sie nach.
7. **Ins Repo schreiben** (`data/editions/`, `data/history/`, `data/hn-editions/`,
   `data/forums-editions/`) in einem Commit von `github-actions[bot]`.
8. **„Website“ startet** danach von selbst (`workflow_run`), auch nach einem teilweise
   gescheiterten Lauf. Nur dieser eine Workflow veröffentlicht.

### Einmalig einrichten

- **Secret `COLLECT_TOKEN`:** klassischer Personal Access Token ohne Scopes. Der
  eingebaute Token erlaubt nur 1000 Anfragen pro Stunde, ein erster Lauf braucht rund 3000.
- **Copilot:** Der Workflow hat die Berechtigung `copilot-requests: write` und rechnet
  über den eingebauten Token auf das Copilot-Abo des Repo-Besitzers ab. Fiele das aus,
  wäre der Ausweg ein Fine-grained Token mit „Copilot Requests“ als
  `COPILOT_GITHUB_TOKEN`.
- **Pages:** unter *Settings → Pages* als Quelle „GitHub Actions“.

### Bekannte Grenzen

- GitHub löscht Caches nach 7 Tagen ohne Benutzung und hält höchstens 10 GB je Repo.
- Geplante Läufe starten bei hoher Last verspätet, am 14. und 15.11.2026 um rund sieben
  Stunden. Deshalb seit dem 17.11.2026 um 02:43 statt 05:17 UTC.
- `astral-sh/setup-uv` ist auf eine genaue Version festgelegt und muss von Hand angehoben
  werden.

## Offen

- Die Feeds sind in keinem Feed-Leser ausprobiert.
