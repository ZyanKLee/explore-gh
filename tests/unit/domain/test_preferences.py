import pytest
from builders import make_snapshot

from explore_gh.domain.preferences import (
    ConsoleEmulatorCheck,
    DislikedTopics,
    PlatformPreference,
)


def platform(**overrides):
    return {s.kind: s for s in PlatformPreference().signals(make_snapshot(**overrides))}


class TestPlatformPreference:
    def test_windows_costs_10_points(self):
        signal = platform(description="A tray tool for Windows 11")["windows"]

        assert (signal.weight, signal.reason) == (-10, "Für Windows („windows“)")

    def test_macos_and_ios_together_cost_10_points_once(self):
        signals = platform(description="Notes for macOS and iOS")

        assert signals["apple"].weight == -10
        assert signals["apple"].reason == "Für macOS oder iOS („macos“, „ios“)"

    def test_linux_gives_20_points(self):
        assert platform(topics=("wayland",))["linux"].weight == 20

    def test_linux_lifts_the_penalties(self):
        assert set(platform(description="For Windows, macOS and Linux")) == {"linux"}

    @pytest.mark.parametrize(
        "description", ["Change your MAC address", "An Apple TV-style launcher for Android"]
    )
    def test_a_mac_address_or_an_apple_look_is_no_platform(self, description):
        assert platform(description=description) == {}

    def test_the_readme_does_not_count(self):
        assert platform(readme="Install on Windows, macOS or Linux.") == {}


class TestConsoleEmulatorCheck:
    def test_an_emulator_for_a_console_costs_50_points(self):
        (signal,) = ConsoleEmulatorCheck().signals(
            make_snapshot(description="A Nintendo Switch 2 emulator")
        )

        assert signal.kind == "console_emulator"
        assert signal.weight == -50
        assert signal.reason == "Emulator für Spielkonsolen („emulator“, „nintendo“, „switch 2“)"

    def test_a_port_for_a_console_counts_as_well(self):
        assert ConsoleEmulatorCheck().signals(make_snapshot(description="PS3 port of the game"))

    @pytest.mark.parametrize("description", ["A terminal emulator", "Remap your Xbox controller"])
    def test_an_emulator_or_a_console_alone_costs_nothing(self, description):
        assert ConsoleEmulatorCheck().signals(make_snapshot(description=description)) == ()


class TestDislikedTopics:
    def test_roblox_costs_50_points(self):
        (signal,) = DislikedTopics().signals(make_snapshot(topics=("roblox",)))

        assert (signal.kind, signal.weight) == ("disliked_topic", -50)
        assert signal.reason == "Unerwünschtes Thema: „roblox“"

    def test_other_topics_cost_nothing(self):
        assert DislikedTopics().signals(make_snapshot()) == ()
