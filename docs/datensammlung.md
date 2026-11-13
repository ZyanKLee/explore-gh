# Datensammlung (Bounded Context „Acquisition“)

## Aufgabe

Die Datensammlung findet einmal täglich Kandidaten, holt zu jedem eine
Momentaufnahme (`Snapshot`) und speichert sie. Sie **bewertet nicht** und **schließt
nichts aus**: Auch Forks, Krypto-Projekte oder chinesische READMEs landen als
Momentaufnahme im Speicher. Ob ein Repo taugt, entscheidet erst `Assessment`.

**Eine Ausnahme spart Anfragen:** Für Repos, die nie gezeigt werden können (Fork,
archiviert, Spiegel oder ohne erkannten Code), holt die Sammlung keinen Sternverlauf.
Sie bekommen trotzdem eine Momentaufnahme, nur mit leerem Verlauf. Die Regel dazu steht
in der Domäne (`Snapshot.can_never_be_shown`). Das spart etwa 11 % der Anfragen.

## Ablauf

```
CollectSnapshots.run()
  1. Kandidaten finden      alle CandidateSources fragen, Ergebnisse zusammenführen
  2. Schon Erledigtes       Repos mit Momentaufnahme von heute überspringen
  3. Einteilen              neu holen / auffrischen / übernehmen
  4. Übernehmen             ohne Anfragen
  5. In Gruppen von 20:     RepoSource.fetch(gruppe, jetzt)
                            SnapshotStore.append(heute, momentaufnahmen)
  6. Die Besten             je Sektion die 60 besten auffrischen
  7. Aufräumen              SnapshotStore.prune(heute − 14 Tage)
  → CollectionReport        gefunden, gesammelt, fehlend, fehlgeschlagen, Fehler,
                            neu geholt, aufgefrischt, übernommen
```

Die Schritte 3, 4 und 6 beschreibt der Abschnitt „Momentaufnahmen weiterverwenden“.

- Kandidaten, die mehrere Quellen liefern, werden nur einmal geholt. `RepoId`
  vergleicht ohne Rücksicht auf Groß- und Kleinschreibung, wie GitHub selbst.
- Fällt eine Kandidatenquelle aus, wird das im Bericht vermerkt und die anderen
  Quellen werden trotzdem verwendet.
- **Gespeichert wird nach jeder Gruppe.** Ein Abbruch verliert höchstens eine Gruppe.
- **Ein erneuter Lauf am selben Tag setzt fort:** Er holt nur, was noch fehlt. Wer den
  Tag neu sammeln will, löscht die Datei des Tages.
- Schlägt eine Gruppe fehl, wird sie übersprungen und im Bericht als fehlgeschlagen
  geführt. Nach 3 fehlgeschlagenen Gruppen in Folge hört der Lauf auf. Das bis dahin
  Gesammelte bleibt erhalten.
- **Fortschritt:** Suche und Sammlung melden jeden Schritt über `logging`. Die
  Kommandozeile zeigt die Meldungen an.
- **Probelauf:** `collect --limit N` begrenzt die Zahl der Kandidaten. Die Quellen
  hören auf zu suchen, sobald genug gefunden sind.

## Kandidatensuche

Erste Quelle: `GitHubSearchCandidates` über die REST Search API.

- Eine Suchanfrage pro Erstellungstag der letzten 30 Tage:
  `created:2026-11-12 stars:>=50 fork:false archived:false`, sortiert nach Sternen,
  je eine Seite à 100 Ergebnisse. Das sind 30 Suchanfragen pro Lauf.
- Die Aufteilung nach Tagen umgeht die Grenze von 1000 Ergebnissen pro Suche.
- Zwischen zwei Suchanfragen liegen 2 Sekunden Pause (Limit: 30 pro Minute).
- `fork:false archived:false` spart nur Aufwand. Der eigentliche Ausschluss passiert
  trotzdem in `Assessment`.

**Diese Quelle allein verfehlt das Ziel.** Sie findet nur neue Repos, die schnell
Sterne sammeln. Das ist das Profil von Hype-Projekten. Von Hand gebaute Projekte sind
oft Monate oder Jahre alt, bevor sie entdeckt werden. Siehe „Geplant: weitere
Kandidatenquellen“.

## Momentaufnahme

`GitHubRepoSource` holt die Fakten mit **einer** GraphQL-Abfrage pro Gruppe von 20
Repos und den Sternverlauf mit einer REST-Anfrage pro Repo.

| Feld | Quelle (GraphQL) | Wofür |
|---|---|---|
| `description`, `homepage`, `topics` | `description`, `homepageUrl`, `repositoryTopics` | AI-Thema, Krypto, Sprache |
| `primary_language` | `primaryLanguage` | Vielfaltsregel |
| `created_at`, `pushed_at` | `createdAt`, `pushedAt` | Bonus für neue Projekte, Aktivität |
| `stars`, `forks`, `open_issues` | `stargazerCount`, `forkCount`, `issues(states: OPEN)` | Aufstieg, Größe |
| `watchers`, `pull_requests`, `recent_issue_authors` | `watchers`, `pullRequests`, Autoren der letzten 100 Issues (verschiedene Personen, ohne Bots) | Gegenprobe zu gekauften Sternen |
| `is_fork`, `is_archived`, `is_mirror`, `is_template` | gleichnamige Felder | Ausschlüsse |
| `license` | `licenseInfo.spdxId` | Signal |
| `root_files` | `object(expression: "HEAD:")` | `CLAUDE.md`, `.cursorrules` …, „kein Code“ |
| `readme` | `object(expression: "HEAD:README.md")` u. a. Varianten, gekürzt auf 20 000 Zeichen | AI-Thema, Krypto, Sprache, „kein Code“ |
| `recent_commits` | Verlauf des Standard-Branches, bis zu 100 Commits der letzten 90 Tage | AI-Mithilfe, Contributors, Kontinuität |
| `star_history` | REST: `GET /repos/{owner}/{repo}/stargazers/history` | Aufstieg, Verlaufskurve auf der Seite, Sterne auf einen Schlag |

Ein `Commit` enthält Zeitpunkt, Autor (GitHub-Login, sonst Git-Name), ob es ein Bot
ist (Name endet auf `[bot]`), die `Co-authored-by`-Einträge und die erste Zeile der
Nachricht.

### Sternverlauf

Seit Juli 2026 gibt GitHub Stargazer-Listen nur noch an Admins und Mitarbeiter eines
Repos heraus. Über GraphQL kommt eine leere Liste zurück, über REST ein 404. Deshalb
fragen wir Stargazer gar nicht mehr ab.

Stattdessen nutzen wir den neuen Endpunkt `GET /repos/{owner}/{repo}/stargazers/history`:

- Er liefert Wochen, die neueste zuerst. `week` ist der Sonntag als Unix-Zeit, `days`
  enthält die neuen Sterne je Tag, beginnend am Sonntag.
- Wir holen 6 Wochen (`per_page=6`) und bilden daraus `StarHistory`: die neuen Sterne
  der letzten 35 Tage, der letzte Eintrag ist heute. Tage ohne Angabe zählen als 0.
- `StarHistory.gained()` ist der Gewinn der letzten 7 Tage einschließlich heute.
  `gained(30)` liefert den Gewinn eines Monats.
- Der Wert ist immer exakt und gilt für Repos jeden Alters. Eine eigene Historie über
  Wochen brauchen wir nicht. Das ursprünglich geplante Aggregate `RepoHistory`
  entfällt.
- GitHub garantiert nicht, dass Wochen- und Tagesgrenzen an UTC ausgerichtet sind.
  Zurzeit sind sie es.

## Ports

```python
class CandidateSource(Protocol):
    name: str
    def discover(self, today: date, limit: int | None = None) -> list[Candidate]: ...

class RepoSource(Protocol):
    def fetch(self, repos: Sequence[RepoId], now: datetime,
              with_star_history: bool = True) -> list[Snapshot]: ...
    # Repos, die es nicht (mehr) gibt, fehlen einfach im Ergebnis.

class SnapshotStore(Protocol):
    def append(self, day: date, snapshots: Sequence[Snapshot]) -> None: ...
    def load(self, day: date) -> list[Snapshot]: ...   # je Repo die jüngste
    def prune(self, before: date) -> None: ...

class Clock(Protocol):
    def now(self) -> datetime: ...   # immer UTC
```

Adapter melden Ausfälle als `SourceUnavailable`.

## Speicherung

- `data/snapshots/YYYY-MM-DD.jsonl.gz`, eine Momentaufnahme pro Zeile
- `data/snapshots/YYYY-MM-DD.status.json`: wie der Lauf des Tages ausging. `publish`
  prüft daran, ob die Sammlung vollständig ist (siehe `ausgabe.md`).
- Aufbewahrung: 14 Tage. Das reicht, um Bewertungsregeln an echten Daten
  auszuprobieren, ohne die APIs erneut abzufragen.
- Arbeitsdaten, **nicht** im Git-Repo. Dauerhaft gespeichert werden nur die Ausgaben
  (`Edition`s).

## Fehler und Rate Limits

Gemeinsam für alle GitHub-Adapter:

- `403`/`429` mit `Retry-After`: so lange warten, dann erneut versuchen.
- `x-ratelimit-remaining: 0`: bis `x-ratelimit-reset` warten.
- `5xx` oder eine abgeschnittene, unlesbare Antwort: mit wachsender Pause erneut
  versuchen, insgesamt höchstens 3 Versuche.
  Danach `SourceUnavailable`.
- GraphQL-Fehler vom Typ `NOT_FOUND` betreffen nur einzelne Repos. Jeder andere
  GraphQL-Fehler führt zu `SourceUnavailable`, auch wenn Daten mitkommen. Sonst würde
  ein verweigerter Zugriff wie ein fehlendes Repo aussehen.
- Warten erfolgt über eine übergebene `sleep`-Funktion, damit Tests nicht warten.

## Zugang zu GitHub

- **Token:** ein *klassischer* personal access token **ohne Scopes**, mit
  Ablaufdatum. Er liest nur öffentliche Daten. Mit ihm ist alles geprüft. Ob auch
  ein fine-grained Token den Sternverlauf lesen darf, ist nicht geprüft.
- **Ablage:** Umgebungsvariable `GITHUB_TOKEN`, sonst eine Zeile `GITHUB_TOKEN=…` in
  `.env` im Projektverzeichnis. `.env` steht in `.gitignore`. Die Variable hat Vorrang.
- **HTTP-Client** (`make_github_client`): setzt `Authorization`, einen eindeutigen
  `User-Agent` (`github-anti-ai`), `Accept` und `X-GitHub-Api-Version`.
- **Anfragebudget:** Der Client zählt die Anfragen eines Laufs. Ab 4000 Anfragen
  verweigert er weitere (`RequestBudgetExceeded`, eine Art `SourceUnavailable`). Das
  ist eine Notbremse für Fehler wie Endlosschleifen.
- Anfragen laufen nacheinander, nie parallel.

## Budget pro Lauf

| Schritt | Anfragen | Dauer |
|---|---|---|
| Suche | 30 | 3 bis 4 Minuten (gemessen: etwa 5 s Antwortzeit plus 2 s Pause) |
| GraphQL | eine je 20 Kandidaten | etwa 6 s je Gruppe (gemessen) |
| Sternverlauf | eine je Kandidat | etwa 0,2 s je Repo (gemessen) |

Gemessen am 12.11.2026: 60 Kandidaten in 35 Sekunden.

**Vollständiger Lauf, Nacht zum 13.11.2026:** 2937 Kandidaten, 2857 Momentaufnahmen,
38 Minuten (Suche 2,5 Minuten, Momentaufnahmen 35 Minuten), rund 3000 Anfragen.
Erlaubt sind 5000 REST-Anfragen pro Stunde. 4 von 147 Gruppen schlugen fehl: einmal
HTTP 502, dreimal „Resource limits for this query exceeded“ (siehe „Offen“).

Der automatische `GITHUB_TOKEN` in GitHub Actions hat nur 1000 Anfragen pro Stunde.
Für den späteren Betrieb dort brauchen wir einen eigenen Token als Secret.

## Konstanten

| Name | Wert | Ort |
|---|---|---|
| `GROWTH_WINDOW_DAYS`, `STAR_HISTORY_DAYS` | 7, 35 | Domäne |
| `COMMIT_LOOKBACK` | 90 Tage | Domäne |
| `README_MAX_CHARS` | 20 000 | Domäne |
| `SNAPSHOT_RETENTION_DAYS` | 14 | Anwendung |
| `FETCH_CHUNK_SIZE`, `MAX_CONSECUTIVE_FAILURES` | 20, 3 | Anwendung |
| Suchfenster, Mindeststerne, Pause | 30 Tage, 50, 2 s | Adapter (Parameter) |

## Momentaufnahmen weiterverwenden

Umgesetzt am 13.11.2026. Die Tests stehen in
`tests/unit/domain/test_snapshot_reuse.py`,
`tests/unit/application/test_collect_reuse.py` und
`tests/integration/test_reuse_adapters.py`.

### Warum

Ohne Weiterverwendung holt jeder Lauf alle Kandidaten vollständig neu. Gemessen in der
Nacht zum 13.11.2026: 2937 Kandidaten, rund 3000 Anfragen, 38 Minuten. Fast alle Anfragen entfallen auf den
Sternverlauf (eine je Repo), die übrigen Fakten kommen gebündelt (eine je 20 Repos).

Die Suche liefert zu jedem Treffer die aktuelle Sternzahl gratis mit. Daraus führen
wir den Sternverlauf selbst fort und brauchen die teure Anfrage nur noch für Repos, die
wir zum ersten Mal sehen.

### Regel

Für jeden Kandidaten von heute sucht der Lauf die jüngste Momentaufnahme der letzten
3 Tage und entscheidet:

| Lage | Was geschieht | Anfragen |
|---|---|---|
| Keine Momentaufnahme in den letzten 3 Tagen | **neu holen:** Fakten und Sternverlauf von GitHub | 1/20 + 1 |
| Fakten jünger als 3 Tage | **übernehmen:** Momentaufnahme gilt weiter, Sternzahl von heute aus der Suche | 0 |
| Fakten 3 Tage alt oder älter | **auffrischen:** Fakten neu von GitHub, Sternverlauf aus eigenen Daten | 1/20 |
| Unter den Besten (siehe unten) | **auffrischen**, auch wenn die Fakten jünger sind | 1/20 |

Sonderfälle:

- **Quelle ohne Sternzahl** (künftig Hacker News, Lobste.rs): Übernehmen geht nicht,
  es wird aufgefrischt.
- **Momentaufnahme ohne Sternverlauf** (das Repo war beim letzten Mal ein Fork oder
  ohne Code): neu holen.
- **Auffrischen schlägt fehl:** Die ältere Momentaufnahme wird übernommen und der
  Fehler im Bericht vermerkt. Das Repo gilt nicht als fehlgeschlagen.

### Eigener Sternverlauf

`StarHistory.continued(days_passed, gained)` schiebt den Verlauf um die vergangenen
Tage weiter und trägt den Gewinn am letzten Tag ein. Der Gewinn ist die Sternzahl von
heute minus die der letzten Momentaufnahme, mindestens 0.

- **Lücken:** Fehlt ein Repo an einem Tag in der Suche, steht für diesen Tag 0 im
  Verlauf und der ganze Gewinn am Tag danach. Die Summe über 7 Tage, auf die es für
  den Aufstieg ankommt, stimmt trotzdem.
- **Verlorene Sterne** zählen als 0, nicht als Abzug.
- Der Verlauf bleibt 35 Tage lang.

### Alter der Fakten

Eine Momentaufnahme bekommt ein zweites Datum:

- `taken_at`: der Tag, zu dem die Momentaufnahme gehört
- `facts_at`: wann die Fakten zuletzt von GitHub kamen. Bei einer frisch geholten
  Momentaufnahme ist das dasselbe.

Dateien aus der Zeit davor haben kein `facts_at`. Beim Lesen gilt dann `taken_at`.

### Verschwundene Repos

Dafür braucht es keine eigene Regel. Kandidat ist nur, was die Quellen heute finden.
Ein gelöschtes, archiviertes oder privat gestelltes Repo taucht in der Suche nicht mehr
auf und bekommt keine Momentaufnahme von heute. `publish` und `explain` lesen nur die
Momentaufnahmen des Tages.

### Die Besten vor der Veröffentlichung auffrischen

Nichts auf der Seite soll älter als ein Tag sein. Nach dem Übernehmen bewertet der Lauf
deshalb alle Momentaufnahmen von heute und frischt je Sektion die 60 nicht
ausgeschlossenen Repos mit der höchsten Punktzahl auf, sofern ihre Fakten nicht von
heute sind.

- **60 je Sektion statt 100 insgesamt:** Sonst könnte die Hauptliste alle Plätze
  belegen und die AI-Sektion ginge leer aus. 60 ist das Dreifache der 20 Plätze und
  lässt Luft für Sperre und Vielfaltsregel. Das sind höchstens 6 Anfragen.
- Die Punktzahl kann sich durch das Auffrischen ändern. Es wird nicht ein zweites Mal
  nachgefasst.
- `CollectSnapshots` bekommt dafür die Bewertungsfunktion (`assess`) als Parameter.
  Ohne sie entfällt der Schritt.

### Ablauf mit Weiterverwendung

```
CollectSnapshots.run()
  1. Kandidaten finden      Quellen liefern Candidate(repo, stars)
  2. Schon Erledigtes       Repos mit Momentaufnahme von heute überspringen
  3. Einteilen              neu holen / auffrischen / übernehmen
  4. Übernehmen             ohne Anfragen, sofort gespeichert
  5. Neu holen              in Gruppen von 20, mit Sternverlauf
  6. Auffrischen            in Gruppen von 20, ohne Sternverlauf
  7. Die Besten             bewerten, je Sektion 60 auffrischen
  8. Aufräumen              SnapshotStore.prune(heute − 14 Tage)
  → CollectionReport        zusätzlich: fetched, refreshed, carried_over
```

Ein erneuter Lauf am selben Tag stellt keine Anfragen mehr, wenn alles da ist.

### Änderungen an Ports und Modell

```python
@dataclass(frozen=True)
class Candidate:
    repo: RepoId
    stars: int | None = None      # None, wenn die Quelle keine Sternzahl kennt

class CandidateSource(Protocol):
    def discover(self, today, limit=None) -> list[Candidate]: ...

class RepoSource(Protocol):
    def fetch(self, repos, now, with_star_history=True) -> list[Snapshot]: ...
```

- `GitHubSearchCandidates` liest `stargazers_count` aus den Suchtreffern.
- `GitHubRepoSource` lässt mit `with_star_history=False` die Anfrage nach dem
  Sternverlauf weg.
- Die Prüfung `checks/request_count.py` zählt weiter die Anfragen eines Laufs ohne
  Vorgeschichte. Ein zweiter Fall für den Folgetag fehlt noch.
- Verschwindet ein Repo zwischen dem Übernehmen und dem Auffrischen der Besten, bleibt
  seine übernommene Momentaufnahme des Tages stehen. Der Speicher kann nichts
  zurücknehmen.

### Gemessene Wirkung

Zweiter Sammeltag, 13.11.2026, mit den Momentaufnahmen des Vortags:

| | Erster Tag | Folgetag |
|---|---|---|
| Kandidaten | 2937 | 2846 |
| Neu geholt | 2857 | 401 |
| Übernommen | – | 2312 |
| Als Beste aufgefrischt | – | 113 |
| Dauer | 38 Minuten | 8 Minuten |

- Von den 8 Minuten entfallen 2,5 auf die Suche, 4,5 auf das Neuholen und 1 auf das
  Auffrischen der Besten.
- **Unter „neu geholt“ sind rund 290 alte Bekannte:** Repos, die nie gezeigt werden
  können (Fork, archiviert, ohne Code), haben keinen Sternverlauf und werden deshalb
  jeden Tag neu geholt. Das kostet nur die gebündelte Abfrage, etwa 15 Anfragen.
  Wirklich neu waren 129 Repos, dazu die 80 am Vortag gescheiterten.
- 160 Repos des Vortags fand die Suche nicht mehr. Sie haben keine Momentaufnahme vom
  13.11.
- Eine Gruppe scheiterte an HTTP 502. Ein zweiter Lauf holte die 20 Repos in knapp 3
  Minuten nach, fast alles davon Suche. Er fragte für nichts anderes an.
- Das Auffrischen nach 3 Tagen ist noch nicht gelaufen, dafür fehlen die Tage.

### Neue Konstanten

| Name | Wert | Ort |
|---|---|---|
| `REFRESH_AFTER_DAYS` | 3 | Anwendung |
| `FRESH_LEADERS_PER_SECTION` | 60 | Anwendung |

## Separate Trendlisten

Hacker News und Lobsters haben getrennte Datenflüsse und speisen keine GitHub-Kandidaten ein:

1. `HackerNewsSearch` holt über die Algolia-API (`/search_by_date`) alle Storys der
  letzten 48 Stunden mit mindestens 50 Punkten (`STORY_WINDOW`, `MIN_STORY_POINTS` in
  `domain/hn.py`).
2. `HnProjectResolver` folgt Links von Projekt-Websites zu öffentlichen
  GitHub-, GitLab- und Gitea-/Forgejo-Repositories. GitHub-Metadaten kommen über die
  GitHub-API, die anderen bekannten Formate über die jeweilige Forge-API.
3. `HnEditionCurator` wählt mit dem gemeinsamen `CommunityCurator` aus (siehe
  „Community-Ausgaben“ in `ausgabe.md`). HN-Punkte bestimmen die Rangfolge; die
  GitHub-Momentum-Regel wird nicht angewendet.
4. `JsonHnEditionStore` schreibt eine unveränderliche Tagesausgabe nach
  `data/hn-editions/`. Pelican liest sie getrennt von `data/editions/`.

Lobsters folgt demselben Projekt- und OSS-Modell, aber mit einer eigenen Story-Quelle
und Rangfolge:

1. `LobstersSearch` liest die ersten zwei Seiten von „hottest“ (`/hottest.json`,
  `/page/2.json`) und die Storys mit dem Tag `show` aus den letzten 7 Tagen
  (`/t/show.json`). Steht eine Story auf mehreren Seiten, zählt sie einmal.
  `newest` bleibt draußen, weil dort noch nichts bewertet ist (`HOTTEST_PAGES`,
  `SHOW_WINDOW` in `domain/lobsters.py`).
2. `LobstersProjectResolver` erhält Lobsters-Story und Diskussionslink, während der
  gemeinsame Resolver Projektseiten und Forge-APIs prüft.
3. `LobstersEditionCurator` sortiert nach Lobsters-Score und nutzt denselben
  `CommunityCurator` wie die HN-Ausgabe.
4. `JsonLobstersEditionStore` schreibt getrennt nach `data/lobsters-editions/`.

### Zeitraum der Suchen

Gemessen am 13.11.2026 gegen 15 Uhr:

| Quelle | Storys | Alter |
|---|---|---|
| HN-Startseite (bis dahin genutzt) | 30, ab 3 Punkten | 1 bis 40 Stunden |
| HN, 48 Stunden ab 50 Punkten | 107, davon 7 Show HN und 12 direkt auf einer Forge | bis 48 Stunden |
| Lobsters `hottest` (bis dahin genutzt) | 25 | 2 bis 40 Stunden |
| Lobsters `hottest` Seite 2 | 25 | 4 bis 69 Stunden |
| Lobsters `show` | 25, davon 11 direkt auf einer Forge | 15 bis 87 Tage |

Die Startseite zeigte nur, was um 06:37 UTC gerade oben stand. Storys, die tagsüber
oben standen und vor dem Lauf herausgefallen waren, fehlten, ganz neue mit 3 Punkten
waren dabei. Die Schwelle von 50 Punkten entspricht den 50 neuen Sternen der
GitHub-Liste. Das Fenster ist länger als ein Tag, damit keine Story zwischen zwei Läufe
fällt. Dass sie dann an zwei Tagen gefunden wird, fängt die Sperre ab (siehe
„Community-Ausgaben“ in `ausgabe.md`). Lobsters bietet keine Suche nach Datum, deshalb
dort mehr Seiten statt eines Zeitfensters.

### Bezug zur Story (`relates_to_story`)

Verlinkt eine Story direkt ein Repo, gehört dieses Repo zur Story. Verlinkt sie eine
Website, sucht der Resolver dort Links zu Repos. Blogs verlinken aber oft auch ihr
Theme, den Arbeitgeber des Autors oder den Code der Website. Am 13.11.2026 waren
deshalb drei von sieben Lobsters-Einträgen falsch, etwa `bitbrain/jekyll-dash`
(Blog-Theme) unter einem Artikel über ein Rechenzentrum.

Ein auf einer Website gefundenes Repo zählt deshalb nur, wenn es einen Bezug zur Story
hat (`shared_words` in `domain/community.py`).

- **Wörter des Repos:** Besitzer (erster Teil des Pfads) und Name (letzter Teil),
  zerlegt an allem, was kein Buchstabe und keine Ziffer ist, dazu Besitzer und Name
  ohne Trennzeichen. `rust-lang/rust` ergibt `rust`, `lang`, `rustlang`.
- **Wörter der Story:** der Titel, der Hostname und der Pfad der Website, genauso
  zerlegt. `blog.rust-lang.org` ergibt `blog`, `rust`, `lang`, `rustlang`, `org`. Der
  Pfad findet Projekte, die nur in der Adresse stehen, etwa
  `moddb.com/mods/openq4/…` für `themuffinator/openQ4`.
- **Bezug:** mindestens ein gemeinsames Wort. Nicht mit zählen Wörter unter 3 Zeichen,
  reine Zahlen und allgemeine Wörter wie `blog`, `www`, `com`, `org`, `github`
  (`GENERIC_WORDS`). Der vollständige Repo-Name zählt ab 2 Zeichen: „Adapting CPython
  for yk“ findet `ykjit/yk`, ein Teil wie `yk` in `yk-tools` zählt dagegen nicht.
- **Websites als Repo:** Repos mit dem Namen `….github.io`, `….gitlab.io` oder
  `….codeberg.page` enthalten den Code einer Website. Auf einer Website gefunden
  zählen sie nie.

**Welches Repo gewinnt:** Der Resolver betrachtet alle Repo-Links der Seite mit Bezug
und nimmt das Repo mit den meisten gemeinsamen Wörtern, bei Gleichstand das erste auf
der Seite. Unter „Announcing the GraphQL over HTTP specification“ gewinnt so
`graphql/graphql-over-http` (`graphql`, `over`, `http`) gegen `graphql/graphql-spec`
(`graphql`, `spec`). Links ohne Bezug fragt er gar nicht erst bei der Forge an. Links
auf Unterseiten eines Repos (`…/tree/main`, `…/-/blob/…`, `…/src/…`) gelten als Link
auf das Repo, so dass jedes Repo nur einmal angefragt wird.

Am 13.11.2026 entfernt die Regel `bitbrain/jekyll-dash`, `oxidecomputer/omicron` und
`graphql/graphql.github.io`. Sie kostet auch einen richtigen Fund:
`raphlinus/vic-2350` unter „JIT bitmap text rendering for microcontrollers“ auf
`linebender.org`. Lieber ein Projekt zu wenig als eines, das nicht zur Story gehört.

### Topics und README

Für die AI-Sektion holt der Resolver die Topics aus der Repo-Abfrage und für das
gewählte Repo das README, ein Repo pro Story also eine Anfrage mehr:

- GitHub: `/repos/{owner}/{name}/readme` (roh)
- GitLab: `readme_url` aus der Projektabfrage, `/-/blob/` durch `/-/raw/` ersetzt
- Gitea/Forgejo: `/api/v1/repos/{owner}/{name}/raw/README.md`

Das README hat drei Zustände:

- **Text:** gelesen.
- **Leer (`""`):** Das Repo hat sicher keines. GitHub und GitLab sagen das verlässlich
  (404 bzw. kein `readme_url`). Das Projekt fällt dann wie bei GitHub heraus („Kein
  README“).
- **Unbekannt (`None`):** Die Abfrage ist fehlgeschlagen, oder Gitea kennt kein
  `README.md` (das README kann anders heißen). Das Projekt bleibt, AI-Regel und
  Sprachregel haben dann nur Name, Beschreibung und Topics.

### Forge oder nicht

Für einen Link auf einen unbekannten Host fragt der Resolver auf Verdacht die APIs von
GitLab (`/api/v4/projects/…`) und Gitea/Forgejo (`/api/v1/repos/…`) ab. Antwortet ein
solcher Host mit einem Fehler oder gar nicht, ist er keine Forge, und der Resolver liest
die Seite wie jede andere Website. Nur bei GitHub, gitlab.com und codeberg.org
(`KNOWN_FORGE_HOSTS`) bedeuten 403, 429 und 5xx einen Ausfall (`SourceUnavailable`).
Vorher hat ein 403 von einer Nachrichtenseite die ganze Story verworfen.

### Lizenz

Ein Projekt gilt als Open Source (`is_open_source_license`), wenn

- seine Lizenz auf der Freigabeliste steht (`OPEN_SOURCE_LICENSES`), oder
- es eine Lizenzdatei hat, die die Forge nicht erkennt (`NOASSERTION`). GitHub meldet
  das zum Beispiel bei zwei Lizenzdateien für MIT und Apache oder bei abgewandelten
  Lizenztexten. GitLab meldet `other`, der Resolver übersetzt das in `NOASSERTION`.

Ohne Lizenzdatei oder mit einer Lizenz außerhalb der Liste (etwa `BUSL-1.1`) bleibt ein
Projekt draußen. Seit dem 13.11.2026 so entschieden: Vorher fielen echte Projekte wie
`ykjit/yk` und `ice-wm/icewm` heraus. Die Seite zeigt `NOASSERTION` nicht als
Lizenznamen, genau wie bei den GitHub-Listen.

Der Resolver kennt GitHub, GitLab und Gitea-/Forgejo-API-Formate; beliebige unbekannte
Forge-APIs lassen sich nicht automatisch beurteilen.

Reddit bleibt wegen OAuth-, Lösch- und Aufbewahrungsregeln zurückgestellt.

## Geplant: mehr Daten in der Momentaufnahme

Für die Bewertungsregeln fehlt noch:

| Daten | Wofür |
|---|---|
| Inhalt der Manifeste (`pyproject.toml`, `requirements.txt`, `package.json`, `Cargo.toml`, `go.mod`), gekürzt | AI-Thema über Abhängigkeiten wie `openai`, `langchain` |
| Agent-Dateien in Unterordnern (`.github/copilot-instructions.md`, `.claude/`, `.cursor/`) | AI-Mithilfe |
| Hinzugefügte und gelöschte Zeilen je Commit | „50 000 Zeilen in drei Tagen von einer Person“ |
| Gesamtzahl der Commits, Zahl der Commits im Rückblick | „5000 Sterne bei 3 Commits“, Kontinuität |
| Sprachanteile in Bytes | Repos ohne eigentlichen Code |

## Offen

- **„Resource limits for this query exceeded“:** GitHub lehnt manche Gruppen von 20
  Repos als zu aufwendig ab. Im ersten vollständigen Lauf traf das 3 Gruppen. Seit dem
  13.11.2026 halbiert `GitHubRepoSource` eine abgelehnte Gruppe und fragt erneut. Ein
  einzelnes Repo, das auch allein zu aufwendig ist, wird ausgelassen und im Protokoll
  genannt. Im zweiten Lauf trat der Fehler nicht auf, die Abhilfe ist also nur durch
  Tests belegt.
- Die Test-Fixtures für Suche und GraphQL sind von Hand geschrieben, damit keine Namen
  und E-Mail-Adressen echter Personen im Repo landen. Ihre Form ist gegen echte
  Antworten geprüft. Der Sternverlauf ist eine echte Antwort.
