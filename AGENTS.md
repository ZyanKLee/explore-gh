# github-anti-ai

Eine persönliche Explore-Seite für Open-Source-Software. Die Hauptliste zeigt
aufstrebende, aktive GitHub-Repos, die überwiegend von Menschen geschrieben wurden.
Separate Plattformlisten (beginnend mit HN) zeigen trendende OSS-Projekte von
GitHub, GitLab und öffentlichen Gitea-/Forgejo-Instanzen. Reine AI- und LLM-Tools
sollen die Hauptliste nicht verwässern.

Der Projektinhaber ist kein Software-Entwickler. Code und Workflows deshalb einfach,
gut nachvollziehbar und wartungsarm halten.

## Werkzeuge

Primäre Datenquelle ist GitHub selbst:

- **REST API (v3)**
  - `/search/repositories` für die Kandidatensuche (z. B. `stars:>N pushed:>DATUM`).
    Pro Suchanfrage höchstens 1000 Ergebnisse, etwa 30 Suchanfragen pro Minute mit
    Token. Größere Mengen über aufgeteilte Anfragen holen (nach Sprache, Zeitraum,
    Sternbereich).
  - Sternverlauf: `GET /repos/{owner}/{repo}/stargazers/history` (neue Sterne je Tag).
    Stargazer-Listen gibt GitHub seit Juli 2026 nur noch an Admins und Mitarbeiter
    eines Repos heraus, sie sind für uns nicht nutzbar.
  - Weitere Repo-Details bei Bedarf: Sprachen, Releases, Contributors,
    `/stats/commit_activity`.
  - Etwa 5000 Anfragen pro Stunde mit Token.
- **GraphQL API (v4)**: um viele Felder vieler Repos gebündelt abzufragen.
  Punktbasiertes Limit, etwa 5000 Punkte pro Stunde.

Es gibt keine offizielle Trending- oder Explore-API. Trending berechnen wir selbst.

## Zusätzliche Datenquellen (vorgemerkt)

- GH Archive (gharchive.org, auch BigQuery): alle öffentlichen Ereignisse, für eigenes Trending
- OSS Insight (ossinsight.io): Trending und Statistiken per API
- ecosyste.ms: Repos, Pakete, Abhängigkeiten, Commits
- deps.dev und OpenSSF Scorecard: Abhängigkeiten, Qualitätssignale
- Paket-Registries (crates.io, PyPI, npm …): Downloadzahlen
- Hacker News (Algolia-API), Lobste.rs, Reddit: eigene Trendlisten, keine Signale in
  der GitHub-Bewertung

Awesome-Listen bewusst **nicht** verwenden.

## Bisherige Entscheidungen

- **AI als Thema** (Tools, die ausschließlich für den Einsatz von AI gebaut sind):
  nur in einer eigenen, separaten Sektion, nie in den Hauptlisten. Gemeint sind LLMs,
  Agenten, Chatbots sowie Generatoren für Bilder, Musik und Video. Klassisches
  maschinelles Lernen zählt nicht dazu. Die genaue
  Abgrenzung steht in `docs/bewertung.md`.
- **AI als Werkzeug** (mit AI geschriebener Code): führt zu einer Abwertung, aber nicht
  zum Ausschluss.
- **Zielgruppe der Funde**: aufstrebende Projekte mit viel Aufmerksamkeit in letzter Zeit,
  ohne AI-Slop. Sowohl mehrere Contributors als auch kontinuierliche Arbeit einer
  einzelnen Person zählen positiv.
- **„Aufstrebend“**: Mischung aus absolutem und relativem Wachstum, z. B. Sternzuwachs
  der letzten 7 Tage im Verhältnis zur bisherigen Größe, mit Mindestschwelle (etwa 50
  neue Sterne). Keine Altersgrenze, kleiner Bonus für neue Projekte.
- **Wiederholungen**: Ein gezeigtes Repo ist 30 Tage gesperrt. Die Sperre wird aus den
  gespeicherten Ausgaben abgeleitet.
- **Vielfalt**: pro Sektion höchstens 4 Repos je Programmiersprache und 2 je Besitzer.
- **Themen**: nicht festgelegt, Interessen ändern sich. Ausnahmen sind die folgenden
  Vorlieben.
- **Plattform**: Projekte für Windows −10 Punkte, für macOS oder iOS −10, für Linux +20.
  Nennt ein Projekt auch Linux, entfallen die Abzüge.
- **Emulatoren für Spielkonsolen** (PS4, PS5, Switch 2, Nintendo, Xbox): −10 Punkte.
- **Unerwünschte Themen**: Roblox −50 Punkte.
- **Ausschlüsse**: Forks, archivierte Repos, Spiegel, Repos ohne eigentlichen Code
  (Linksammlungen, Tutorials, Material zur Vorbereitung auf Bewerbungsgespräche,
  Dotfiles, Prompt-Sammlungen), Köder für Schadsoftware und Kryptowährungen.
- **Sprache**: nur Repos mit deutscher oder englischer Beschreibung und README.
- **Transparenz**: Jede Auf- oder Abwertung wird beim Eintrag begründet, in einem
  aufklappbaren Bereich „Warum Platz …?“. Zuerst war das ein (i) mit Tooltip, der mit
  Tastatur und auf dem Telefon schlecht erreichbar war.
- **Ausgabe**: statische Website plus RSS-Feed, täglich 20 Repos in der Hauptliste und
  20 in der separaten AI-Sektion. Archiv frühere Tage, zum Durchblättern.
- **Community-Ausgaben**: eigene Such-, Erhebungs-, OSS-Filter- und Publikationsläufe
  für HN und Lobsters. Die jeweiligen Plattform-Punkte bestimmen die Rangfolge;
  Projekte gelangen nicht in die GitHub-Bewertung. Projekt-Websites werden zu
  öffentlichen Repos auf GitHub, GitLab und Gitea-/Forgejo-kompatiblen Instanzen
  verfolgt.
- **Hosting**: GitHub Pages mit GitHub Actions, täglicher Lauf per Cron. Das Repo ist
  `ZyanKLee/explore-gh`. Die Workflows beschreibt `docs/veroeffentlichung.md`.
- **Token**: klassischer personal access token ohne Scopes (damit ist alles geprüft).
- **Technik**: Python. Gerendert wird mit Pelican (Jinja2-Vorlagen, eigenes Theme).
  Jeder Tag ist ein Artikel, die AI-Sektion läuft als eigene Kategorie und bekommt
  damit einen eigenen Feed.
- **Architektur**: zwei getrennte Schritte.
  1. Ein eigenständiges Sammelskript, technisch unabhängig von Pelican. Es fragt die
     APIs ab, speichert Momentaufnahmen und bewertet die Repos. Pro Tag schreibt es
     eine Ergebnisdatei.
  2. Pelican rendert nur aus diesen Dateien, ohne API-Zugriffe.
  Die Ergebnisse vergangener Tage werden nie neu berechnet.
- **Klassifizierung**: vorerst ein Regelsystem, kein LLM.
- **Kein Feedback- oder Personalisierungsmechanismus**, um Interessensblasen zu vermeiden.

## Domain-Driven Design

Code und Bezeichner sind auf Englisch, das Glossar verbindet sie mit den deutschen Begriffen.

### Bounded Contexts

- **Acquisition**: Kandidaten finden, APIs abfragen, Ergebnisse in `Snapshot`s übersetzen.
  API-Formate gelangen nie in die Domäne.
- **HN Trending**: HN-Storys finden, Projekt-Websites zu öffentlichen Forge-Repos
  auflösen und eigene HN-Ausgaben kuratieren. Getrennt von GitHub `Snapshot`s.
- **Lobsters Trending**: Lobsters-Storys finden, Projekt-Websites zu öffentlichen
  Forge-Repos auflösen und eigene Lobsters-Ausgaben kuratieren. Getrennt von GitHub
  `Snapshot`s und HN-Ausgaben.
- **Assessment** (Core): Signale, Ausschlüsse, Sektion, Punktzahl
- **Curation** (Core): tägliche `Edition` mit Sperre, Vielfaltsregel und Top 20
- **Publication**: Seitenmodell (reine Funktionen) plus dünne Pelican-Anbindung. Kennt
  nur das JSON-Format der Ausgaben.

### Glossar

| Begriff | Code | Bedeutung |
|---|---|---|
| Repo | `Repo`, `RepoId` | GitHub-Repository als Kandidat, Identität `owner/name` |
| HN-Projekt | `HnProjectCandidate` | öffentliches, auf HN verlinktes Softwareprojekt samt Forge- und HN-Fakten |
| Lobsters-Projekt | `LobstersProjectCandidate` | öffentliches, auf Lobsters verlinktes Softwareprojekt samt Forge- und Lobsters-Fakten |
| Community-Kurator | `CommunityCurator` | gemeinsame Auswahlregeln der HN- und Lobsters-Ausgaben, die Rangfolge gibt die Plattform vor |
| Bezug zur Story | `relates_to_story`, `shared_words` | ein auf einer Website gefundenes Repo teilt Wörter mit Titel, Hostname oder Pfad der Story; das Repo mit den meisten gewinnt |
| Kandidat | `Candidate` | Repo, das eine Quelle heute gefunden hat, samt Sternzahl, falls die Quelle sie kennt |
| Momentaufnahme | `Snapshot` | Alles, was zu einem Zeitpunkt über ein Repo gesammelt wurde. `facts_at` sagt, wann die Fakten zuletzt von GitHub kamen. |
| Sternverlauf | `StarHistory` | Neue Sterne je Tag über 35 Tage. `gained()` ist der Gewinn der letzten 7 Tage. |
| Commit | `Commit` | Zeitpunkt, Autor, Bot ja/nein, Co-Autoren, erste Zeile der Nachricht |
| Kandidatenquelle | `CandidateSource` | Liefert Kandidaten für einen Tag |
| Signal | `Signal` | Beobachtete Tatsache mit Gewicht und Begründung (Text für „Warum Platz …?“ auf der Seite) |
| Aufstieg | `Momentum` | Aktueller Zugewinn an Aufmerksamkeit, aus der Momentaufnahme abgeleitet |
| AI-Thema | `AiFocus` | Repo existiert für den Einsatz von AI und kommt in die AI-Sektion |
| AI-Mithilfe | `AiAssistance` | Hinweise auf AI-geschriebenen Code, führt nur zur Abwertung |
| Ausschluss | `Exclusion` | Grund, ein Repo ganz zu entfernen |
| Substanz | `SubstanceCheck` | Hinweise auf echte Arbeit und echtes Interesse: Team, Kontinuität, Issues. Dazu die Gegenprobe zu gekauften Sternen. |
| Plattform | `PlatformPreference` | Vorliebe des Inhabers: Linux wertet auf, Windows und Apple werten ab |
| Bewertung | `Assessment` | Sektion, Punktzahl, Signale, ggf. Ausschluss. Die Punktzahl ist die Summe der Signalgewichte. Erzeugt vom `Assessor`. |
| Tageswert | `DailyRecord` | Was von einer Bewertung dauerhaft bleibt: Zahlen, Urteil, Rang. Ohne Texte, Commits und Personen. |
| Sektion | `Section` | `MAIN` oder `AI` |
| Ausgabe | `Edition` | Auswahl eines Tages, je Sektion bis zu 20 `Entry`s. Unveränderlich nach Veröffentlichung. |
| Sperre | `Cooldown` | 30 Tage, wird aus vergangenen Ausgaben abgeleitet, nicht separat gespeichert. HN und Lobsters sperren je aus ihren eigenen Ausgaben (`recently_shown`). |
| Vielfaltsregel | `MAX_PER_LANGUAGE`, `MAX_PER_OWNER` | Pro Sektion höchstens 4 Einträge je Programmiersprache und 2 je Besitzer, ebenso in den HN- und Lobsters-Ausgaben |

Persistenz-Abstraktionen heißen `…Store`, nicht „Repository“, weil „Repo“ schon das
GitHub-Repository bezeichnet.

### Projektspezifische Regeln

- Aggregate: `Edition`. Sie prüft ihre Invarianten
  selbst: höchstens 20 pro Sektion, Vielfaltsregel, keine Duplikate. Sie trägt die
  Statistik des Tages (`EditionStats`).
- Ports: `CandidateSource`, `RepoSource`, `SnapshotStore`, `CollectionStatusStore`,
  `DailyRecordStore`, `EditionStore`, `Clock`.
  Adapter melden Ausfälle als `SourceUnavailable`.
- `domain/` ist frei von Ein- und Ausgabe. Die aktuelle Zeit kommt nur über `Clock`.
- Schwellenwerte, Gewichte und Keyword-Listen stehen als benannte Konstanten in der
  Domäne.
- Jedes Signal trägt seine Begründung selbst. Das Theme rendert sie nur.

### Struktur

```plaintext
src/github_anti_ai/{domain,application,adapters,publication}/
                       # publication/ enthält auch Pelican-Plugin und theme/
docs/                  # Konzepte mit Stand und Geplantem: datensammlung.md (Acquisition),
                       # bewertung.md (Assessment), ausgabe.md (Curation),
                       # veroeffentlichung.md (Publication), langzeitdaten.md
data/                  # editions/ (versioniert), snapshots/ (Arbeitsdaten, 14 Tage),
                       # history/ (versioniert), hn-editions/ und lobsters-editions/ (versioniert)
tests/unit/            # Domäne und Use Cases
tests/integration/     # Adapter gegen aufgezeichnete Antworten in fixtures/, dazu die
                       # Regeln gegen die Beispielsammlung (fixtures/labelled/)
checks/                # Hilfsskripte: Anfragen zählen, Beispielsammlung erzeugen
```

## Test-Driven Development

- `pytest`, streng nach TDD. Bugfixes beginnen mit einem reproduzierenden Test.
- Testnamen verwenden die Begriffe aus dem Glossar.
- Ports werden durch In-Memory-Fakes ersetzt statt durch Mocks. Tests verwenden eine
  feste `Clock`.
- Die Testsuite greift nie live auf APIs zu. Live-Tests nur mit `@pytest.mark.live`.
- Jede Bewertungsregel wird in beide Richtungen getestet (greift / greift nicht),
  einschließlich ihrer Begründung.
