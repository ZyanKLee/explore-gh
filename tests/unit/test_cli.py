from pathlib import Path

import pytest

from github_anti_ai.cli import MissingToken, load_token, main, parse_args


def test_the_data_directory_is_data_unless_chosen():
    assert parse_args(["collect"]).data_dir == Path("data")
    assert parse_args(["collect", "--data-dir", "data-test"]).data_dir == Path("data-test")


def test_collection_is_unlimited_unless_limited_for_trial_runs():
    assert parse_args(["collect"]).limit is None
    assert parse_args(["daily", "--limit", "60"]).limit == 60


@pytest.mark.parametrize("command", ["publish", "daily"])
def test_cooldown_completeness_and_review_are_on_off_and_off_by_default(command):
    args = parse_args([command])

    assert (args.ignore_cooldown, args.allow_incomplete, args.review) == (False, False, False)
    args = parse_args([command, "--ignore-cooldown", "--allow-incomplete", "--review"])
    assert (args.ignore_cooldown, args.allow_incomplete, args.review) == (True, True, True)


def test_publish_and_explain_take_a_day():
    assert str(parse_args(["publish", "--day", "2026-11-13"]).day) == "2026-11-13"
    assert parse_args(["explain", "a/x"]).day is None


def test_site_options():
    args = parse_args(["site"])
    assert (args.output, args.site_url, args.plausible) == (Path("output"), None, None)
    args = parse_args(
        ["site", "--output", "_site", "--site-url", "https://x/", "--plausible", "https://p/s.js"]
    )
    assert (args.output, args.site_url, args.plausible) == (
        Path("_site"),
        "https://x/",
        "https://p/s.js",
    )


def test_the_preview_runs_on_port_8000_unless_chosen():
    assert parse_args(["serve"]).port == 8000
    assert parse_args(["serve", "--port", "8080"]).port == 8080


@pytest.mark.parametrize("command", ["collect-hn", "collect-lobsters"])
def test_the_community_lists_have_their_own_commands(command):
    assert parse_args([command, "--limit", "5"]).limit == 5


class TestToken:
    def test_the_environment_comes_first(self, tmp_path):
        (tmp_path / ".env").write_text("GITHUB_TOKEN=from-file\n")

        assert load_token({"GITHUB_TOKEN": " from-env "}, tmp_path / ".env") == "from-env"

    @pytest.mark.parametrize(
        "line", ["GITHUB_TOKEN=abc", 'GITHUB_TOKEN="abc"', "GITHUB_TOKEN = 'abc' "]
    )
    def test_otherwise_the_env_file_also_quoted(self, tmp_path, line):
        (tmp_path / ".env").write_text(f"OTHER=1\n{line}\n")

        assert load_token({}, tmp_path / ".env") == "abc"

    def test_a_missing_token_is_reported(self, tmp_path):
        with pytest.raises(MissingToken, match="GITHUB_TOKEN fehlt"):
            load_token({}, tmp_path / ".env")


def test_explain_reports_a_repo_without_snapshot(tmp_path, capsys):
    code = main(["explain", "a/x", "--data-dir", str(tmp_path), "--day", "2026-11-12"])

    assert code == 1
    assert "Keine Momentaufnahme von a/x am 2026-11-12" in capsys.readouterr().err


def test_publish_without_snapshots_says_so(tmp_path, capsys):
    code = main(["publish", "--data-dir", str(tmp_path), "--day", "2026-11-12"])

    assert code == 1
    assert "keine Momentaufnahmen" in capsys.readouterr().err


def test_site_builds_into_the_output_directory(tmp_path, capsys):
    code = main(["site", "--data-dir", str(tmp_path / "data"), "--output", str(tmp_path / "out")])

    assert code == 0
    assert (tmp_path / "out" / "index.html").exists()
