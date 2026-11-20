# Bewertung (Bounded Context „Assessment“)

Die Bewertung macht aus einer Momentaufnahme ein `Assessment`: Sektion, Signale,
Punktzahl und gegebenenfalls einen Ausschluss. Sie ist reine Logik ohne Ein- und Ausgabe
und kommt ohne Sprachmodell aus. Das Modell liest erst danach gegen (siehe `ausgabe.md`).

Alle Zahlen und Begriffslisten stehen als benannte Konstanten in `src/explore_gh/domain/`.
Geeicht sind sie an 102 von Hand beurteilten Repos (siehe „Beispielsammlung“).

## Ablauf

```
Assessor.assess(snapshot) → Assessment
  1. Sektion bestimmen     AiFocusClassifier      MAIN oder AI
  2. Signale sammeln       MomentumCalculator     Aufstieg (immer das erste Signal)
                           SubstanceCheck         Arbeit und echtes Interesse
                           OwnerHistory           Vorgeschichte des Besitzers
                           AiAssistanceDetector   AI-Mithilfe
                           PlatformPreference     Linux, Windows, Apple
                           ConsoleEmulatorCheck   Emulatoren für Spielkonsolen
                           DislikedTopics         unerwünschte Themen
                           AiFocusClassifier      AI-Begriffe (Gewicht 0)
  3. Ausschluss prüfen     ExclusionPolicy        erster Treffer gilt
Danach, über alle Repos des Tages:
  4. Kopien                CopyCheck
```

- **Die Punktzahl ist die Summe der Gewichte aller Signale.** Mehr steckt nicht dahinter.
  Die Begründung „Warum Platz …?“ listet die Signale auf und erklärt die Punktzahl damit
  vollständig.
- Ein `Signal` hat eine Art (`kind`), ein Gewicht in Punkten und eine Begründung in einem
  Satz. Die Begründung steht im Code beim Signal, das Theme zeigt sie nur.
- Signale und Sektion werden **immer** berechnet, auch für ausgeschlossene Repos. So
  zeigt `explain` das ganze Bild.

### Begriffslisten

Alle Begriffslisten (`TermList`) zählen nur ganze Wörter. Groß- und Kleinschreibung ist
egal, Bindestriche und Unterstriche gelten als Leerzeichen, ein angehängtes Mehrzahl-s
zählt mit. Mehrere Wörter passen auf jeden Leerraum dazwischen. Ausnahme-Wendungen
(`unless_in`) werden vorher aus dem Text genommen.

Wo nicht anders gesagt, prüfen die Regeln **Name, Beschreibung und Topics**, nicht das
README. Ein README erwähnt vieles, was nichts über das Projekt sagt.

## Ausschlüsse (`ExclusionPolicy`)

In dieser Reihenfolge. Der erste Treffer bestimmt den Grund.

| Art | Regel |
|---|---|
| `fork`, `archived`, `mirror` | Das Repo ist ein Fork, archiviert oder ein Spiegel. |
| `no_code` | GitHub erkennt keine Programmiersprache. |
| `collection` | Sammlung oder Lernmaterial: `awesome`, `curated list`, `interview`, `tutorial`, `roadmap`, `cheatsheet`, `cheat sheet`, `dotfiles`, `leetcode`, `system prompts`, `prompt collection`, `prompt library` |
| `lure` | Köder für Schadsoftware, am Wortlaut oder an der README-Vorlage (siehe unten) |
| `no_readme` | Es gibt kein README. |
| `language` | Weder deutsch noch englisch (siehe unten) |
| `crypto` | Kryptowährungen: `crypto`, `cryptocurrency`, `cryptocurrencies`, `bitcoin`, `ethereum`, `solana`, `web3`, `defi`, `nft`, `blockchain`, `memecoin`, `altcoin`, `stablecoin`, `airdrop`, `trading bot`, `smart contract`, `binance`, `hyperliquid`. Nicht `cryptography`, `token` oder `wallet`. |
| `young` | Weniger als 14 Tage Entwicklung (siehe unten) |
| `low_momentum` | Weniger als 60 neue Sterne in 14 Tagen |
| `copy` | Kopie eines Repos eines anderen Besitzers (siehe unten) |
| `review` | Vom Gegenlesen herausgenommen (siehe `ausgabe.md`) |

Die Regeln von `collection` bis `crypto` brauchen nur Texte (`check_text`). Sie gelten
auch für die HN- und Lobsters-Listen (siehe `community.md`). Ein README, das sich nicht
lesen ließ (`None`), ist dort kein Grund zum Ausschluss, ein leeres schon.

### Köder für Schadsoftware

Hunderte Repos geben sich als Installationspaket bekannter Bezahlsoftware aus („Adobe
Acrobat Pro 2026: Secure Standalone …“). Sie haben etwa 100 oder 1100 Sterne und weder
Forks noch Issues. Das README zeigt einen Knopf, der zu einer Seite mit einem
PowerShell-Befehl führt. Ein Repo gilt als Köder, wenn eines zutrifft:

1. **Wortlaut:** `secure standalone`, `complete standalone`, `standalone desktop`,
   `standalone setup`, `desktop setup`, `desktop installer`, `pre configured`,
   `pre activated`, `full feature`, `all features enabled`, `full version`.
   `standalone`, `setup` und `installer` allein zählen nicht.
2. **README-Vorlage:** ein Bild als Knopf, das auf eine GitHub-Pages-Seite verlinkt
   (in Markdown oder HTML), und das Wort PowerShell.

Köder nach einer neuen Vorlage rutschen durch. Sie bekommen dann meist den Abzug
`no_echo` und das Gegenlesen fängt sie ab. Ändern die Urheber ihre Vorlage, muss die
Regel nachgezogen werden.

### Sprache erkennen

Geprüft wird der Fließtext aus Beschreibung und README: die ersten 4000 Zeichen, ohne
Code-Blöcke, Links, Bilder und HTML.

1. Mehr als 20 % der Buchstaben in nicht lateinischer Schrift (Chinesisch, Kyrillisch,
   Arabisch …): andere Sprache. Das gilt auch für die Beschreibung allein.
2. Weniger als 40 Wörter: kein Urteil, das Repo bleibt.
3. Der Anteil häufiger deutscher und englischer Funktionswörter (`the`, `and`, `der`,
   `und` …) wird mit dem von neun anderen Sprachen in lateinischer Schrift verglichen
   (Spanisch, Portugiesisch, Französisch, Italienisch, Niederländisch, Türkisch,
   Indonesisch, Vietnamesisch, Polnisch). Passt eine andere besser: andere Sprache.
4. Unter 5 % deutsch-englischer Funktionswörter: andere Sprache.

Der Vergleich ersetzt eine feste Schwelle, die englische READMEs aus Listen und Tabellen
aussortiert hatte.

### Mindestens 14 Tage Entwicklung

Zwischen Anlegen (`created_at`) und letztem Push (`pushed_at`) müssen 14 Tage liegen
(`MIN_DEVELOPMENT_DAYS`). Beide Zeitpunkte vergibt GitHub, die Daten der Commits zählen
nicht, weil Köder sie zurückdatieren.

Das ist die eigentliche Antwort auf Köder-Kampagnen: GitHub löscht solche Repos meist
nach wenigen Tagen. Der Preis: Kein Projekt erscheint an seinem ersten Tag. Da die
Kandidatensuche nur Repos bis 30 Tage findet, zeigt die Liste Repos im Alter von 14 bis
30 Tagen.

Das Sternfenster ist deshalb ebenfalls 14 Tage lang (`GROWTH_WINDOW_DAYS`), sonst wären
die Sterne der ersten Tage am 14. Tag schon verloren. Bewusst entschieden: Ein Repo, das
fast alle Sterne in den ersten Tagen bekommt und danach kaum noch, erscheint nie.

### Kopien (`CopyCheck`)

Dasselbe Projekt, von mehreren Konten als eigenes Repo hochgeladen. Anlass war der
15.11.2026: Die Plätze 1 bis 4 belegte viermal derselbe IPTV-Player von vier Konten.

Die Regel braucht alle Repos eines Tages. Sie läuft nach der Einzelbewertung. Ein schon
ausgeschlossenes Repo behält seinen Grund.

- **Kopie** heißt: Bei verschiedenen Besitzern stimmt eines davon überein
  - Name und Beschreibung,
  - Beschreibung und Topics (fängt abgewandelte Namen),
  - das README, wenn es mindestens 500 Zeichen hat (`MIN_COPIED_README_CHARS`).

  Groß- und Kleinschreibung und Leerraum sind egal. Forks zählen nicht mit, Repos ohne
  Beschreibung oder ohne Topics nicht beim jeweiligen Vergleich.
- **Fast gleichzeitig angelegt:** Alle Repos der Gruppe fliegen raus.
- **Eines ist mindestens 7 Tage älter als das nächste** (`COPY_ORIGINAL_MIN_LEAD`): Es
  bleibt als Original, nur die jüngeren fliegen raus.
- Die gleiche Beschreibung allein reicht bewusst nicht: Sonst wären drei verschiedene
  Switch-2-Emulatoren Kopien gewesen.
- **Lücke:** Ändert eine Kampagne Beschreibung und README je Kopie leicht ab, greift die
  Regel nicht.

## Sektion (`AiFocusClassifier`)

- **AI als Thema:** LLMs, Agenten und Chatbots samt allem, was nur für deren Einsatz
  gebaut ist (Agent-Frameworks, MCP-Server, Prompt- und Skill-Sammlungen, Erweiterungen
  für AI-Coding-Assistenten, Wrapper um Modell-APIs). Ebenso Generatoren für Bilder,
  Musik und Video. Das Repo kommt in die AI-Sektion.
- **Kein AI-Thema:** klassisches maschinelles Lernen (Statistik, Bilderkennung,
  Trainings- und Rechen-Frameworks).

**Regel:** AI-Begriffe an **mindestens zwei von vier Stellen**:

| Stelle | zählt, wenn |
|---|---|
| Topics | ein Topic einen AI-Begriff enthält |
| Name | der Repo-Name einen AI-Begriff enthält |
| Beschreibung | die Beschreibung einen AI-Begriff enthält |
| README | das README mindestens 5 AI-Begriffe enthält |

**Ausnahmen, in denen eine Stelle allein genügt:**

- **Topics mit mindestens 2 verschiedenen AI-Begriffen.** Topics sind das eigene Etikett
  des Besitzers.
- **README mit mindestens 10 AI-Begriffen, wenn es weder Beschreibung noch Topics gibt.**
  Als fehlend gilt auch eine Beschreibung, die nur den Namen wiederholt („The official
  code of ToolSpace“). Füllwörter wie „official“, „code“, „repo“, „demo“ zählen dabei nicht.
- **README mit mindestens 50 AI-Begriffen**, egal was sonst dasteht. Die Schwelle ist
  vorsichtig: Darunter liegen zunehmend Werkzeuge, die AI nur nebenbei erwähnen.

Jede Stelle mit AI-Begriffen gibt ein Signal mit Gewicht 0. Es bestimmt die Sektion, nicht
den Rang, und macht eine einzelne Erwähnung in der Begründung sichtbar.

**AI-Begriffe:** `ai`, `llm`, `gpt`, `chatgpt`, `openai`, `anthropic`, `claude`,
`deepseek`, `copilot`, `codex`, `ollama`, `llama`, `llamaindex`, `vllm`, `litellm`,
`gguf`, `vlm`, `language model`, `foundation model`, `huggingface`, `hugging face`,
`diffusers`, `openrouter`, `lm studio`, `open webui`, `gemma`, `mistral`, `qwen`, `sdxl`,
`aigc`, `langchain`, `langgraph`, `crewai`, `autogen`, `tool calling`, `text generation`,
`mcp`, `rag`, `agentic`, `agent`, `ai agent`, `coding agent`, `agent skill`, `subagent`,
`multi agent`, `chatbot`, `genai`, `generative ai`, `large language model`,
`prompt engineering`, `system prompt`, `vibe coding`, `stable diffusion`,
`diffusion model`, `comfyui`, `midjourney`, `text to image`, `image generation`,
`text to video`, `video generation`, `text to music`, `music generation`.

- **`agent`** zählt, außer in den festen Wendungen `user agent`, `build agent`,
  `ssh agent`, `gpg agent`, `tpm agent`, `monitoring agent`, `agent based`.
- **Bewusst nicht dabei**, weil mehrdeutig: `prompt` (Shell-Prompt), `cursor`,
  `gemini` (auch ein Netzprotokoll), `diffusion`. Ebenso nicht die Begriffe des
  klassischen maschinellen Lernens: `machine learning`, `deep learning`,
  `neural network`, `pytorch`, `tensorflow`, `computer vision`.
- **Bekannte Schwäche:** Die Regel erfasst auch Werkzeuge, die AI nur als Nebenfunktion
  nennen. Das ist der kleinere Fehler. Haupt- und Nebenfunktion trennt erst das
  Gegenlesen.

## Aufstieg (`MomentumCalculator`)

```
Punkte = 20 × log10(Gewinn) × (0,5 + 0,5 × √(Gewinn / Sterne))
```

`Gewinn` sind die neuen Sterne der letzten 14 Tage, `Sterne` die Gesamtzahl (mindestens
der Gewinn). Der erste Faktor belohnt absolute Aufmerksamkeit, gedämpft. Der zweite
belohnt Wachstum im Verhältnis zur Größe, zwischen 0,5 (Riese) und 1 (alles neu).

| Beispiel | Gewinn / Sterne | Punkte |
|---|---|---|
| Neues Repo | 100 / 100 | 40 |
| Neues Repo, viel Aufmerksamkeit | 1000 / 1000 | 60 |
| Mittleres Repo im Aufwind | 500 / 5000 | 35,5 |
| `astral-sh/uv` | 389 / 91 943 | 27,6 |
| `torvalds/linux` | 1094 / 255 489 | 32,4 |

## Substanz (`SubstanceCheck`)

| Art | Regel | Punkte |
|---|---|---|
| `team` | 2 bis 4 aktive Autoren in 90 Tagen / 5 oder mehr | +5 / +8 |
| `continuity` | Commits von Menschen in 4 bis 7 verschiedenen Wochen / in 8 oder mehr | +5 / +10 |
| `engagement` | Issues von mindestens 3 verschiedenen Personen | +5 |
| `new_project` | Das Repo ist höchstens 30 Tage alt. | +3 |
| `no_echo` | Weniger als ein Fork, Issue-Autor oder Pull Request je 100 Sterne | −40 |
| `fork_farm` | Mindestens 60 % so viele Forks wie Sterne | −40 |

- `team` und `continuity` zusammen: Mehrere Contributors zählen, die ausdauernde Arbeit
  einer einzelnen Person aber auch.
- `no_echo` und `fork_farm` sind die Gegenprobe zu gekauften Sternen. Fast alle Köder
  haben Sterne, aber weder Forks noch Issues. Mit −40 landet der beste Köder der
  Beispielsammlung auf Rang 201 von 421.
- Bewusst entschieden: Echte Projekte ohne Echo bekommen denselben Abzug. Sie müssen
  erst reifen. Sobald jemand sie forkt oder ein Issue schreibt, entfällt er.
- Forks bleiben Teil des Echos. Sie herauszunehmen hätte 185 weitere, oft echte Repos
  getroffen.
- **Schwäche:** Wir kennen nur die letzten 100 Commits. Sind es genau 100, gibt es kein
  `continuity`-Signal, weil sie bei sehr aktiven Repos nur wenige Tage abdecken.

## Vorgeschichte des Besitzers (`OwnerHistory`)

Köder-Kampagnen benutzen Konten, die eigens dafür angelegt wurden, ohne Mitwirkung an
anderen Projekten.

| Art | Regel | Punkte |
|---|---|---|
| `owner_age` | je 30 Tage Alter des Besitzerkontos | +0,25, höchstens +10 |
| `owner_contributions` | je anderem Projekt, an dem der Besitzer zuletzt mit Commits oder Pull Requests mitgewirkt hat | +1, höchstens +5 |

- **Follower zählen bewusst nicht.** Nicht jeder Entwickler sammelt Leute um sich.
- **Nur Bonus, kein Abzug.** Einem neuen Konto fehlt nur der Bonus.
- **Organisationen** haben ein Alter, aber keine Mitwirkung. Unbekannt heißt: kein Signal.

## AI-Mithilfe (`AiAssistanceDetector`)

Führt zur Abwertung, nie zum Ausschluss.

| Art | Regel | Punkte |
|---|---|---|
| `ai_commits` | Anteil der letzten Commits mit AI-Beteiligung, ab 10 % | −15 × Anteil |
| `ai_files` | Anweisungsdateien für AI-Agenten im Hauptverzeichnis | −3 |

- **AI-Beteiligung:** Ein AI-Werkzeug ist Co-Autor oder hat den Commit selbst verfasst.
  Erkannt werden Claude, Anthropic, Copilot, Cursor, Codex, OpenAI, ChatGPT, Devin AI,
  Gemini, Google Jules, Aider, OpenHands, Windsurf, Capy AI, opencode und Amp, am Namen,
  am GitHub-Konto oder an der E-Mail-Domain. Namen, die auch Menschen tragen, zählen nur
  eindeutig: „Claude Opus 5.5“ ja, „Claude Monet“ nein.
- **Gewöhnliche Bots** (Dependabot, Renovate …) zählen weder als AI noch als Mensch.
- **Anweisungsdateien:** `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.claude`, `.cursor`,
  `.cursorrules`, `.windsurfrules`, `.clinerules`, `.codex`, `.agents`,
  `.aider.conf.yml`. Das Gewicht ist bewusst klein: Auch `torvalds/linux` hat eine
  `AGENTS.md`.
- Der Abzug war zuerst bis zu 30 Punkte. Damit kamen Edelsteine mit viel AI-Mithilfe nie
  in eine Ausgabe, faktisch ein Ausschluss. Deshalb seit dem 12.11.2026 höchstens 15.

## Vorlieben des Inhabers (`preferences.py`)

| Art | Regel | Punkte |
|---|---|---|
| `windows` | nennt Windows: `windows`, `win32`, `win10`, `win11`, `winui`, `wpf` | −10 |
| `apple` | nennt macOS oder iOS: `macos`, `mac`, `osx`, `os x`, `ios`, `ipados`, `iphone`, `ipad`, `watchos`, `tvos`, `visionos`, `apple silicon`, `apple`, `icloud` | −10 |
| `linux` | nennt Linux: `linux`, `wayland`, `gnome`, `kde`, `systemd`, `ubuntu`, `debian`, `fedora`, `archlinux`, `arch linux`, `nixos`, `hyprland` | +20 |
| `console_emulator` | nennt einen Emulator **und** eine Spielkonsole | −50 |
| `disliked_topic` | nennt ein unerwünschtes Thema (`DISLIKED_TOPICS`, zurzeit `roblox`) | −50 je Thema |

- **Linux hebt die Abzüge auf.** Ein Projekt für alle drei Plattformen bekommt +20.
  macOS und iOS zusammen geben nur einen Abzug.
- „MAC address“, „Apple TV-style“ und „Apple style“ zählen nicht als Apple.
- **Emulator:** `emulator`, `emulation`, `recompilation`, `recompiled`, `recompiler`,
  `recomp`, `port`, `ported`, `porting`, `compatibility layer`.
  **Konsole:** `ps1` bis `ps5`, `psx`, `psp`, `ps vita`, `psvita`, `playstation`,
  `switch2`, `switch 2`, `switch game`, `nintendo`, `n64`, `gamecube`, `wii`, `wii u`,
  `3ds`, `xbox`, `dreamcast`. Ein Terminal-Emulator oder eine App für den Xbox-Controller
  bekommt keinen Abzug. Portierungen, die nur den Namen des Spiels nennen, fallen durch.
  Sie fängt das Gegenlesen ab (`game_port`, siehe `ausgabe.md`) und nimmt sie ganz heraus.
- Ein neues unerwünschtes Thema ist eine Zeile in `DISLIKED_TOPICS`.
- **Schwäche:** Die Programmiersprache (Swift, PowerShell) zählt nicht als Hinweis auf
  die Plattform.

## Befehl `explain`

```
explore-gh explain owner/name [--day JJJJ-MM-TT] [--data-dir data]
```

Zeigt für ein Repo aus der Sammlung eines Tages (Standard: heute) Sektion, Punktzahl,
Ausschluss und jedes Signal mit Gewicht und Begründung, auch wenn es nicht gezeigt wurde.
Eine Kopie erkennt der Befehl unter den übrigen Repos desselben Tages.

## Regeländerungen vergleichen

```
uv run python checks/compare_rules.py [--against REF] [--day JJJJ-MM-TT] [--show N]
```

Bewertet die gespeicherten Momentaufnahmen (14 Tage) mit dem Arbeitsstand und mit einem
anderen git-Stand (Standard: der letzte Commit) und listet je Tag:

- Repos, die neu in die Ausgabe kommen, herausfallen oder den Platz wechseln (ohne Sperre
  und Gegenlesen),
- Wechsel der Sektion, neue, aufgehobene und geänderte Ausschlüsse,
- geänderte Punktzahlen, die größten zuerst, mit den Signalen, die sich geändert haben.

So entstehen Angaben wie „in den Daten vom 15.11. verschiebt das 8 Repos“. Jeder Stand
liest die Momentaufnahmen mit seinem eigenen Code. Ein Stand von vor dem 17.11.2026 kann
die danach geschriebenen Momentaufnahmen nicht lesen.

## Beispielsammlung

Am 12.11.2026 hat der Projektinhaber 102 Repos von Hand beurteilt: AI-Thema ja oder nein
und ein Urteil (Edelstein, ok, Slop, raus). Sie liegen ohne Namen und E-Mail-Adressen von
Personen in `tests/integration/fixtures/labelled/`. `test_labelled_examples.py` prüft die
Regeln dagegen: Eine Änderung darf die Übereinstimmung nicht verschlechtern.

```
uv run python checks/make_labelled_examples.py data-test/snapshots/2026-11-12.jsonl.gz data-test/urteile.csv
```

erzeugt die Sammlung nach weiteren Urteilen neu.

Stand:

- **AI-Thema** stimmt bei 86 von 102 überein. Abweichungen: AI-Repos, die AI nur an einer
  Stelle nennen, und Werkzeuge, die AI nur nebenbei erwähnen.
- **Slop:** 13 von 18 sind ausgeschlossen, keiner erreicht die Punktzahl der besten
  Edelsteine.
- **„raus“ ist meist Geschmack:** Emulatoren, Roblox, Begleit-Code zu Forschungsarbeiten.
  Thematische Filter sind bewusst nicht vorgesehen, bis auf die Vorlieben oben.
- **Die Stichprobe ist jung** (alle Repos bis 11 Tage alt). `continuity` und der Bonus
  für neue Projekte lassen sich daran nicht prüfen.

## Noch nicht abgedeckt

Diese Regeln brauchen Daten, die wir noch nicht sammeln (siehe `datensammlung.md`):

- AI-Thema über Abhängigkeiten (`openai`, `langchain` in den Manifesten)
- Anweisungsdateien in Unterordnern (`.github/copilot-instructions.md`)
- „50 000 Zeilen in drei Tagen von einer Person“
