"""The owner's taste: emulators of game consoles are rated down."""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import TermList, quoted

CONSOLE_EMULATOR_PENALTY = 50.0

EMULATOR_TERMS = TermList(
    ["emulator", "emulation", "recompilation", "recompiled", "recompiler", "recomp", "port"]
)
CONSOLE_TERMS = TermList(
    ["ps4", "ps5", "playstation", "switch2", "switch 2", "nintendo", "xbox"]
)


class ConsoleEmulatorCheck:
    def signal(self, snapshot: Snapshot) -> Signal | None:
        """Looks at name, description and topics. Both an emulator and a console must be named."""
        text = " . ".join([snapshot.repo.name, snapshot.description, *snapshot.topics])
        emulators = EMULATOR_TERMS.distinct(text)
        consoles = CONSOLE_TERMS.distinct(text)
        if not (emulators and consoles):
            return None
        return Signal(
            "console_emulator",
            -CONSOLE_EMULATOR_PENALTY,
            f"Emulator für Spielkonsolen ({quoted(emulators + consoles)})",
        )
