import pytest

from builders import make_snapshot
from github_anti_ai.domain.console_emulator import CONSOLE_EMULATOR_PENALTY, ConsoleEmulatorCheck


def signal(repo="alice/tiny-editor", **overrides):
    return ConsoleEmulatorCheck().signal(make_snapshot(repo, **overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "A PS5 emulator for the PS4"},
        {"description": "Guide to Nintendo Switch 2 emulator forks"},
        {"description": "Experimental Xbox emulator written in Rust"},
        {"topics": ("emulator", "switch2")},
        {"repo": "alice/nintendo-emulator"},
        {"description": "PS4 emulation on Linux"},
    ],
)
def test_an_emulator_for_a_game_console_is_rated_down(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")
    found = signal(repo, **overrides)

    assert found.kind == "console_emulator"
    assert found.weight == -CONSOLE_EMULATOR_PENALTY


def test_the_reason_names_emulator_and_console():
    reason = signal(description="A PS5 emulator for the PS4").reason

    assert "emulator" in reason
    assert "ps5" in reason


@pytest.mark.parametrize(
    "description",
    [
        "A terminal emulator with GPU rendering",
        "Emulate macOS on iOS and iPadOS",
        "Companion app for your Xbox controller",
        "Static recompilation of a Switch 2 game to native Windows",
    ],
)
def test_emulator_or_console_alone_is_no_reason(description):
    assert signal(description=description) is None


def test_the_assessor_includes_the_console_emulator_in_the_score():
    from github_anti_ai.domain.assessor import Assessor

    plain = Assessor().assess(make_snapshot(description="A terminal emulator"))
    console = Assessor().assess(make_snapshot(description="A PS4 emulator"))

    assert console.score == pytest.approx(plain.score - CONSOLE_EMULATOR_PENALTY)
