# Datensammlung (Bounded Context „Acquisition“)

Die Datensammlung findet einmal täglich Kandidaten, holt zu jedem eine Momentaufnahme
(`Snapshot`) und speichert sie. Sie **bewertet nicht** und **schließt nichts aus**: Auch
Forks oder chinesische READMEs landen als Momentaufnahme im Speicher. Ob ein Repo taugt,
entscheidet erst `Assessment`. API-Formate gelangen nie in die Domäne.

Die Community-Listen (HN, Lobsters) sammeln getrennt, siehe `community.md`.

## Ablauf

```
CollectSnapshots.run()
  1. Kandidaten finden     alle CandidateSources fragen, jedes Repo einmal
  2. Schon Erledigtes      Repos mit Momentaufnahme von heute überspringen
  3. Einteilen             neu holen / auffrischen / übernehmen
  4. Übernehmen            ohne Anfragen, sofort gespeichert
  5. Neu holen             in Gruppen von 20, mit Sternverlauf
  6. Auffrischen           in Gruppen von 20, ohne Sternverlauf
  7. Die Besten            bewerten, je Sektion 60 auffrischen
  8. Aufräumen             Momentaufnahmen und Status älter als 14 Tage löschen
  9. Status speichern      wie der Lauf ausging (für publish)
  → CollectionReport       gefunden, gesammelt, fehlend, fehlgeschlagen, Fehler,
                           neu geholt, aufgefrischt, übernommen
```

- `RepoId` vergleicht ohne Rücksicht auf Groß- und Kleinschreibung, wie GitHub.
- Fällt eine Kandidatenquelle aus, steht das im Bericht, die anderen gelten weiter.
- **Gespeichert wird nach jeder Gruppe.** Ein Abbruch verliert höchstens eine Gruppe.
- **Ein erneuter Lauf am selben Tag setzt fort** und holt nur, was fehlt. Wer den Tag neu
  sammeln will, löscht die Datei des Tages.
- Schlägt eine Gruppe fehl, gilt sie als fehlgeschlagen. Nach 3 Fehlschlägen in Folge
  fragt der Lauf nicht weiter. Das Gesammelte bleibt.
- **Probelauf:** `collect --limit N` begrenzt die Zahl der Kandidaten.
- Jeder Schritt meldet sich über `logging`, die Kommandozeile zeigt es an.

## Kandidatensuche (`GitHubSearchCandidates`)

- Eine Suchanfrage pro Erstellungstag der letzten 30 Tage:
  `created:2026-11-12 stars:>=50 fork:false archived:false`, nach Sternen sortiert, eine
  Seite à 100 Treffer. Die Aufteilung nach Tagen umgeht die Grenze von 1000 Treffern.
- Zwischen zwei Suchanfragen 2 Sekunden Pause (30 Suchanfragen pro Minute).
- Jeder Treffer bringt seine Sternzahl mit. Das macht das Weiterverwenden möglich.
- **Abgeschnittene Treffer werden gemeldet** (seit 18.11.2026): Findet GitHub mehr als
  die 100 Treffer einer Seite (`total_count`), warnt das Protokoll, etwa
  `created:2026-11-12: 100 von 347 Treffern, 247 abgeschnitten`. Bricht GitHub die Suche
  ab (`incomplete_results`), warnt es ebenso.

**Offene Frage: weitere Seiten holen?** In den Ausgaben vom 13., 15. und 17.11.2026 war
die Seite an 27 bis 29 von 30 Erstellungstagen voll. Gezeigte Repos standen bis auf
Platz 99 ihres Erstellungstags, je Ausgabe 2 bis 4 auf Platz 81 bis 100. Hinter Platz 100
liegen also vermutlich weitere Kandidaten mit wenigen Sternen und starkem relativem
Wachstum. Zählen würden nur Erstellungstage, die mindestens 14 Tage zurückliegen, jüngere
Repos sind ohnehin ausgeschlossen. Ob sich Seite 2 lohnt, entscheiden die gemeldeten
Zahlen.

**Diese Quelle allein verfehlt einen Teil des Ziels.** Sie findet nur neue Repos, die
schnell Sterne sammeln. Von Hand gebaute Projekte sind oft älter, bevor sie entdeckt werden.

## Momentaufnahme (`GitHubRepoSource`)

Die Fakten kommen über **eine** GraphQL-Abfrage je 10 Repos, der Sternverlauf über eine
REST-Anfrage je Repo.

| Feld | Quelle (GraphQL) | Wofür |
|---|---|---|
| `description`, `homepage`, `topics` | `description`, `homepageUrl`, `repositoryTopics` | AI-Thema, Ausschlüsse, Seite |
| `primary_language` | `primaryLanguage` | „kein Code“, Vielfaltsregel |
| `created_at`, `pushed_at` | `createdAt`, `pushedAt` | Entwicklungszeit, neues Projekt |
| `stars`, `forks`, `pull_requests` | `stargazerCount`, `forkCount`, `pullRequests` | Aufstieg, Echo |
| `recent_issue_authors` | Autoren der letzten 100 Issues, verschiedene Personen, ohne Bots | Engagement, Echo |
| `is_fork`, `is_archived`, `is_mirror` | gleichnamige Felder | Ausschlüsse |
| `owner_created_at`, `owner_contributed_to` | `owner { createdAt, repositoriesContributedTo }` (nur Commits und Pull Requests, ohne eigene Repos; Organisationen nur das Alter) | Vorgeschichte des Besitzers |
| `license` | `licenseInfo.spdxId` | Seite |
| `root_files` | `object(expression: "HEAD:")` | Anweisungsdateien für Agenten |
| `readme` | `README.md`, `readme.md`, `README.rst`, `README.txt`, `README`, gekürzt auf 20 000 Zeichen | AI-Thema, Sprache, Köder, Kopien |
| `recent_commits` | Standard-Branch, bis zu 100 Commits der letzten 90 Tage | AI-Mithilfe, Team, Kontinuität |
| `star_history` | REST: `GET /repos/{owner}/{repo}/stargazers/history` | Aufstieg, Kurve auf der Seite |

Ein `Commit` enthält Zeitpunkt, Autor (GitHub-Login, sonst Git-Name), ob es ein Bot ist
(Name endet auf `[bot]`), die `Co-authored-by`-Einträge und die erste Zeile der Nachricht.

**Sternverlauf:** Stargazer-Listen gibt GitHub seit Juli 2026 nur noch an Admins und
Mitarbeiter heraus. Der Endpunkt `stargazers/history` liefert dagegen Wochen (neueste
zuerst, `week` ist der Sonntag als Unix-Zeit, `days` die neuen Sterne je Tag ab Sonntag).
Wir holen 6 Wochen und bilden daraus `StarHistory`: die neuen Sterne der letzten 35 Tage,
der letzte Eintrag ist heute, Tage ohne Angabe zählen als 0. `gained()` ist der Gewinn der
letzten 14 Tage einschließlich heute.

**Keine Anfrage für Aussichtsloses:** Für ein Repo, das nie gezeigt werden kann (Fork,
archiviert, Spiegel, ohne erkannten Code, `Snapshot.can_never_be_shown`), holt die
Sammlung keinen Sternverlauf. Es bekommt trotzdem eine Momentaufnahme.

## Momentaufnahmen weiterverwenden

Ohne Weiterverwendung kostet jeder Lauf rund 3000 Anfragen und 40 Minuten, fast alles für
den Sternverlauf. Die Suche liefert die heutige Sternzahl gratis. Daraus führen wir den
Verlauf selbst fort.

Für jeden Kandidaten sucht der Lauf die jüngste Momentaufnahme der letzten 3 Tage:

| Lage | Was geschieht | Anfragen |
|---|---|---|
| keine Momentaufnahme in den letzten 3 Tagen, oder eine ohne Sternverlauf | **neu holen:** Fakten und Sternverlauf | 1/10 + 1 |
| Fakten jünger als 3 Tage | **übernehmen:** Momentaufnahme gilt weiter, mit der Sternzahl von heute | 0 |
| Fakten 3 Tage alt oder älter, oder die Quelle kennt die Sternzahl nicht | **auffrischen:** Fakten neu, Sternverlauf fortgeführt | 1/10 |

- **Fortgeführter Sternverlauf** (`StarHistory.continued`): Der Verlauf rückt um die
  vergangenen Tage weiter, der Gewinn seit der letzten Momentaufnahme steht am letzten
  Tag. Verlorene Sterne zählen als 0. Fehlt ein Repo einen Tag lang, steht der ganze
  Gewinn am Tag danach; die Summe im Sternfenster stimmt trotzdem.
- **Auffrischen schlägt fehl:** Kennt die Suche die Sternzahl, wird die ältere
  Momentaufnahme übernommen. Sonst gilt das Repo als fehlgeschlagen.
- **Alter der Fakten:** `taken_at` ist der Tag, zu dem die Momentaufnahme gehört,
  `facts_at` der Zeitpunkt, an dem die Fakten zuletzt von GitHub kamen.
- **Die Besten vor der Veröffentlichung auffrischen:** Nach dem Übernehmen bewertet der
  Lauf alle Momentaufnahmen des Tages und frischt je Sektion die 60 besten nicht
  ausgeschlossenen auf (`FRESH_LEADERS_PER_SECTION`), sofern ihre Fakten nicht von heute
  sind. 60 je Sektion statt 120 insgesamt, damit keine Sektion leer ausgeht; das
  Dreifache der Plätze lässt Luft für Sperre und Vielfaltsregel.
- Verschwundene Repos brauchen keine Regel: Was die Suche nicht mehr findet, bekommt keine
  Momentaufnahme von heute.

Gemessen am 13.11.2026: Folgetag 8 statt 38 Minuten, 401 Repos neu geholt, 2312
übernommen, 113 als Beste aufgefrischt.

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

class CollectionStatusStore(Protocol):
    def save(self, status: CollectionStatus) -> None: ...   # ersetzt den Tag
    def load(self, day: date) -> CollectionStatus | None: ...
    def prune(self, before: date) -> None: ...

class Clock(Protocol):
    def now(self) -> datetime: ...   # immer UTC
```

## Speicherung

- `data/snapshots/JJJJ-MM-TT.jsonl.gz`: eine Momentaufnahme je Zeile. Jeder Lauf hängt
  einen gzip-Block an. Beim Lesen gilt je Repo die letzte Zeile.
- `data/snapshots/JJJJ-MM-TT.status.json`: gefunden, gesammelt, fehlgeschlagen. `publish`
  prüft daran, ob die Sammlung vollständig ist.
- Aufbewahrung 14 Tage. Arbeitsdaten, **nicht** im Git-Repo. Im Betrieb liegen sie im
  Cache von GitHub Actions.
- Dateien älterer Versionen bleiben lesbar: ohne `facts_at` (gilt dann `taken_at`), ohne
  Vorgeschichte des Besitzers (unbekannt), mit Feldern, die keine Regel mehr braucht
  (`open_issues`, `watchers`, `is_template`; seit dem 17.11.2026 nicht mehr gesammelt).

## Fehler und Rate Limits

Gemeinsam für alle GitHub-Anfragen (`github_http.send`):

- `403`/`429` mit `Retry-After`: so lange warten, dann erneut. Mit
  `x-ratelimit-remaining: 0`: bis `x-ratelimit-reset` warten. Ein anderes 403 ist ein
  Fehler.
- `5xx`, Verbindungsfehler oder eine abgeschnittene, unlesbare Antwort: mit wachsender
  Pause erneut, höchstens 3 Versuche. Danach `SourceUnavailable`.
- GraphQL-Fehler vom Typ `NOT_FOUND` betreffen nur einzelne Repos. Jeder andere
  GraphQL-Fehler führt zu `SourceUnavailable`, auch wenn Daten mitkommen. Sonst sähe ein
  verweigerter Zugriff wie ein fehlendes Repo aus.
- **Zu aufwendige Gruppen:** „Resource limits for this query exceeded“ und HTTP 502/504
  (GitHub bricht nach 10 Sekunden ab) liegen an einzelnen Repos. Eine solche Gruppe wird
  sofort halbiert und erneut gefragt, nur ein einzelnes Repo wird bei 502/504 dreimal
  versucht. Ein Repo, das auch allein scheitert, wird ausgelassen und im Protokoll
  genannt. Jede Teilung meldet eine Zeile. Nach mehr als 10 Abbrüchen in einer Gruppe
  (`MAX_TIMEOUTS_PER_BATCH`) gilt GitHub als gestört.
- **Gruppen von 10** (`BATCH_SIZE`, seit 17.11.2026): Mit 20 scheiterte an manchen
  Morgen fast jede Gruppe. Gespeichert wird weiter in Gruppen von 20.
- Gewartet wird über eine übergebene `sleep`-Funktion, damit Tests nicht warten.
- Anfragen laufen nacheinander, nie parallel.

## Zugang zu GitHub

- **Token:** ein *klassischer* personal access token **ohne Scopes**. Er liest nur
  Öffentliches. Damit ist alles geprüft.
- **Ablage:** Umgebungsvariable `GITHUB_TOKEN`, sonst eine Zeile `GITHUB_TOKEN=…` in
  `.env` (steht in `.gitignore`). Die Variable hat Vorrang.
- **Client** (`make_github_client`): setzt `Authorization`, `User-Agent`
  (`explore-gh`), `Accept` und `X-GitHub-Api-Version`. Er zählt die Anfragen eines
  Laufs und verweigert ab 4000 jede weitere (`RequestBudgetExceeded`), als Notbremse.
- Der eingebaute Token in GitHub Actions erlaubt nur 1000 Anfragen pro Stunde, deshalb
  braucht der Betrieb ein eigenes Secret (siehe `veroeffentlichung.md`).

## Budget eines Laufs

| Schritt | Anfragen | Dauer |
|---|---|---|
| Suche | 30 | 2,5 bis 4 Minuten |
| Fakten | eine je 10 Kandidaten, die geholt oder aufgefrischt werden | |
| Sternverlauf | eine je neu geholtem Kandidaten | etwa 0,2 s je Repo |

Erster Lauf ohne Vorgeschichte: rund 2900 Kandidaten, 3000 Anfragen, 40 Minuten.
Folgetag: rund 8 Minuten. Erlaubt sind 5000 Anfragen pro Stunde.

## Konstanten

| Name | Wert | Ort |
|---|---|---|
| `GROWTH_WINDOW_DAYS`, `STAR_HISTORY_DAYS` | 14, 35 | `domain/model.py` |
| `COMMIT_LOOKBACK`, `README_MAX_CHARS` | 90 Tage, 20 000 | `domain/model.py` |
| `SNAPSHOT_RETENTION_DAYS`, `REFRESH_AFTER_DAYS` | 14, 3 | `application/collect_snapshots.py` |
| `FETCH_CHUNK_SIZE`, `MAX_CONSECUTIVE_FAILURES`, `FRESH_LEADERS_PER_SECTION` | 20, 3, 60 | `application/collect_snapshots.py` |
| `BATCH_SIZE`, `MAX_TIMEOUTS_PER_BATCH` | 10, 10 | `adapters/github_repo_source.py` |
| Suchfenster, Mindeststerne, Pause | 30 Tage, 50, 2 s | `adapters/github_search.py` |

## Geplant: mehr Daten

| Daten | Wofür |
|---|---|
| Manifeste (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` …), gekürzt | AI-Thema über Abhängigkeiten |
| Agent-Dateien in Unterordnern (`.github/copilot-instructions.md`, `.claude/`) | AI-Mithilfe |
| Zeilen je Commit | „50 000 Zeilen in drei Tagen von einer Person“ |
| Zahl aller Commits | „5000 Sterne bei 3 Commits“, Kontinuität über 100 Commits hinaus |
| Sprachanteile in Bytes | Repos ohne eigentlichen Code |

Weitere Kandidatenquellen, die auch ältere, von Hand gebaute Projekte finden: GH Archive,
OSS Insight, ecosyste.ms, Paket-Registries (siehe `AGENTS.md`).

## Offen

- Die Test-Fixtures für Suche und GraphQL sind von Hand geschrieben, damit keine Namen
  echter Personen im Repo landen. Ihre Form ist gegen echte Antworten geprüft, der
  Sternverlauf ist eine echte Antwort.
- Eine Prüfung, die die Anfragen eines Laufs gegen ein nachgestelltes GitHub zählt, gab
  es bis zum Neuaufbau (`checks/request_count.py`). Sie ist entfallen, weil ihre
  Referenzdaten veraltet waren.
