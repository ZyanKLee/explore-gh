# Bewertung (Bounded Context „Assessment“)

## Aufgabe

Die Bewertung macht aus einer Momentaufnahme ein `Assessment`: Sektion, Punktzahl,
Signale und gegebenenfalls einen Ausschluss. Sie ist reine Logik ohne Ein- und Ausgabe
und kommt ohne LLM aus.

Alle Zahlen stehen als benannte Konstanten in der Domäne. Sie sind am 12.11.2026 an
102 von Hand beurteilten Repos geeicht worden (siehe „Beispielsammlung“ unten).

## Ablauf

```
Assessor.assess(snapshot) → Assessment
  1. Ausschluss prüfen     ExclusionPolicy     erster Treffer gilt
  2. Sektion bestimmen     AiFocusClassifier   MAIN oder AI
  3. Signale sammeln       MomentumCalculator  Aufstieg
                           SubstanceCheck      Arbeit und echtes Interesse
                           OwnerHistory        Vorgeschichte des Besitzers
                           AiAssistanceDetector  AI-Mithilfe
                           PlatformPreference  Plattform
                           ConsoleEmulatorCheck  Emulatoren für Spielkonsolen
                           DislikedTopics      unerwünschte Themen
  4. Punktzahl             Summe aller Signalgewichte
```

Signale, Sektion und Punktzahl werden **immer** berechnet, auch für ausgeschlossene
Repos. So zeigt `explain` das ganze Bild.

## Punktzahl

**Die Punktzahl ist die Summe der Gewichte aller Signale.** Mehr steckt nicht dahinter.
Die Begründung auf der Seite listet die Signale auf und erklärt damit die Punktzahl
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
| `lure` | Name, Beschreibung oder Topics klingen nach einem Köder für Schadsoftware: `secure standalone`, `complete standalone`, `standalone desktop`, `standalone setup`, `desktop setup`, `desktop installer`, `pre configured`, `pre activated`, `full feature`, `all features enabled`, `full version`. |
| `no_readme` | Es gibt kein README. |
| `language` | Beschreibung und README sind weder deutsch noch englisch (siehe unten). |
| `crypto` | Name, Beschreibung oder Topics nennen Kryptowährungen: `crypto`, `cryptocurrency`, `bitcoin`, `ethereum`, `solana`, `web3`, `defi`, `nft`, `blockchain`, `memecoin`, `altcoin`, `stablecoin`, `airdrop`, `trading bot`, `smart contract`, `binance`, `hyperliquid`. Nicht `cryptography`, `token` oder `wallet`. |
| `young` | Weniger als 14 Tage Entwicklung auf GitHub (siehe unten). |
| `low_momentum` | Weniger als 60 neue Sterne in 14 Tagen. |

Begriffe zählen nur als ganze Wörter. Bindestriche und Unterstriche gelten als
Leerzeichen, Groß- und Kleinschreibung ist egal, ein angehängtes Mehrzahl-s zählt mit.
Das gilt für alle Begriffslisten in diesem Dokument.

### Kopien (`CopyCheck`)

Dasselbe Projekt, von mehreren Konten als eigenes Repo hochgeladen. Für GitHub sind das
keine Forks, der Ausschluss `fork` greift also nicht. Anlass war die Ausgabe vom
15.11.2026: Die Plätze 1 bis 4 der Hauptliste belegte viermal `IPTV_Player_2.0`, von vier
Konten innerhalb von zehn Minuten angelegt, jedes mit rund 670 Sternen an einem Tag und
genau 12 Forks.

Anders als die übrigen Ausschlüsse braucht diese Regel alle Repos eines Tages. Sie läuft
deshalb nach der Bewertung der einzelnen Repos und vergibt die Art `copy`. Ein Repo, das
schon aus einem anderen Grund ausgeschlossen ist, behält seinen Grund.

- **Kopie** heißt, bei verschiedenen Besitzern stimmt eines davon überein:
  - Name und Beschreibung,
  - Beschreibung und Topics (fängt Kampagnen, die den Namen abwandeln, etwa
    `IPTV_Player_2.0` und `IPTV_Player2.0`),
  - das README, wenn es mindestens 500 Zeichen hat (`MIN_COPIED_README_CHARS`).

  Groß- und Kleinschreibung und Leerraum sind egal. Forks zählen nicht mit, ebenso
  wenig Repos ohne Beschreibung oder ohne Topics beim jeweiligen Vergleich.
- **Fast gleichzeitig angelegt:** Alle Repos der Gruppe werden ausgeschlossen.
- **Eines ist mindestens 7 Tage älter als das nächste** (`COPY_ORIGINAL_MIN_LEAD`): Es
  bleibt als mutmaßliches Original, nur die jüngeren werden ausgeschlossen.

In der Sammlung vom 15.11.2026 fand die Regel vier Kampagnen: 96 Kopien von
`ai--manus2.0`, 49 des IPTV-Players, 15 von `GitHub-Copilot-app` und 3 eines
Path-of-Exile-Helfers. Die gleiche Beschreibung allein reicht bewusst nicht: Damit
wären drei verschiedene Switch-2-Emulatoren als Kopien durchgegangen.

**Bekannte Lücke:** Ändert eine Kampagne Beschreibung und README je Kopie leicht ab,
greift die Regel nicht.

### Mindestens 14 Tage Entwicklung

Ein Repo wird erst gezeigt, wenn zwischen seinem Anlegen (`created_at`) und dem letzten
Push (`pushed_at`) mindestens 14 Tage liegen (`MIN_DEVELOPMENT_DAYS`). Beide Zeitpunkte
vergibt GitHub selbst. Die Daten der Commits zählen nicht, weil Köder sie zurückdatieren.

Die Regel ist die eigentliche Antwort auf Köder-Kampagnen: Jede neue Vorlage rutscht
durch die Begriffslisten, aber GitHub löscht solche Repos meist nach wenigen Tagen. Was
nach 14 Tagen noch da ist und weiterentwickelt wird, ist selten ein Köder.

- **Preis:** Kein Projekt erscheint mehr an seinem ersten Tag. Am 15.11.2026 waren 21
  der besten 40 Repos der Hauptliste zu jung.
- **Sternfenster:** Der Aufstieg zählt deshalb die Sterne der letzten 14 statt 7 Tage,
  mit Schwelle 60 statt 50. Sonst wären die Sterne der ersten Tage am 14. Tag schon aus
  dem Fenster gefallen. Mit beiden Regeln waren am 15.11.2026 in der Hauptliste 235
  Repos zeigbar (mit dem alten Fenster 130), in der AI-Sektion 131 (75).
- **Bewusst so entschieden (15.11.2026):** Ein Repo, das fast alle Sterne an den ersten
  ein, zwei Tagen bekommt und danach kaum noch, fällt unter die Schwelle und erscheint
  nie. Wer nur am Anfang Aufmerksamkeit bekommt, ist vermutlich weniger interessant,
  als es zuerst schien. Die Sammlung frischt `pushed_at` nur alle 3 Tage auf, ein Repo
  wird also erst am 14. bis 17. Tag zeigbar. Ein Fenster von 21 Tagen hätte solche
  Repos mitgenommen und ist deshalb nicht gewählt worden.
- **Die Kandidatensuche findet nur Repos, die höchstens 30 Tage alt sind.** Gezeigt
  werden damit Repos im Alter von 14 bis 30 Tagen.

### Köder für Schadsoftware

Hunderte Repos geben sich als Installationspaket bekannter Bezahlsoftware aus („Adobe
Acrobat Pro 2026: Secure Standalone …“, „Xshell: Advanced SSH/SFTP Terminal Emulator
for Windows“). Sie haben etwa 100 oder 1100 Sterne und weder Forks noch Issues. Ihr
README zeigt einen Knopf, der zu einer Seite mit einem PowerShell-Befehl führt.

Ein Repo gilt als Köder, wenn eines von beidem zutrifft:

1. **Wortlaut:** Name, Beschreibung oder Topics enthalten eine der Wendungen aus der
   Tabelle oben. `standalone`, `setup` und `installer` allein zählen nicht, sie stehen
   auch in ehrlichen Beschreibungen.
2. **README-Vorlage:** Das README enthält ein Bild als Knopf, das auf eine
   GitHub-Pages-Seite verlinkt (`[![](files/button.png)](https://….github.io/…)`
   oder dasselbe in HTML), und nennt PowerShell.

In den 880 echten Repos schließt das 156 aus (18 %), 60 davon schon über den Wortlaut.
Keines der 156 hat einen Fork, ein Issue oder einen Pull Request je 100 Sterne. Von den
18 als Slop beurteilten Repos der Beispielsammlung sind 13 ausgeschlossen, 9 davon als
Köder.

**Bekannte Lücke:** Köder nach einer neuen Vorlage rutschen durch den Ausschluss. Sie
bekommen dann noch den Abzug `no_echo` und kommen damit nicht in eine Ausgabe. Ändern
die Urheber ihre Vorlage, muss die Regel nachgezogen werden. So geschehen bei
`Pereira001/dlss5-manager`, das den Knopf in HTML statt in Markdown schreibt.

### Sprache erkennen

Geprüft wird der Fließtext aus Beschreibung und README (die ersten 4000 Zeichen, ohne
Code-Blöcke, Links und HTML).

1. Sind mehr als 20 % der Buchstaben nicht lateinisch (Chinesisch, Kyrillisch,
   Arabisch …), ist es eine andere Sprache. Das gilt auch für die Beschreibung
   allein, selbst wenn das README englisch ist.
2. Bei weniger als 40 Wörtern Fließtext gibt es sonst kein Urteil. Das Repo bleibt
   drin.
3. Wir zählen, wie viele Wörter zu den häufigsten deutschen und englischen
   Funktionswörtern gehören (`the`, `and`, `der`, `und` …), und ebenso für neun andere
   Sprachen in lateinischer Schrift (Spanisch, Portugiesisch, Französisch, Italienisch,
   Niederländisch, Türkisch, Indonesisch, Vietnamesisch, Polnisch). Passt eine dieser
   Listen besser als die deutsch-englische, ist es eine andere Sprache.
4. Liegt der deutsch-englische Anteil unter 5 %, ist es ebenfalls eine andere Sprache.

Der Vergleich mit anderen Sprachen ersetzt seit der Eichung eine feste Schwelle von
15 %. Die hatte englische READMEs aussortiert, die fast nur aus Listen und Tabellen
bestehen (6 von 152 Sprach-Ausschlüssen in den echten Daten).

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

**Ausnahme, in der die Topics allein genügen:** Stehen dort mindestens 2 verschiedene
AI-Begriffe, gehört das Repo in die AI-Sektion. Topics vergibt der Besitzer selbst als
Etikett. Anlass war `huawei-csl/MACaQ` am 15.11.2026: Topics `llm`, `local-ai`,
`image-generation`, `video-generation`, aber kein AI-Begriff in Name und Beschreibung
und nur 3 im README, und damit auf Platz 13 der Hauptliste. In den Daten vom 15.11.
verschiebt die Ausnahme 4 von 1067 Repos der Hauptliste: drei AI-Projekte und einen
Köder mit erfundenen Topics.

**Zwei Ausnahmen, in denen das README allein genügt:**

- Hat ein Repo weder Beschreibung noch Topics, bleiben ihm nur zwei Stellen. Dann
  reicht ein README mit mindestens 10 AI-Begriffen.
  Als fehlend gilt auch eine Beschreibung, die nur den Namen wiederholt, etwa „The
  official code of ToolSpace“ (`dongguanting/ToolSpace` am 15.11.2026: 20 AI-Begriffe
  im README, Platz 9 der Hauptliste). Füllwörter wie „official“, „code“, „repo“ oder
  „demo“ zählen dabei nicht. In den Daten vom 15.11. verschiebt das 8 Repos, darunter
  `deepseek-ai/chat-demo` und drei Forschungs-Repos von `MUSE-AI-Lab`.
- Ein README mit mindestens 50 AI-Begriffen entscheidet immer, egal was sonst dasteht.
  Anlass war `storytold/craft-anything` am 13.11.2026: 62 AI-Begriffe im README, aber
  keiner in Name, Beschreibung oder Topics, und damit auf Platz 5 der Hauptliste.

Die Schwelle 50 ist vorsichtig gewählt. In den Daten vom 13.11. verschiebt sie 2 von
486 Repos der Hauptliste. Schon ab 40 wären es 7, ab 30 wären es 11, darunter aber
zunehmend Werkzeuge, die AI nur nebenbei erwähnen.

**Bekannte Schwäche:** Die Regel erfasst auch Werkzeuge, die AI nur als Nebenfunktion
erwähnen, etwa einen GPU-Taskmanager mit „LLM model insights“ oder ein Schreibtisch-
Panel mit einem Widget für AI-Kontingente. Das ist der kleinere Fehler: AI-Werkzeuge in
der Hauptliste wären schlimmer. Mit Begriffslisten lässt sich Haupt- und Nebenfunktion
nicht trennen. Dichte und Position der Begriffe im README haben es in der
Beispielsammlung auch nicht geschafft.

Eine einzelne Erwähnung reicht also nicht. Ein Editor mit „AI auto captions“ in der
Beschreibung bleibt in der Hauptliste, bekommt aber ein Signal mit Gewicht 0, damit
man die Erwähnung in der Begründung sieht.

**AI-Begriffe:** `ai`, `llm`, `llms`, `gpt`, `chatgpt`, `openai`, `anthropic`, `claude`,
`deepseek`, `copilot`, `codex`, `ollama`, `langchain`, `mcp`, `rag`, `agentic`,
`agent`, `ai agent`, `coding agent`, `agent skill`, `subagent`, `multi agent`, `chatbot`,
`genai`, `generative ai`, `large language model`, `prompt engineering`,
`system prompt`, `vibe coding`, `stable diffusion`, `diffusion model`, `comfyui`,
`midjourney`, `text to image`, `image generation`, `text to video`,
`video generation`, `text to music`, `music generation`.

**Seit dem 15.11.2026 dazu:** Namen von Laufzeiten, Modellfamilien und Werkzeugen:
`llama`, `llamaindex`, `vllm`, `litellm`, `gguf`, `vlm`, `language model`,
`foundation model`, `huggingface`, `hugging face`, `diffusers`, `openrouter`,
`lm studio`, `open webui`, `gemma`, `mistral`, `qwen`, `sdxl`, `aigc`, `langgraph`,
`crewai`, `autogen`, `tool calling`, `text generation`. In den Daten vom 15.11.
wechseln dadurch 30 von 2880 Repos in die AI-Sektion, keines zurück.
Erwogen und verworfen: das README im Gegenzug erst ab 6 statt 5 AI-Begriffen zu
zählen. Das hätte 14 Repos in der Hauptliste gehalten, davon 11 mit AI als Thema.
`gemini` bleibt draußen, weil es auch ein Netzprotokoll bezeichnet.

**`agent` zählt seit dem 13.11.2026 mit.** Vorher galt das Wort als mehrdeutig. In den
echten Daten nannten es 29 von 519 Repos der Hauptliste, und fast alle waren Werkzeuge
für AI-Agenten („Checkouts for agents“, „terminals for coding agents“). Ausgenommen
bleiben feste Wendungen: `user agent`, `build agent`, `ssh agent`, `gpg agent`,
`tpm agent`, `monitoring agent`, `agent based`. Die Änderung verschiebt 33 Repos in die
AI-Sektion, etwa 6 davon zu Unrecht, weil sie Agenten nur am Rand erwähnen.

`tpm agent` kam am 13.11.2026 dazu: `Foxboron/ssh-tpm-agent` (ein ssh-agent für TPMs)
landete in der Lobsters-AI-Sektion, weil sein Name 36-mal im README steht und „ssh tpm
agent“ nicht unter `ssh agent` fällt. Die Beispielsammlung enthält keinen solchen Fall.

**Bewusst nicht dabei**, weil mehrdeutig: `prompt` (Shell-Prompt), `cursor`
(Textcursor), `gemini` (Gemini-Protokoll), `diffusion` (Physik). Ebenfalls nicht dabei
sind die Begriffe des klassischen maschinellen Lernens: `machine learning`,
`deep learning`, `neural network`, `pytorch`, `tensorflow`, `computer vision`.

## Aufstieg (`MomentumCalculator`)

Ein Signal `momentum`:

```
Punkte = 20 × log10(Gewinn) × (0,5 + 0,5 × √(Gewinn / Sterne))
```

`Gewinn` sind die neuen Sterne der letzten 14 Tage (bis 15.11.2026: 7 Tage), `Sterne`
ist die Gesamtzahl.

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
| `no_echo` | Weniger als ein Fork, Issue-Autor oder Pull Request je 100 Sterne | −40 |
| `fork_farm` | Mindestens 60 % so viele Forks wie Sterne | −40 |

- **`continuity` und `team` zusammen** decken ab, was du wolltest: Mehrere
  Contributors zählen, die ausdauernde Arbeit einer einzelnen Person aber auch.
- **`no_echo` und `fork_farm`** sind die Gegenprobe zu gekauften Sternen. In den
  echten Daten hatten 30 % der Kandidaten Sterne, aber weder Forks noch Issues.
  Darunter waren fast alle Köder-Repos. Das Echo wird an der Sternzahl gemessen, weil
  es Köder mit 1100 Sternen und genau einem Fork gibt. Der Abzug war zuerst −25. Damit
  kamen Köder mit 1000 Sternen bis auf Rang 51 der Hauptliste. Mit −40 liegt der beste
  auf Rang 201 von 421.
- **Köder täuschen Kontinuität vor:** Sie datieren Commits zurück und bekommen so
  `continuity`. Das fällt gegen den Abzug nicht ins Gewicht.
- **Bekannte Schwäche:** Wir kennen nur die letzten 100 Commits. Bei sehr aktiven
  Repos reichen sie nur wenige Tage zurück. Sind es genau 100, gibt es deshalb kein
  `continuity`-Signal. Abhilfe bringen die geplanten Daten (Zahl der Commits je Woche).

## Vorgeschichte des Besitzers (`OwnerHistory`)

Köder-Kampagnen benutzen Konten, die eigens dafür angelegt wurden. Die vier geprüften
Konten der Kampagne vom 15.11.2026 waren alle am 14.10.2026 innerhalb von anderthalb
Stunden entstanden und wirkten an keinem anderen Projekt mit. Die Besitzer echter
Projekte hatten Konten aus den Jahren 2017 bis 2023.

| Art | Regel | Punkte |
|---|---|---|
| `owner_age` | je 30 Tage Alter des Besitzerkontos | +0,25, höchstens +10 (nach gut 3 Jahren) |
| `owner_contributions` | je anderem Projekt, an dem der Besitzer zuletzt mit Commits oder Pull Requests mitgewirkt hat | +1, höchstens +5 |

- **Follower zählen bewusst nicht.** Nicht jeder Entwickler sammelt Leute um sich.
- **Kein Abzug, nur Bonus:** Ein neues Konto verliert nichts, ihm fehlt nur der Bonus.
- **Organisationen** haben ein Alter, aber keine Mitwirkung an anderen Projekten.
- **Unbekannt** (Momentaufnahmen von vor dem 15.11.2026): kein Signal.

## Gegenlesen (`Reviewer`, `CopilotReviewer`)

Die Regeln oben erkennen bekannte Muster. Jede neue Kampagne rutscht zunächst durch.
Deshalb liest seit dem 15.11.2026 ein Sprachmodell die Repos gegen, die gezeigt würden.
Es bestimmt weder Rang noch Sektion, es kann nur herausnehmen. Wann und wie oft es
gefragt wird, steht in `ausgabe.md`.

| Kategorie | Bedeutung | Folge |
|---|---|---|
| `ok` | Ein echtes Softwareprojekt. Gilt auch im Zweifel. | bleibt |
| `malware` | Köder: gibt sich als bekannte Software, Crack oder Gratis-Version aus und führt zu einem Download statt zu Quellcode. | raus |
| `piracy` | Umgeht Kopierschutz oder Lizenzprüfungen oder verteilt geschützte Inhalte. Ein Abspielprogramm oder Emulator allein nicht. | raus |
| `scam` | Betrug, Spam, reine Werbung. | raus |
| `no_software` | Linksammlung, Kursmaterial, Konfiguration, Prompt-Sammlung, Kopie eines fremden Projekts. | raus |
| `placeholder` | Ankündigung ohne Code, automatisch erzeugter Inhalt ohne eigene Arbeit. | raus |

- **Geschmack zählt nicht.** Thema, Programmiersprache, Qualität des Codes und der
  Einsatz von AI sind dem Modell als Ausschlussgrund ausdrücklich untersagt. Sonst
  entstünde die Interessensblase, die das Projekt vermeiden will.
- **Was das Modell sieht:** je Repo Name, Beschreibung, Topics, Sprache, Sterne, Forks,
  Alter von Repo und Besitzerkonto und die ersten 1500 Zeichen des README. 10 Repos je
  Aufruf, also etwa 4 Aufrufe am Tag.
- **Technik:** die Copilot-CLI (`copilot -p … -s --no-ask-user`). Sie ist ein Agent, der
  Werkzeuge benutzen könnte. Hier ist ihr keines erlaubt, sie darf nicht nachfragen und
  startet in einem leeren Verzeichnis. Welches Modell antwortet, bestimmt die CLI. Mit
  der Umgebungsvariable `COPILOT_MODEL` lässt es sich festlegen.
- **Fremde Texte im Prompt:** Ein README kann versuchen, das Modell zu einer Einstufung
  zu überreden. Der Prompt warnt davor. Gelingt es trotzdem, bleibt das Repo so in der
  Liste, wie es ohne Gegenlesen dort stünde. Der Text des Modells erscheint nie auf der
  Seite: Gezeigte Einträge tragen nur den festen Satz „Gegengelesen von Copilot:
  unauffällig“.
- **Noch nie gegen die echte CLI gelaufen** (Stand 15.11.2026). Getestet ist der
  Adapter gegen einen Stellvertreter. Aufruf und Schalter stammen aus der Dokumentation
  von GitHub.

## Nicht übernommen: Forks nicht mehr als Echo zählen

Die Köder vom 15.11.2026 hatten je genau 12 Forks und entgingen damit dem Abzug „kaum
Echo“. Die Idee, Forks dort nicht mehr mitzuzählen, hätte in der Sammlung dieses Tages
185 weitere Repos mit −40 getroffen, darunter klar echte wie `paulirish/chrome-capture`.
Sie ist deshalb verworfen.

## AI-Mithilfe (`AiAssistanceDetector`)

Führt zur Abwertung, nie zum Ausschluss.

| Art | Regel | Punkte |
|---|---|---|
| `ai_commits` | Anteil der letzten Commits mit AI-Beteiligung, ab 10 % | −15 × Anteil |
| `ai_files` | Anweisungsdateien für AI-Agenten im Hauptverzeichnis | −3 |

- **Ein Commit hat AI-Beteiligung**, wenn ein AI-Werkzeug als Co-Autor eingetragen ist
  oder ihn selbst verfasst hat. Erkannt werden: Claude, Anthropic, Copilot, Cursor,
  Codex, OpenAI, ChatGPT, Devin AI, Gemini, Google Jules, Aider, OpenHands, Windsurf,
  Capy AI, opencode, Amp. Erkannt wird am Namen, am GitHub-Konto oder an der
  E-Mail-Domain (`anthropic.com`, `openai.com`, `cursor.com` …). Namen, die auch
  Menschen tragen, zählen nur in der eindeutigen Form: „Devin AI“ ja, „Devin Smith“
  nein, „Claude Opus 5.5“ ja, „Claude Monet“ nein.
- **Gewöhnliche Bots** (Dependabot, GitHub Actions, Renovate) zählen weder als AI noch
  als Mensch. Sie fließen in den Anteil nicht ein.
- **Anweisungsdateien:** `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.claude`, `.cursor`,
  `.cursorrules`, `.windsurfrules`, `.clinerules`, `.codex`, `.agents`, `.aider.conf.yml`.
  Das Gewicht ist bewusst klein: Auch `torvalds/linux` und `astral-sh/uv` haben eine
  `AGENTS.md`. Eine `AI_POLICY.md` zählt nicht.

In den echten Daten: 72 % der Repos ohne AI-Commits, 18 % mit mindestens 75 %.

## Plattform (`PlatformPreference`)

Eine Vorliebe des Projektinhabers, entschieden am 12. und 13.11.2026.

| Art | Regel | Punkte |
|---|---|---|
| `windows` | Name, Beschreibung oder Topics nennen Windows, aber nicht Linux | −10 |
| `apple` | … nennen macOS oder iOS, aber nicht Linux | −10 |
| `linux` | … nennen Linux | +20 |

- **Linux hebt die Abzüge auf.** Nennt ein Projekt auch Linux, entfallen die Abzüge
  für Windows und Apple. Den Bonus gibt es trotzdem. Ein Projekt für alle drei
  Plattformen bekommt also +20.
- **macOS und iOS zusammen** geben nur einen Abzug.
- **Das README zählt nicht.** Installationsanleitungen nennen jede Plattform, das sagt
  nichts über das Projekt.
- **Begriffe:** Windows: `windows`, `win32`, `win10`, `win11`, `winui`, `wpf`. Apple:
  `macos`, `mac`, `osx`, `os x`, `ios`, `ipados`, `iphone`, `ipad`, `watchos`, `tvos`,
  `visionos`, `apple silicon`, `apple`, `icloud` (die letzten beiden seit dem
  15.11.2026). Linux: `linux`, `wayland`, `gnome`, `kde`, `systemd`,
  `ubuntu`, `debian`, `fedora`, `archlinux`, `arch linux`, `nixos`, `hyprland`.
  „MAC address“ zählt nicht als Mac, „Apple TV-style“ und „Apple style“ nicht als Apple:
  Sie beschreiben ein Aussehen, etwa bei Startbildschirmen für Android TV.
- **Die Werte** waren zuerst −3 und +6. Bei Punktzahlen um 60 bis 90 in den oberen
  Rängen fiel das kaum ins Gewicht.
- **Bekannte Schwäche:** Die Programmiersprache (Swift, PowerShell) zählt nicht als
  Hinweis auf die Plattform.

## Emulatoren für Spielkonsolen (`ConsoleEmulatorCheck`)

Ebenfalls eine Vorliebe des Projektinhabers, entschieden am 13.11.2026.

| Art | Regel | Punkte |
|---|---|---|
| `console_emulator` | Name, Beschreibung oder Topics nennen einen Emulator **und** eine Spielkonsole | −50 |

- **Emulator:** `emulator`, `emulation`, `recompilation`, `recompiled`, `recompiler`,
  `recomp`, `port`.
- **Konsole:** `ps1` bis `ps5`, `psx`, `psp`, `ps vita`, `psvita`, `playstation`,
  `switch2`, `switch 2`, `nintendo`, `n64`, `gamecube`, `wii`, `wii u`, `3ds`, `xbox`,
  `dreamcast`. Die älteren Konsolen kamen am 15.11.2026 dazu, nachdem eine
  PS3-Portierung ohne Abzug durchgegangen war.
- Beides muss vorkommen. Ein Terminal-Emulator oder eine App für den Xbox-Controller
  bekommt keinen Abzug.
- **Nicht erfasst:** Portierungen, die keine Konsole nennen, sondern nur den Namen des
  Spiels.

## Unerwünschte Themen (`DislikedTopics`)

Eine Vorliebe des Projektinhabers. Nennen Name, Beschreibung oder Topics eines dieser
Themen, gibt es einen Abzug. Ein neues Thema ist eine Zeile in `DISLIKED_TOPICS`.

| Art | Thema | Punkte | Seit |
|---|---|---|---|
| `disliked_topic` | `roblox` | −50 | 13.11.2026 |

Mit −50 kommt ein solches Repo praktisch nie in eine Ausgabe, bleibt aber über
`explain` nachvollziehbar.

## Befehl `explain`

```
github-anti-ai explain owner/name [--day JJJJ-MM-TT] [--data-dir data]
```

Zeigt für ein Repo aus der Sammlung eines Tages (Standard: heute) Sektion, Punktzahl, Ausschluss und alle
Signale mit Gewicht und Begründung. Auch für Repos, die es nicht in die Ausgabe
geschafft haben. Gibt es zu dem Repo keine Momentaufnahme, meldet der Befehl das.

## Beispielsammlung

Am 12.11.2026 hat der Projektinhaber 102 Repos aus dem Probelauf von Hand beurteilt:
AI-Thema ja oder nein, dazu ein Urteil (Edelstein, ok, Slop, raus). Die Sammlung liegt
ohne Namen und E-Mail-Adressen von Personen unter
`tests/integration/fixtures/labelled/`. `tests/integration/test_labelled_examples.py`
prüft die Regeln dagegen: Eine Änderung darf die Übereinstimmung nicht verschlechtern.

Neu erzeugen nach weiteren Urteilen:

```
uv run python checks/make_labelled_examples.py data-test/snapshots/2026-11-12.jsonl.gz data-test/urteile.csv
```

### Ergebnis der Eichung

| Was | Vorher | Nachher |
|---|---|---|
| AI-Thema stimmt mit dem Urteil überein | 85 von 102 | 88 von 102 (86 seit dem 13.11.: `agent` als AI-Begriff und die README-Schwelle 50 kosten je ein Urteil) |
| Englische READMEs fälschlich als fremdsprachig aussortiert (alle 880) | 6 | 0 |
| Bester Rang eines Köders in der Hauptliste (421 Repos) | 51 | 201 |

Geändert wurden die Sprachregel, die Ausnahme für Repos ohne Beschreibung, der Abzug
für `no_echo` und `fork_farm` (25 → 40) und der Abzug für `ai_commits` (30 → 15).

### Was die Regeln nicht treffen

- **AI-Thema, 14 Abweichungen.** 8 AI-Repos landen in der Hauptliste, meist weil nur
  eine Stelle AI nennt (z. B. `agentic` nur in der Beschreibung) oder gar keine. 6
  Repos landen zu Unrecht in der AI-Sektion, weil sie AI als Nebenfunktion erwähnen.
  Darunter ist ein Edelstein (`ersinkoc/phonebox`).
- **Edelsteine mit viel AI-Mithilfe.** 3 der 10 Edelsteine haben AI-Beteiligung an
  mehr als 70 % ihrer Commits. Mit dem ersten Abzug von bis zu 30 Punkten lagen sie auf
  den Rängen 188 bis 304 der Hauptliste und wären nie in eine Ausgabe gekommen. Das war
  faktisch ein Ausschluss. Am 12.11.2026 ist der Abzug deshalb auf 15 gesenkt worden.
  Sie liegen jetzt auf den Rängen 119 bis 235 von 421. Der Preis: 13 statt 5 der
  besten 100 Repos haben mehrheitlich AI-Commits, unter den besten 20 sind es 2.
- **„raus“ ist meist Geschmack.** 23 der 30 so beurteilten Repos schließt keine Regel
  aus: Emulatoren, Roblox, Begleit-Code zu Forschungsarbeiten, AI-Repos. Thematische
  Filter sind bewusst nicht vorgesehen. Ein möglicher Ausschluss wäre Begleit-Code zu
  Forschungsarbeiten.
- **Köder waren zuerst teils als „ok“ beurteilt.** Repos nach dem Muster „… desktop
  setup“ mit 1000 Sternen, ohne Forks und Issues, sind Köder für Schadsoftware. Neun
  solche Repos sind nachträglich als „slop“ markiert worden.
- **Echte Projekte ohne Echo.** Zwei als legitim geprüfte Repos (`799953468/frp-ban`,
  `guzhezao/parcel-shift`) haben 170 Sterne, aber weder Forks noch Issues. Sie bekommen
  denselben Abzug wie die Köder. Das ist am 12.11.2026 bewusst so entschieden: Solche
  Projekte müssen erst reifen. Sobald jemand sie forkt oder ein Issue schreibt,
  entfällt der Abzug.
- **Die Stichprobe ist jung.** Alle 880 Repos sind höchstens 11 Tage alt. `continuity`
  und der Bonus für neue Projekte sind daran nicht prüfbar.

## Noch nicht abgedeckt

Diese Regeln brauchen Daten, die wir noch nicht sammeln (siehe `datensammlung.md`,
„Geplant“):

- AI-Thema über Abhängigkeiten (`openai`, `langchain` in den Manifesten)
- Anweisungsdateien in Unterordnern (`.github/copilot-instructions.md`)
- „50 000 Zeilen in drei Tagen von einer Person“
- Community-Trends aus Hacker News und Lobste.rs laufen in eigenen Listen, nicht als
  positives Signal in der GitHub-Bewertung
