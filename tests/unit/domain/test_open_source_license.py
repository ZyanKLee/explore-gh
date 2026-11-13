from github_anti_ai.domain.opensource import UNRECOGNIZED_LICENSE, is_open_source_license


def test_license_from_the_allowlist_counts_as_open_source():
    assert is_open_source_license("MIT")


def test_license_file_that_the_forge_cannot_identify_counts_as_open_source():
    # GitHub reports NOASSERTION for dual licenses or modified license texts
    assert UNRECOGNIZED_LICENSE == "NOASSERTION"
    assert is_open_source_license("NOASSERTION")


def test_repo_without_license_file_is_not_open_source():
    assert not is_open_source_license(None)


def test_license_outside_the_allowlist_is_not_open_source():
    assert not is_open_source_license("BUSL-1.1")
