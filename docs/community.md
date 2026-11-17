# Community-Listen (Bounded Context „Community Trending“)

Neben der GitHub-Liste gibt es eigene Listen für trendende Open-Source-Projekte auf
Hacker News und Lobsters. Die Punkte der Plattform bestimmen die Rangfolge. Die Projekte
gelangen nicht in die GitHub-Bewertung, und umgekehrt.

Beide Plattformen folgen denselben Regeln. Sie unterscheiden sich nur in ihrer `Platform`
(Kürzel, Name, Adresse der Diskussion) und in ihrer Story-Quelle. Ein und derselbe Use
Case (`CollectCommunityEdition`), Kurator (`CommunityCurator`) und Resolver
(`ProjectResolver`) dienen beiden.

Projekte können auf GitHub, GitLab oder einer öffentlichen Gitea-/Forgejo-Instanz liegen.

## Ablauf

```
CollectCommunityEdition(platform).run()
  1. Gibt es die Ausgabe von heute schon?   → ja: nichts holen, sie zurückgeben
  2. Storys finden                          StorySource.discover
  3. Je Story das Projekt auflösen          ProjectResolver.resolve
                                            (Ausfall einer Story: auslassen, protokollieren)
  4. Ausgaben der Sperrfrist laden          eigene Ausgaben der letzten 30 Tage
  5. Auswählen                              CommunityCurator.curate
  6. Speichern                              CommunityEditionStore.save
```

Gegengelesen wird hier nicht.

## Storys

| Plattform | Quelle | Was |
|---|---|---|
| HN | Algolia-API, `/search_by_date` | alle Storys der letzten 48 Stunden mit mindestens 50 Punkten (`HN_STORY_WINDOW`, `HN_MIN_STORY_POINTS`) |
| Lobsters | `/hottest.json`, `/page/2.json`, `/t/show.json` | die ersten zwei Seiten „hottest“ und die Storys mit dem Tag `show` der letzten 7 Tage (`LOBSTERS_HOTTEST_PAGES`, `LOBSTERS_SHOW_WINDOW`) |

- Nur Storys mit Link zählen (keine Ask-HN-Beiträge).
- Steht eine Story auf mehreren Lobsters-Seiten, zählt sie einmal. `newest` bleibt
  draußen, dort ist noch nichts bewertet.
- Das Fenster ist länger als ein Tag, damit keine Story zwischen zwei Läufe fällt. Dass
  sie dann an zwei Tagen gefunden wird, fängt die Sperre ab. Die Schwelle von 50 Punkten
  entspricht der Mindestzahl neuer Sterne der GitHub-Liste.
- Lobsters bietet keine Suche nach Datum, deshalb dort mehr Seiten statt eines Zeitfensters.

## Vom Link zum Repo (`ProjectResolver`)

1. **Die Story verlinkt ein Repo:** Es gehört zur Story (`linked_directly`). Links auf
   Unterseiten (`…/tree/main`, `…/-/blob/…`, `…/src/…`) gelten als Link auf das Repo.
2. **Die Story verlinkt eine Website:** Der Resolver liest die Seite und sammelt die Links,
   die nach Quellcode aussehen (`rel="code-repository"`, oder „source“, „repository“,
   „github“, „gitlab“, „codeberg“, „gitea“, „forgejo“ in Linktext oder Host). Davon zählt
   nur ein Repo mit **Bezug zur Story** (siehe unten). Gewinnt das Repo mit den meisten
   gemeinsamen Wörtern, bei Gleichstand das erste auf der Seite. Links ohne Bezug fragt
   der Resolver gar nicht erst an.

### Bezug zur Story (`shared_words`)

Blogs verlinken oft ihr Theme, den Arbeitgeber oder den Code der Website. Am 13.11.2026
waren deshalb drei von sieben Lobsters-Einträgen falsch, etwa ein Blog-Theme unter einem
Artikel über ein Rechenzentrum.

- **Wörter des Repos:** Besitzer und Name, zerlegt an allem, was kein Buchstabe und keine
  Ziffer ist, dazu beide ohne Trennzeichen. `rust-lang/rust` ergibt `rust`, `lang`,
  `rustlang`.
- **Wörter der Story:** Titel, Hostname und Pfad der Website, genauso zerlegt.
- **Bezug:** mindestens ein gemeinsames Wort. Nicht mit zählen Wörter unter 3 Zeichen,
  reine Zahlen und allgemeine Wörter wie `blog`, `www`, `com`, `github` (`GENERIC_WORDS`).
  Der vollständige Repo-Name zählt ab 2 Zeichen („Adapting CPython for yk“ findet
  `ykjit/yk`).
- **Websites als Repo** (`….github.io`, `….gitlab.io`, `….codeberg.page`) zählen nie.
- Lieber ein Projekt zu wenig als eines, das nicht zur Story gehört.

### Forges

| Forge | Fakten | README |
|---|---|---|
| GitHub | `api.github.com/repos/{owner}/{name}` mit dem Token | `/readme` (roh, jeder Dateiname); 404 heißt: keines |
| GitLab | `/api/v4/projects/{pfad}` und `/languages` (häufigste Sprache) | `readme_url` mit `/-/raw/`; ohne `readme_url`: keines |
| Gitea/Forgejo | `/api/v1/repos/{owner}/{name}` | `/raw/README.md`; 404 heißt: unbekannt, es kann anders heißen |

- **Forge oder nicht:** Für einen unbekannten Host fragt der Resolver auf Verdacht die
  GitLab- und die Gitea-API. Antwortet der Host mit einem Fehler oder gar nicht, ist er
  keine Forge, und die Seite wird wie jede Website gelesen. Nur bei GitHub, gitlab.com und
  codeberg.org (`KNOWN_FORGE_HOSTS`) bedeuten 403, 429 und 5xx einen Ausfall.
- **README:** Text (gelesen), `""` (sicher keines: das Projekt fällt wie bei GitHub
  heraus) oder `None` (unbekannt: es bleibt, AI- und Sprachregel haben dann nur Name,
  Beschreibung und Topics). Gespeichert wird das README nie.
- **Sicherheit:** Nur `http` und `https` auf Standard-Ports, nie `localhost`, `.local`
  oder Adressen, die zu privaten Netzen auflösen. Weiterleitungen folgt der Resolver
  selbst, höchstens drei, und prüft jedes Ziel. Seiten über 1 MB werden nicht gelesen.

### Lizenz

Ein Projekt gilt als Open Source (`is_open_source_license`), wenn seine Lizenz auf der
Freigabeliste steht (`OPEN_SOURCE_LICENSES`) oder es eine Lizenzdatei hat, die die Forge
nicht erkennt (`NOASSERTION`, bei GitLab `other`), etwa zwei Lizenzdateien für MIT und
Apache. Ohne Lizenzdatei oder mit einer Lizenz außerhalb der Liste (`BUSL-1.1`) bleibt es
draußen. Die Seite zeigt `NOASSERTION` nicht als Lizenznamen.

## Auswahlregeln (`CommunityCurator`)

Wie bei GitHub zwei Sektionen: Hauptliste und AI-Sektion.

1. **Nur Open Source mit Code**, ohne Forks und archivierte Repos, und ohne die
   Text-Ausschlüsse der GitHub-Liste (`ExclusionPolicy.check_text`: Sammlungen, Köder,
   kein README, fremde Sprache, Kryptowährungen). Die Schwelle für neue Sterne entfällt,
   an ihre Stelle treten die Punkte der Plattform.
2. **Sperre:** wie bei GitHub 30 Tage, abgeleitet aus den eigenen Ausgaben der Plattform.
   HN und Lobsters sperren sich nicht gegenseitig und nicht gegen die GitHub-Liste.
3. **Ein Repo nur einmal:** Verlinken mehrere Storys dasselbe Repo, zählt die mit dem
   besseren Rang. Gleich sind Adressen, die sich nur in Groß- und Kleinschreibung und
   einem Schrägstrich am Ende unterscheiden (`repository_key`).
4. **AI-Thema:** dieselbe Regel wie bei GitHub (`AiFocusClassifier.classify_text`), aus
   Name, Beschreibung, Topics und README.
5. **Rangfolge:** Punkte der Plattform, dann Kommentare, dann die neuere Story.
6. **Vielfalt:** wie bei GitHub höchstens 4 je Sprache und 2 je Besitzer. Besitzer ist der
   erste Teil des Pfads zusammen mit der Forge: `github.com/alice` und
   `codeberg.org/alice` sind zwei (`owner_key`).
7. Schluss nach 20 je Sektion, nie aufgefüllt.

`CommunityEdition` prüft beim Erzeugen selbst, dass jede Sektion höchstens 20 Projekte
hat, die Vielfaltsregel einhält und kein Repo doppelt vorkommt, auch nicht über beide
Sektionen. Das gilt auch beim Laden aus dem Archiv.

**Bewusst nicht übernommen:** die Abwertung für AI-Mithilfe (bräuchte Commits von allen
Forges) und die Vorlieben des Inhabers (noch nicht entschieden).

### „Warum Platz …?“

Der Kurator gibt jedem gewählten Projekt seine Begründung mit (`reasons`):

- **Fundstelle:** „Die Story verlinkt das Repo direkt.“ oder „Gefunden über einen Link
  auf blog.rust-lang.org. Repo und Story teilen „lang“, „rust“, „rustlang“.“
- **Lizenz:** nur bei einer Lizenzdatei, die die Forge nicht erkennt.
- **AI-Begriffe:** die Signale des `AiFocusClassifier`, auch in der Hauptliste.

Die Seite zeigt sie aufklappbar, daneben die Punkte der Plattform.

## Speicherformat

`data/hn-editions/JJJJ-MM-TT.json` und `data/lobsters-editions/JJJJ-MM-TT.json`,
versioniert, unveränderlich.

```json
{
  "format_version": 1,
  "day": "2026-11-17",
  "projects": [
    {
      "story": {"id": "50519744", "title": "Jiff 1.0: A datetime library for Rust",
                "url": "https://burntsushi.net/jiff/", "points": 369, "comments": 81,
                "created_at": "2026-11-16T16:53:39+00:00"},
      "repository_url": "https://github.com/BurntSushi/jiff",
      "project_url": "https://burntsushi.net/jiff/",
      "description": "A datetime library for Rust …",
      "language": "Rust",
      "license_id": "Unlicense",
      "is_fork": false, "is_archived": false, "has_code": true,
      "topics": ["datetime", "rust"],
      "linked_directly": false,
      "reasons": ["Gefunden über einen Link auf burntsushi.net. Repo und Story teilen „burntsushi“, „jiff“."]
    }
  ],
  "ai_projects": []
}
```

- **Einziger Unterschied der Plattformen:** HN nennt die Punkte `points` und speichert
  keine `discussion_url` (sie folgt aus der ID). Lobsters nennt sie `score` und speichert
  `discussion_url`. Im Code heißen beide `Story.points`.
- Ausgaben von vor dem 13.11.2026 haben weder `ai_projects` noch `topics`, `reasons` und
  `linked_directly`. Sie werden mit leerer AI-Sektion und ohne Begründung gelesen.

## Ports

```python
class StorySource(Protocol):
    def discover(self, now: datetime, limit: int | None = None) -> list[Story]: ...

class ProjectResolver(Protocol):
    def resolve(self, story: Story) -> CommunityProject | None: ...

class CommunityEditionStore(Protocol):   # je Plattform einer
    def save(self, edition: CommunityEdition) -> None: ...   # AlreadyPublished
    def load(self, day: date) -> CommunityEdition | None: ...
    def since(self, day: date) -> list[CommunityEdition]: ...
```

## Kommandozeile

```
github-anti-ai collect-hn [--limit N] [--data-dir data]
github-anti-ai collect-lobsters [--limit N] [--data-dir data]
```

Beide brauchen den GitHub-Token für die GitHub-API.

## Zurückgestellt

Reddit, wegen OAuth-, Lösch- und Aufbewahrungsregeln.
