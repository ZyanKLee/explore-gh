# Community-Listen (Bounded Context „Community Trending“)

Neben der GitHub-Liste gibt es eigene Listen für trendende Open-Source-Projekte: täglich
auf Hacker News und wöchentlich in den Foren (Lobsters, Lemmy, Mastodon, siehe
„Wochenliste Foren“). Die Punkte der Plattform bestimmen die Rangfolge. Die Projekte
gelangen nicht in die GitHub-Bewertung, und umgekehrt.

Alle Listen folgen denselben Regeln. Sie unterscheiden sich in ihrer `Platform` (Kürzel,
Name, Adresse der Diskussion, täglich oder wöchentlich) und in ihrer Story-Quelle. Ein und
derselbe Use Case (`CollectCommunityEdition`), Kurator (`CommunityCurator`) und Resolver
(`ProjectResolver`) dienen allen. Bis zum 17.11.2026 gab es eine tägliche Lobsters-Liste;
ihre Ausgaben bleiben im Archiv unter `/lobsters/archiv/`.

Projekte können auf GitHub, GitLab oder einer öffentlichen Gitea-/Forgejo-Instanz liegen.

## Ablauf

```
CollectCommunityEdition(platform).run()
  1. Gibt es die Ausgabe von heute schon?   → ja: nichts holen, sie zurückgeben
                                            (wöchentlich: die Ausgabe vom Montag)
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
| Foren | Lobsters, Lemmy, Mastodon | siehe „Wochenliste Foren“ |

- Bei HN zählen nur Storys mit Link (keine Ask-HN-Beiträge).
- Das Fenster ist länger als ein Tag, damit keine Story zwischen zwei Läufe fällt. Dass
  sie dann an zwei Tagen gefunden wird, fängt die Sperre ab. Die Schwelle von 50 Punkten
  entspricht der Mindestzahl neuer Sterne der GitHub-Liste.

## Vom Link zum Repo (`ProjectResolver`)

Der Resolver prüft in dieser Reihenfolge; das Erste, was ein Repo ergibt, gilt.

1. **Die Story verlinkt ein Repo:** Es gehört zur Story (`linked_directly`). Links auf
   Unterseiten (`…/tree/main`, `…/-/blob/…`, `…/src/…`) gelten als Link auf das Repo.
2. **Die Story verlinkt eine Website:** Der Resolver liest die Seite und sammelt die Links,
   die nach Quellcode aussehen (`rel="code-repository"`, oder „source“, „repository“,
   „github“, „gitlab“, „codeberg“, „gitea“, „forgejo“ in Linktext oder Host). Davon zählt
   nur ein Repo mit **Bezug zur Story** (siehe unten). Gewinnt das Repo mit den meisten
   gemeinsamen Wörtern, bei Gleichstand das erste auf der Seite. Links ohne Bezug fragt
   der Resolver gar nicht erst an.
3. **Der Text des ersten Beitrags verlinkt ein Repo** (nur Foren, `Story.links`): wie bei
   einer Website, mit Bezug zur Story (`found_in_post`). Verfolgt werden nur Links zu
   Hosts, die nach einer Forge aussehen (`github.com`, `gitlab.com`, `codeberg.org` oder
   „git“, „forge“, „codeberg“ im Host, `FORGE_HOST_WORDS`). Unterseiten wie
   `…/tool/releases` zählen als Link auf das Repo.

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
5. **Rangfolge:** Punkte der Plattform (in den Foren ihr Vielfaches der Schwelle), dann
   Kommentare, dann die neuere Story.
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

- **Fundstelle:** „Die Story verlinkt das Repo direkt.“, „Gefunden über einen Link
  auf blog.rust-lang.org. Repo und Story teilen „lang“, „rust“, „rustlang“.“ oder
  „Gefunden im ersten Beitrag. …“
- **Punkte und Herkunft** (nur Foren): „34 Punkte auf Lobsters, das 3,4-Fache der
  Schwelle von 10.“, dazu „Auch auf Lemmy c/rust, 22 Punkte.“
- **Lizenz:** nur bei einer Lizenzdatei, die die Forge nicht erkennt.
- **AI-Begriffe:** die Signale des `AiFocusClassifier`, auch in der Hauptliste.

Die Seite zeigt sie aufklappbar, daneben die Punkte der Plattform.

## Speicherformat

`data/hn-editions/JJJJ-MM-TT.json`, `data/forums-editions/JJJJ-MM-TT.json` (Tag ist der
Montag der Woche) und das Archiv `data/lobsters-editions/JJJJ-MM-TT.json`, versioniert,
unveränderlich.

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

- **Unterschiede der Plattformen:** HN nennt die Punkte `points` und speichert keine
  `discussion_url` (sie folgt aus der ID). Lobsters nennt sie `score` und speichert
  `discussion_url`. Die Foren nennen sie `points`, speichern `discussion_url` und je Story
  die Herkunft: `"origin": {"name": "Lemmy c/rust", "reference_points": 15,
  "min_points": 15, "points_label": "Punkte"}`, dazu `"found_in_post": true`, wenn das
  Repo im Text des ersten Beitrags stand. Im Code heißen alle Punkte `Story.points`.
- **Weitere Storys** (`other_stories`): andere Storys, die dasselbe Repo verlinken, im
  selben Format wie `story`. Fehlt, wenn es keine gibt. Ausgaben von vor dem 23.11.2026
  nennen sie nur in der Begründung, ohne Link.
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
explore-gh collect-hn [--limit N] [--data-dir data]
explore-gh collect-forums [--limit N] [--data-dir data]
```

Beide brauchen den GitHub-Token für die GitHub-API. `collect-forums` läuft täglich mit und
tut nur etwas, wenn die Ausgabe vom Montag noch fehlt.

## Wochenliste „Foren“

Seit 18.11.2026, erste Ausgabe am Montag, 23.11.2026.

### Warum

Lobsters lieferte zu wenig für eine tägliche Liste: 10 Projekte in der ersten Ausgabe,
danach 1, 2, 5 und 1 (14. bis 17.11.2026). Andere kleine Plattformen sind allein ebenso
dünn. Deshalb fasst eine **gemeinsame Liste** mehrere Plattformen zusammen und erscheint
**wöchentlich**. Die HN-Liste bleibt, wie sie ist: Sie trägt sich allein.

### Herkunft der Storys (`adapters/forum_sources.py`)

| Herkunft | Schnittstelle | Schwelle |
|---|---|---|
| **Lobsters** | `/newest/page/N.json`, bis die Storys älter als 8 Tage sind, höchstens 12 Seiten, 3 Sekunden Pause je Seite | 10 Punkte |
| **Lemmy**, über programming.dev (`LEMMY_COMMUNITIES`): `programming`, `rust`, `devops`, `opensource@lemmy.ml`, `linux@lemmy.ml`, `selfhosted@lemmy.world` | `/api/v3/post/list?community_name=…&sort=New`, Seite für Seite bis älter als 8 Tage | 15 Punkte |
| **Mastodon**, über fosstodon.org (`MASTODON_TAGS`): `#opensource`, `#foss`, `#rust`, `#linux` | `/api/v1/timelines/tag/{tag}`, mit `max_id` zurück bis älter als 8 Tage | **testweise keine**, Bezugsgröße 5 Reaktionen |

- **Lobsters** fragt „newest“ statt „hottest“: Die Liste erscheint einmal die Woche und
  sieht so jede Story der Woche mit ihrer heutigen Punktzahl. Nach schnellen Anfragen
  antwortet Lobsters mit 429, deshalb die Pause (`LOBSTERS_PAUSE_SECONDS`).
- **Lemmy** sieht über programming.dev auch Communities anderer Instanzen. Beiträge aus
  PieFed und Mbin kommen über die Föderation mit. Entfernte und gelöschte Beiträge
  bleiben draußen.
- **Mastodon:** Punkte sind Favoriten plus Boosts, Kommentare die Antworten. Ein Toot
  unter mehreren Tags zählt einmal. Mastodon hat testweise keine Schwelle, weil die Funde
  fast keine Reaktionen haben. Für die Rangfolge gelten 5 Reaktionen als Bezugsgröße
  (`MASTODON_REFERENCE_POINTS`), ein Toot ohne Reaktion steht also hinten.
- **Bündel** (`ForumStories`): nur Storys, die 1 bis 8 Tage alt sind
  (`FORUMS_MIN_STORY_AGE`, `FORUMS_MAX_STORY_AGE`), jede Diskussion einmal. Fällt eine
  Quelle aus, gelten die anderen, das Protokoll nennt den Ausfall. Fallen alle aus, fällt
  die Ausgabe aus und der Dienstag holt sie nach.

**Gemessen am 18.11.2026**, Storys der letzten 8 Tage: Lobsters 157 (8 verlinken ein Repo
direkt, 147 eine Website), Lemmy 100 (8 direkt, 7 mit Repo im Text, 74 Website),
Mastodon 441 Toots mit Links (55 mit einem Repo im Text, das zur Story passt). Die
Schwellen sind Startwerte; die Zahlen der ersten Wochen kommen hierher.

**Geprüft und verworfen:** Reddit (neue Anwendungen brauchen seit November 2025 eine
Genehmigung, die Abfrage ohne Anmeldung antwortet mit 403), Mastodon-Trends (nur
Nachrichtenseiten), Echo JS (nur JavaScript, 1 bis 2 Stimmen), gitlab.com (keine
Plattform mit Beiträgen; ohne Anmeldung keine Suche nach neuen Projekten mit Sternen),
Tildes (keine Schnittstelle).

**Noch nicht geprüft:** Bluesky (Suche nach verlinkter Domain, nach Likes sortiert, braucht
ein Konto mit App-Passwort), Discourse-Foren von Sprach-Communities mit Kategorien wie
„Showcase“ oder „Announcements“.

### Nur der erste Beitrag

Gesammelt werden nur Projekte, die der **erste Beitrag** nennt. Antworten und Kommentare
zählen nie, auch wenn dort Repos verlinkt sind.

| Herkunft | Erster Beitrag |
|---|---|
| Lobsters | Link der Story und Text der Story (`description`) |
| Lemmy | `url` und Text (`body`) des Beitrags |
| Mastodon | Text eines Toots, der keine Antwort (`in_reply_to_id` leer) und kein Boost ist. Als Titel dient der Text ohne Links, gekürzt auf 120 Zeichen. |

- Eine Story ohne Link und ohne Links im Text bleibt draußen.
- Links im Text brauchen einen **Bezug zur Story** (siehe „Vom Link zum Repo“). So fällt
  „gebaut mit `tokio-rs/tokio`“ unter einem Beitrag über ein anderes Projekt heraus.
- **HN** bleibt unverändert: Dort zählt schon immer nur der Link der Story.

### Rangfolge über Plattformen hinweg

Punkte verschiedener Plattformen sind nicht vergleichbar. Jede Herkunft (`Origin`) hat
deshalb ihre eigene Schwelle, und die Rangfolge bestimmt das **Vielfache der Schwelle**
(`Story.relative_points`):

- 34 Punkte auf Lobsters (Schwelle 10) ergeben 3,4.
- 45 Punkte auf Lemmy (Schwelle 15) ergeben 3,0.
- Bei Gleichstand entscheiden die Kommentare, dann die neuere Story.

Storys unter der Schwelle ihrer Herkunft fallen heraus. Die Begründung sagt es in einem
Satz: „34 Punkte auf Lobsters, das 3,4-Fache der Schwelle von 10.“ Bei Mastodon: „0
Reaktionen auf Mastodon #rust, das 0,0-Fache der Bezugsgröße von 5. Testweise ohne
Schwelle.“

**Ein Repo auf mehreren Plattformen** erscheint einmal, die Story mit dem höheren Vielfachen
gewinnt. Die anderen Fundstellen nennt die Begründung („Auch auf Lemmy c/rust, 22
Punkte.“). Es gibt dafür keinen Bonus, damit die Regel einfach bleibt. Der Eintrag
verlinkt jede Diskussion: zuerst die der gewinnenden Story, dann die der übrigen in
ihrer Rangfolge (`other_stories`). Dieselbe Diskussion steht nur einmal da.

### Erscheinen

- **Einmal die Woche.** Die Ausgabe gehört zum Montag (`edition_day`). Der tägliche Lauf
  fragt jeden Tag; gibt es die Ausgabe der Woche schon, tut er nichts.
- **Ausgabe:** `data/forums-editions/JJJJ-MM-TT.json` mit dem Datum des Montags.
- **Sperre:** 30 Tage wie bisher, abgeleitet aus den eigenen Wochenausgaben. Die
  Foren-Liste sperrt sich nicht gegen HN oder GitHub.
- Alle übrigen Auswahlregeln gelten unverändert: Open Source mit Code, Ausschlüsse,
  AI-Sektion, Vielfaltsregel, höchstens 20 je Sektion.
- **Seite:** `/forums/` und `/forums/ai/`, Titel „Trending in den Foren, Woche vom …“. Jeder
  Eintrag nennt seine Herkunft: „34 Punkte auf Lobsters“, „Diskussion auf Lemmy c/rust“.

### Offen

- Mastodon nach vier Wochen (Mitte Dezember 2026) prüfen: aufnehmen mit Schwelle, so
  lassen oder streichen.
- Die Schwellen von Lobsters (10) und Lemmy (15) an den ersten Wochen prüfen.
- Mastodon über fosstodon.org allein oder mehrere Instanzen? Jede Instanz sieht nur, was
  ihre Mitglieder abonniert haben.
