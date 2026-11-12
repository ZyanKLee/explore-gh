"""The owner's taste in platforms: Linux counts for a repo, Windows and Apple against it."""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import TermList, normalize, quoted

WINDOWS_PENALTY = 3.0
APPLE_PENALTY = 3.0
LINUX_BONUS = 6.0  # twice the others: a project for all three platforms comes out even

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
        return tuple(found)
