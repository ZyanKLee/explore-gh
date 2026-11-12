# Bewertung (Bounded Context „Assessment“)

Noch nicht entworfen. Hier stehen die Vorgaben, die der Entwurf erfüllen muss.

## Vorgaben

- Ergebnis je Repo: `Assessment(snapshot, section, score, signals, exclusion)`,
  siehe `ausgabe.md`.
- Regelsystem ohne LLM. Jede Regel erzeugt ein `Signal` mit Begründung.
- Die Bedeutung von `score` und `weight` (Wertebereich, Verrechnung) wird hier
  festgelegt.
- Bei neuen Repos ist der relative Sterngewinn immer 100 %. Die Formel für den
  Aufstieg muss damit umgehen.
- Sterne sind käuflich. Der Aufstieg braucht Gegenproben (siehe geplante Daten in
  `datensammlung.md`).

## Regeln eichen

- **Beispielsammlung:** Der Projektinhaber beurteilt einmalig etwa 100 echte Repos aus
  einem Lauf (Edelstein, AI-Thema, Slop, egal). Die Regeln werden daran ausgerichtet.
  Tests mit diesen Beispielen verhindern, dass spätere Änderungen etwas verschlechtern.
- **Befehl `explain owner/name`:** zeigt für ein Repo alle Signale, die Punktzahl, die
  Sektion und einen etwaigen Ausschluss. Auch für Repos, die es nicht in die Ausgabe
  geschafft haben.

## Was als AI-Thema gilt

Entschieden am 12.11.2026:

- **AI-Thema** ist die Welle aus LLMs, Agenten und Chatbots samt allem, was nur für
  deren Einsatz gebaut ist: Agent-Frameworks, MCP-Server, Prompt- und Skill-Sammlungen,
  Erweiterungen für AI-Coding-Assistenten, Wrapper um Modell-APIs.
- **Ebenfalls AI-Thema** sind Generatoren für Bilder, Musik und Video.
- **Kein AI-Thema** ist klassisches maschinelles Lernen: Statistik-Bibliotheken,
  Bilderkennung, Trainings- und Rechen-Frameworks. Solche Repos gehören in die
  Hauptliste.
