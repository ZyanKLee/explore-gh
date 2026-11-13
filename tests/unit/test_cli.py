from pathlib import Path

import pytest

from github_anti_ai.cli import MissingToken, load_token, parse_args


def test_publish_respects_the_cooldown_by_default():
    assert parse_args(["publish"]).ignore_cooldown is False


@pytest.mark.parametrize("command", ["publish", "daily"])
def test_cooldown_can_be_ignored_from_the_command_line(command):
    assert parse_args([command, "--ignore-cooldown"]).ignore_cooldown is True


def test_collect_has_no_cooldown_flag():
    with pytest.raises(SystemExit):
        parse_args(["collect", "--ignore-cooldown"])


def test_collection_is_unlimited_by_default():
    assert parse_args(["collect"]).limit is None


@pytest.mark.parametrize("command", ["collect", "daily"])
def test_number_of_candidates_can_be_limited_for_trial_runs(command):
    assert parse_args([command, "--limit", "40"]).limit == 40


def test_assessment_of_a_repo_can_be_explained():
    args = parse_args(["explain", "alice/tiny-editor"])

    assert args.command == "explain"
    assert args.repo == "alice/tiny-editor"


def test_site_is_built_into_the_output_directory_by_default():
    args = parse_args(["site"])

    assert args.command == "site"
    assert args.output == Path("output")
    assert args.data_dir == Path("data")


def test_output_directory_of_the_site_can_be_chosen():
    assert parse_args(["site", "--output", "/tmp/site"]).output == Path("/tmp/site")


def test_data_directory_defaults_to_data():
    assert parse_args(["collect"]).data_dir == Path("data")


def test_data_directory_can_be_chosen_for_experiments():
    assert parse_args(["publish", "--data-dir", "/tmp/try"]).data_dir == Path("/tmp/try")


def test_token_is_taken_from_the_environment(tmp_path):
    (tmp_path / ".env").write_text("GITHUB_TOKEN=from_file\n")

    assert load_token({"GITHUB_TOKEN": "from_env"}, tmp_path / ".env") == "from_env"


def test_token_is_read_from_env_file_otherwise(tmp_path):
    (tmp_path / ".env").write_text("# GitHub\nOTHER=1\nGITHUB_TOKEN = from_file \n")

    assert load_token({}, tmp_path / ".env") == "from_file"


def test_missing_token_is_reported_without_revealing_anything(tmp_path):
    with pytest.raises(MissingToken) as error:
        load_token({}, tmp_path / ".env")

    assert "GITHUB_TOKEN" in str(error.value)


def test_token_in_env_file_may_be_quoted(tmp_path):
    (tmp_path / ".env").write_text('GITHUB_TOKEN="from_file"\n')

    assert load_token({}, tmp_path / ".env") == "from_file"


def test_publish_refuses_an_incomplete_collection_by_default():
    assert parse_args(["publish"]).allow_incomplete is False


@pytest.mark.parametrize("command", ["publish", "daily"])
def test_incomplete_collection_can_be_allowed_from_the_command_line(command):
    assert parse_args([command, "--allow-incomplete"]).allow_incomplete is True


def test_site_has_no_address_by_default():
    assert parse_args(["site"]).site_url is None


def test_address_of_the_site_can_be_given_for_the_feeds():
    args = parse_args(["site", "--site-url", "https://example.org/fundstuecke/"])

    assert args.site_url == "https://example.org/fundstuecke/"


def test_preview_is_served_on_port_8000_by_default():
    args = parse_args(["serve"])

    assert args.command == "serve"
    assert args.port == 8000
    assert args.output == Path("output")
    assert args.data_dir == Path("data")


def test_port_of_the_preview_can_be_chosen():
    assert parse_args(["serve", "--port", "8080"]).port == 8080


def test_site_counts_no_visits_by_default():
    assert parse_args(["site"]).plausible is None


def test_plausible_script_can_be_given_for_the_published_site():
    args = parse_args(["site", "--plausible", "https://stats.example.org/js/pa-test.js"])

    assert args.plausible == "https://stats.example.org/js/pa-test.js"
