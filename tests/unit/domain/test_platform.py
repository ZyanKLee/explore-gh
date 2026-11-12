import pytest

from builders import make_snapshot
from github_anti_ai.domain.platform import (
    APPLE_PENALTY,
    LINUX_BONUS,
    WINDOWS_PENALTY,
    PlatformPreference,
)


def signals(repo="alice/tiny-editor", **overrides):
    return PlatformPreference().signals(make_snapshot(repo, **overrides))


def weights(repo="alice/tiny-editor", **overrides):
    return {s.kind: s.weight for s in signals(repo, **overrides)}


def test_repo_that_names_no_platform_gets_no_signal():
    assert signals() == ()


def test_a_windows_project_is_rated_down():
    [signal] = signals(description="A taskbar music player for Windows 11")

    assert signal.kind == "windows"
    assert signal.weight == -WINDOWS_PENALTY
    assert "Windows" in signal.reason


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "A menu bar app for macOS"},
        {"description": "Sandbox escape for iOS 27"},
        {"description": "Notes for iPhone and iPad"},
        {"topics": ("swift", "ipados")},
        {"repo": "alice/mac-cleaner"},
    ],
)
def test_a_project_for_macos_or_ios_is_rated_down(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")

    assert weights(repo, **overrides) == {"apple": -APPLE_PENALTY}


def test_macos_and_ios_together_are_rated_down_only_once():
    assert weights(description="One app for macOS, iOS and iPadOS") == {"apple": -APPLE_PENALTY}


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "A native Linux audio mixer"},
        {"topics": ("wayland", "rust")},
        {"description": "Status bar for Hyprland"},
        {"repo": "alice/nixos-installer"},
    ],
)
def test_a_linux_project_is_rated_up(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")
    [signal] = signals(repo, **overrides)

    assert signal.kind == "linux"
    assert signal.weight == LINUX_BONUS
    assert "Linux" in signal.reason


def test_linux_counts_twice_as_much_as_windows_or_apple():
    assert LINUX_BONUS == 2 * WINDOWS_PENALTY == 2 * APPLE_PENALTY


def test_a_project_for_all_three_platforms_comes_out_even():
    found = weights(description="A container runtime for macOS, Windows and Linux")

    assert set(found) == {"windows", "apple", "linux"}
    assert sum(found.values()) == 0


def test_platforms_named_only_in_the_readme_do_not_count():
    # install instructions name every platform, that says nothing about the project
    readme = "# tiny-editor\n\nInstall on Windows, macOS or Linux.\n"

    assert signals(readme=readme) == ()


@pytest.mark.parametrize(
    "description",
    [
        "Looks up the vendor of a MAC address",
        "A tool for studios and bios chips",
        "Rewinds the sliding windowsill sensor log",
    ],
)
def test_words_that_only_look_like_a_platform_do_not_count(description):
    assert signals(description=description) == ()


def test_the_assessor_includes_the_platform_in_the_score():
    from github_anti_ai.domain.assessor import Assessor

    plain = Assessor().assess(make_snapshot())
    linux = Assessor().assess(make_snapshot(description="A tiny terminal text editor for Linux"))

    assert linux.score == pytest.approx(plain.score + LINUX_BONUS)
