# Bewertung (Bounded Context „Assessment“)

## Aufgabe

Die Bewertung macht aus einer Momentaufnahme ein `Assessment`: Sektion, Punktzahl,
Signale und gegebenenfalls einen Ausschluss. Sie ist reine Logik ohne Ein- und Ausgabe
und kommt ohne LLM aus.

Alle Zahlen in diesem Dokument sind **Startwerte**. Sie stehen als benannte Konstanten
in der Domäne und werden an der Beispielsammlung geeicht (siehe unten).

## Ablauf

```
Assessor.assess(snapshot) → Assessment
  1. Ausschluss prüfen     ExclusionPolicy     erster Treffer gilt
  2. Sektion bestimmen     AiFocusClassifier   MAIN oder AI
  3. Signale sammeln       MomentumCalculator  Aufstieg
                           SubstanceCheck      Arbeit und echtes Interesse
                           AiAssistanceDetector  AI-Mithilfe
  4. Punktzahl             Summe aller Signalgewichte
```

Signale, Sektion und Punktzahl werden **immer** berechnet, auch für ausgeschlossene
Repos. So zeigt `explain` das ganze Bild.

## Punktzahl

**Die Punktzahl ist die Summe der Gewichte aller Signale.** Mehr steckt nicht dahinter.
Der Tooltip auf der Seite listet die Signale auf und erklärt damit die Punktzahl
vollständig.

Ein `Signal` hat eine Art (`kind`), ein Gewicht in Punkten und eine Begründung in
einem Satz. Signale zum AI-Thema haben das Gewicht 0: Sie bestimmen die Sektion, nicht
den Rang.

## Ausschlüsse (`ExclusionPolicy`)

Geprüft wird in dieser Reihenfolge. Der erste Treffer bestimmt den Grund.

| Art | Regel |
|---|---|
| `fork`, `archived`, `mirror` | Das Repo ist ein Fork, archiviert oder ein Spiegel. |
| `no_code` | GitHub erkennt keine Programmiersprache. |
| `collection` | Name, Beschreibung oder Topics nennen eine Sammlung oder Lernmaterial: `awesome`, `curated list`, `interview`, `tutorial`, `roadmap`, `cheatsheet`, `cheat sheet`, `dotfiles`, `leetcode`, `system prompts`, `prompt collection`, `prompt library`. |
| `no_readme` | Es gibt kein README. |
| `language` | Beschreibung und README sind weder deutsch noch englisch (siehe unten). |
| `crypto` | Name, Beschreibung oder Topics nennen Kryptowährungen: `crypto`, `cryptocurrency`, `bitcoin`, `ethereum`, `solana`, `web3`, `defi`, `nft`, `blockchain`, `memecoin`, `altcoin`, `stablecoin`, `airdrop`, `trading bot`, `smart contract`, `binance`, `hyperliquid`. Nicht `cryptography`, `token` oder `wallet`. |
| `low_momentum` | Weniger als 50 neue Sterne in 7 Tagen. |

Begriffe zählen nur als ganze Wörter. Bindestriche und Unterstriche gelten als
Leerzeichen, Groß- und Kleinschreibung ist egal, ein angehängtes Mehrzahl-s zählt mit.
Das gilt für alle Begriffslisten in diesem Dokument.

### Sprache erkennen

Geprüft wird der Fließtext aus Beschreibung und README (die ersten 4000 Zeichen, ohne
Code-Blöcke, Links und HTML).

1. Sind mehr als 20 % der Buchstaben nicht lateinisch (Chinesisch, Kyrillisch,
   Arabisch …), ist es eine andere Sprache.
2. Sonst zählen wir, wie viele Wörter zu den häufigsten deutschen und englischen
   Funktionswörtern gehören (`the`, `and`, `der`, `und` …). Liegt ihr Anteil unter
   15 %, ist es eine andere Sprache.
3. Bei weniger als 40 Wörtern Fließtext gibt es kein Urteil. Das Repo bleibt drin.

## Sektion (`AiFocusClassifier`)

Was als AI-Thema gilt, ist am 12.11.2026 entschieden:

- **AI-Thema:** LLMs, Agenten und Chatbots samt allem, was nur für deren Einsatz
  gebaut ist (Agent-Frameworks, MCP-Server, Prompt- und Skill-Sammlungen,
  Erweiterungen für AI-Coding-Assistenten, Wrapper um Modell-APIs). Ebenso Generatoren
  für Bilder, Musik und Video.
- **Kein AI-Thema:** klassisches maschinelles Lernen (Statistik-Bibliotheken,
  Bilderkennung, Trainings- und Rechen-Frameworks).

Die Regel: Ein Repo gehört in die AI-Sektion, wenn AI-Begriffe an **mindestens zwei
von vier Stellen** stehen.

| Stelle | zählt, wenn |
|---|---|
| Topics | ein Topic einen AI-Begriff enthält |
| Name | der Repo-Name einen AI-Begriff enthält |
| Beschreibung | die Beschreibung einen AI-Begriff enthält |
| README | das README mindestens 5 AI-Begriffe enthält |

**Bekannte Schwäche (880 echte Repos, 12.11.2026):** Die Regel erfasst auch Werkzeuge,
die AI nur als Nebenfunktion erwähnen, etwa einen GPU-Taskmanager mit „LLM model
insights“. Das ist der kleinere Fehler: AI-Werkzeuge in der Hauptliste wären
schlimmer. Ob und wie die Regel enger wird, entscheidet die Beispielsammlung.

Eine einzelne Erwähnung reicht also nicht. Ein Editor mit „AI auto captions“ in der
Beschreibung bleibt in der Hauptliste, bekommt aber ein Signal mit Gewicht 0, damit
man die Erwähnung im Tooltip sieht.

**AI-Begriffe:** `ai`, `llm`, `llms`, `gpt`, `chatgpt`, `openai`, `anthropic`, `claude`,
`deepseek`, `copilot`, `codex`, `ollama`, `langchain`, `mcp`, `rag`, `agentic`,
`ai agent`, `coding agent`, `agent skill`, `subagent`, `multi agent`, `chatbot`,
`genai`, `generative ai`, `large language model`, `prompt engineering`,
`system prompt`, `vibe coding`, `stable diffusion`, `diffusion model`, `comfyui`,
`midjourney`, `text to image`, `image generation`, `text to video`,
`video generation`, `text to music`, `music generation`.

**Bewusst nicht dabei**, weil mehrdeutig: `agent` (User-Agent, Build-Agent), `prompt`
(Shell-Prompt), `cursor` (Textcursor), `gemini` (Gemini-Protokoll), `diffusion`
(Physik). Ebenfalls nicht dabei sind die Begriffe des klassischen maschinellen
Lernens: `machine learning`, `deep learning`, `neural network`, `pytorch`,
`tensorflow`, `computer vision`.

## Aufstieg (`MomentumCalculator`)

Ein Signal `momentum`:

```
Punkte = 20 × log10(Gewinn) × (0,5 + 0,5 × √(Gewinn / Sterne))
```

`Gewinn` sind die neuen Sterne der letzten 7 Tage, `Sterne` ist die Gesamtzahl.

- Der erste Faktor belohnt absolute Aufmerksamkeit, gedämpft durch den Logarithmus.
- Der zweite belohnt Wachstum im Verhältnis zur Größe. Er liegt zwischen 0,5
  (Riese, der kaum wächst) und 1 (alle Sterne sind neu).

| Beispiel | Gewinn / Sterne | Punkte |
|---|---|---|
| Neues Repo | 100 / 100 | 40 |
| Neues Repo, viel Aufmerksamkeit | 1000 / 1000 | 60 |
| Mittleres Repo im Aufwind | 500 / 5000 | 36 |
| `astral-sh/uv` | 389 / 91 943 | 28 |
| `torvalds/linux` | 1094 / 255 489 | 32 |

## Substanz (`SubstanceCheck`)

Hinweise auf echte Arbeit und echtes Interesse.

| Art | Regel | Punkte |
|---|---|---|
| `team` | 2 bis 4 aktive Autoren in 90 Tagen / 5 oder mehr | +5 / +8 |
| `continuity` | Commits von Menschen in 4 bis 7 verschiedenen Wochen / in 8 oder mehr | +5 / +10 |
| `engagement` | Issues von mindestens 3 verschiedenen Personen | +5 |
| `new_project` | Das Repo ist höchstens 30 Tage alt. | +3 |
| `no_echo` | Weniger als ein Fork, Issue-Autor oder Pull Request je 100 Sterne | −25 |
| `fork_farm` | Mindestens 60 % so viele Forks wie Sterne | −25 |

- **`continuity` und `team` zusammen** decken ab, was du wolltest: Mehrere
  Contributors zählen, die ausdauernde Arbeit einer einzelnen Person aber auch.
- **`no_echo` und `fork_farm`** sind die Gegenprobe zu gekauften Sternen. In den
  echten Daten hatten 30 % der Kandidaten Sterne, aber weder Forks noch Issues.
  Darunter waren fast alle Köder-Repos. Das Echo wird an der Sternzahl gemessen, weil
  es Köder mit 1100 Sternen und genau einem Fork gibt.
- **Bekannte Schwäche:** Wir kennen nur die letzten 100 Commits. Bei sehr aktiven
  Repos reichen sie nur wenige Tage zurück. Sind es genau 100, gibt es deshalb kein
  `continuity`-Signal. Abhilfe bringen die geplanten Daten (Zahl der Commits je Woche).

## AI-Mithilfe (`AiAssistanceDetector`)

Führt zur Abwertung, nie zum Ausschluss.

| Art | Regel | Punkte |
|---|---|---|
| `ai_commits` | Anteil der letzten Commits mit AI-Beteiligung, ab 10 % | −30 × Anteil |
| `ai_files` | Anweisungsdateien für AI-Agenten im Hauptverzeichnis | −3 |

- **Ein Commit hat AI-Beteiligung**, wenn ein AI-Werkzeug als Co-Autor eingetragen ist
  oder ihn selbst verfasst hat. Erkannt werden: Claude, Anthropic, Copilot, Cursor,
  Codex, OpenAI, ChatGPT, Devin AI, Gemini, Google Jules, Aider, OpenHands, Windsurf,
  Capy AI, opencode. Namen, die auch Menschen tragen, zählen nur in der eindeutigen
  Form: „Devin AI“ ja, „Devin Smith“ nein.
- **Gewöhnliche Bots** (Dependabot, GitHub Actions, Renovate) zählen weder als AI noch
  als Mensch. Sie fließen in den Anteil nicht ein.
- **Anweisungsdateien:** `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.claude`, `.cursor`,
  `.cursorrules`, `.windsurfrules`, `.clinerules`, `.codex`, `.agents`, `.aider.conf.yml`.
  Das Gewicht ist bewusst klein: Auch `torvalds/linux` und `astral-sh/uv` haben eine
  `AGENTS.md`. Eine `AI_POLICY.md` zählt nicht.

In den echten Daten: 72 % der Repos ohne AI-Commits, 18 % mit mindestens 75 %.

## Befehl `explain`

```
github-anti-ai explain owner/name [--data-dir data]
```

Zeigt für ein Repo aus der heutigen Sammlung Sektion, Punktzahl, Ausschluss und alle
Signale mit Gewicht und Begründung. Auch für Repos, die es nicht in die Ausgabe
geschafft haben. Gibt es zu dem Repo keine Momentaufnahme, meldet der Befehl das.

## Regeln eichen: die Beispielsammlung

Braucht deine Mitarbeit und kommt deshalb als eigener Schritt:

1. Aus einem vollständigen Lauf ziehen wir etwa 100 Repos, quer durch alle
   Punktzahlen.
2. Du gibst jedem ein Urteil: **Edelstein**, **AI-Thema**, **Slop**, **egal**.
3. Wir vergleichen deine Urteile mit denen der Regeln und passen Begriffe und Gewichte
   an, wo sie danebenliegen.
4. Die Beispiele werden zu Tests. Eine spätere Änderung darf die Trefferquote nicht
   verschlechtern.

Offen dabei: In den Momentaufnahmen stehen Namen und E-Mail-Adressen aus Commits.
Bevor Beispiele ins Git-Repo kommen, müssen diese Angaben heraus.

## Noch nicht abgedeckt

Diese Regeln brauchen Daten, die wir noch nicht sammeln (siehe `datensammlung.md`,
„Geplant“):

- AI-Thema über Abhängigkeiten (`openai`, `langchain` in den Manifesten)
- Anweisungsdateien in Unterordnern (`.github/copilot-instructions.md`)
- „50 000 Zeilen in drei Tagen von einer Person“
- Erwähnungen auf Hacker News und Lobste.rs als positives Signal
