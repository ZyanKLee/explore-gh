# Datensammlung (Bounded Context „Acquisition“)

## Aufgabe

Die Datensammlung findet einmal täglich Kandidaten, holt zu jedem eine
Momentaufnahme (`Snapshot`) und speichert sie. Sie **bewertet nicht** und **schließt
nichts aus**: Auch Forks, Krypto-Projekte oder chinesische READMEs landen als
Momentaufnahme im Speicher. Ob ein Repo taugt, entscheidet erst `Assessment`.

## Ablauf

```
CollectSnapshots.run()
  1. Kandidaten finden      alle CandidateSources fragen, Ergebnisse zusammenführen
  2. Schon Erledigtes       Repos mit Momentaufnahme von heute überspringen
  3. In Gruppen von 20:     RepoSource.fetch(gruppe, jetzt)
                            SnapshotStore.append(heute, momentaufnahmen)
  4. Aufräumen              SnapshotStore.prune(heute − 14 Tage)
  → CollectionReport        gefunden, gesammelt, fehlend, fehlgeschlagen, Fehler
```

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
    def discover(self, today: date, limit: int | None = None) -> list[RepoId]: ...

class RepoSource(Protocol):
    def fetch(self, repos: Sequence[RepoId], now: datetime) -> list[Snapshot]: ...
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
- Aufbewahrung: 14 Tage. Das reicht, um Bewertungsregeln an echten Daten
  auszuprobieren, ohne die APIs erneut abzufragen.
- Arbeitsdaten, **nicht** im Git-Repo. Dauerhaft gespeichert werden nur die Ausgaben
  (`Edition`s).

## Fehler und Rate Limits

Gemeinsam für alle GitHub-Adapter:

- `403`/`429` mit `Retry-After`: so lange warten, dann erneut versuchen.
- `x-ratelimit-remaining: 0`: bis `x-ratelimit-reset` warten.
- `5xx`: mit wachsender Pause erneut versuchen, insgesamt höchstens 3 Versuche.
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

Gemessen am 12.11.2026: 60 Kandidaten in 35 Sekunden. Hochgerechnet auf 2000
Kandidaten sind das etwa 2100 Anfragen und 20 Minuten. Erlaubt sind 5000 REST-Anfragen
pro Stunde. Ein vollständiger Lauf ist noch nicht gemessen.

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

## Geplant: weitere Kandidatenquellen

- **Hacker News** (Algolia-API) und **Lobste.rs** (JSON-Endpunkte): Beiträge der
  letzten Tage, die auf ein GitHub-Repo verlinken. Menschen empfehlen dort Projekte
  unabhängig von deren Alter.
- **OSS Insight** (Trending-API): vor dem Bau prüfen, ob und wie sie erreichbar ist.
- **Herkunft bleibt erhalten:** Eine Quelle liefert künftig nicht nur die `RepoId`,
  sondern auch, wo und wie stark das Repo erwähnt wurde (z. B. „Hacker News, 300
  Punkte“). `Assessment` macht daraus ein Signal.

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

- Ein vollständiger Lauf ohne `--limit` steht noch aus.
- Die Test-Fixtures für Suche und GraphQL sind von Hand geschrieben, damit keine Namen
  und E-Mail-Adressen echter Personen im Repo landen. Ihre Form ist gegen echte
  Antworten geprüft. Der Sternverlauf ist eine echte Antwort.
