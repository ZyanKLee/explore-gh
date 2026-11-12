import pytest

from github_anti_ai.domain.model import RepoId


def test_repo_id_is_parsed_from_owner_and_name():
    repo = RepoId.parse("alice/tiny-editor")

    assert repo.owner == "alice"
    assert repo.name == "tiny-editor"


def test_repo_id_renders_as_owner_slash_name():
    assert str(RepoId.parse("alice/tiny-editor")) == "alice/tiny-editor"


def test_repo_ids_differing_only_in_case_are_the_same_repo():
    # GitHub ignores case, and different sources spell names differently
    upper = RepoId.parse("Alice/Tiny-Editor")
    lower = RepoId.parse("alice/tiny-editor")

    assert upper == lower
    assert len({upper, lower}) == 1


def test_repo_id_keeps_its_original_spelling_for_display():
    assert str(RepoId.parse("Alice/Tiny-Editor")) == "Alice/Tiny-Editor"


def test_repo_id_knows_its_github_url():
    assert RepoId.parse("alice/tiny-editor").url == "https://github.com/alice/tiny-editor"


@pytest.mark.parametrize(
    "text",
    ["", "alice", "alice/", "/tiny-editor", "alice/tiny/editor", "alice tiny/editor"],
)
def test_malformed_repo_id_is_rejected(text):
    with pytest.raises(ValueError):
        RepoId.parse(text)
