"""The owner's taste: platforms, emulators of game consoles and disliked topics.

All three look at name, description and topics only. A README names every platform it
installs on and every console a project merely mentions. See docs/bewertung.md.
"""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import TermList, labels, quoted

WINDOWS_PENALTY = 10.0
APPLE_PENALTY = 10.0
LINUX_BONUS = 20.0

WINDOWS_TERMS = TermList(["windows", "win32", "win10", "win11", "winui", "wpf"])
APPLE_TERMS = TermList(
    [
        "macos",
        "mac",
        "osx",
        "os x",
        "ios",
        "ipados",
        "iphone",
        "ipad",
        "watchos",
        "tvos",
        "visionos",
        "apple silicon",
        "apple",
        "icloud",
    ],
    # "Apple TV-style" describes a look, not the platform a project runs on
    unless_in=["mac address", "apple tv style", "apple style"],
)
LINUX_TERMS = TermList(
    [
        "linux",
        "wayland",
        "gnome",
        "kde",
        "systemd",
        "ubuntu",
        "debian",
        "fedora",
        "archlinux",
        "arch linux",
        "nixos",
        "hyprland",
    ]
)

CONSOLE_EMULATOR_PENALTY = 50.0
EMULATOR_TERMS = TermList(
    [
        "emulator",
        "emulation",
        "recompilation",
        "recompiled",
        "recompiler",
        "recomp",
        "port",
        "ported",
        "porting",
        "compatibility layer",
    ]
)
CONSOLE_TERMS = TermList(
    [
        "ps1",
        "ps2",
        "ps3",
        "ps4",
        "ps5",
        "psx",
        "psp",
        "ps vita",
        "psvita",
        "playstation",
        "switch2",
        "switch 2",
        "switch game",  # "switch" alone is too often a network switch or a toggle
        "nintendo",
        "n64",
        "gamecube",
        "wii",
        "wii u",
        "3ds",
        "xbox",
        "dreamcast",
    ]
)

# term -> points taken off. A new line here is all a new topic needs.
DISLIKED_TOPICS = {
    "roblox": 50.0,
}


def _labels(snapshot: Snapshot) -> str:
    return labels(snapshot.repo.name, snapshot.description, snapshot.topics)


class PlatformPreference:
    """Linux counts for a repo, Windows and Apple against it, unless it serves Linux too."""

    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        text = _labels(snapshot)
        found = []
        for kind, label, terms, weight in [
            ("windows", "Für Windows", WINDOWS_TERMS, -WINDOWS_PENALTY),
            ("apple", "Für macOS oder iOS", APPLE_TERMS, -APPLE_PENALTY),
            ("linux", "Für Linux", LINUX_TERMS, LINUX_BONUS),
        ]:
            if names := terms.distinct(text):
                found.append(Signal(kind, weight, f"{label} ({quoted(names)})"))
        if any(signal.kind == "linux" for signal in found):
            found = [signal for signal in found if signal.kind == "linux"]
        return tuple(found)


class ConsoleEmulatorCheck:
    """Emulators and ports for game consoles. Both an emulator and a console must be named."""

    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        text = _labels(snapshot)
        emulators = EMULATOR_TERMS.distinct(text)
        consoles = CONSOLE_TERMS.distinct(text)
        if not (emulators and consoles):
            return ()
        return (
            Signal(
                "console_emulator",
                -CONSOLE_EMULATOR_PENALTY,
                f"Emulator für Spielkonsolen ({quoted(emulators + consoles)})",
            ),
        )


class DislikedTopics:
    """One signal per disliked topic the repo names."""

    def __init__(self):
        self._terms = {topic: TermList([topic]) for topic in DISLIKED_TOPICS}

    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        text = _labels(snapshot)
        return tuple(
            Signal("disliked_topic", -DISLIKED_TOPICS[topic], f"Unerwünschtes Thema: „{topic}“")
            for topic, terms in self._terms.items()
            if terms.find(text)
        )
