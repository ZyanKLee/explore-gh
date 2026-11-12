"""The owner's taste in platforms: Linux counts for a repo, Windows and Apple against it.

A project that serves Linux too is not rated down for the other platforms.
"""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import TermList, normalize, quoted

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
    ]
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
_NOT_A_PLATFORM = ["mac address"]


class PlatformPreference:
    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        """Looks at name, description and topics. A README names every platform it installs on."""
        text = normalize(" . ".join([snapshot.repo.name, snapshot.description, *snapshot.topics]))
        for phrase in _NOT_A_PLATFORM:
            text = text.replace(phrase, " ")
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
