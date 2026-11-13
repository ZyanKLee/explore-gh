import json

import pytest

from github_anti_ai.publication.hn_view import load_hn_editions
from github_anti_ai.publication.lobsters_view import load_lobsters_editions


def write_edition(directory, license_id, **story):
    directory.mkdir()
    project = {
        "story": {
            "id": "abc", "title": "Tool", "url": "https://tool.example/", "comments": 1,
            "created_at": "2026-11-13T06:00:00+00:00", **story,
        },
        "repository_url": "https://github.com/a/tool",
        "project_url": "https://tool.example/",
        "description": "",
        "language": "Rust",
        "license_id": license_id,
        "is_fork": False,
        "is_archived": False,
        "has_code": True,
    }
    edition = {"format_version": 1, "day": "2026-11-13", "projects": [project]}
    (directory / "2026-11-13.json").write_text(json.dumps(edition), encoding="utf-8")
    return directory


@pytest.mark.parametrize(
    ("load", "story"),
    [
        (load_hn_editions, {"points": 10}),
        (load_lobsters_editions, {"score": 10, "discussion_url": "https://lobste.rs/s/abc"}),
    ],
)
@pytest.mark.parametrize(("license_id", "shown"), [("NOASSERTION", None), ("MIT", "MIT")])
def test_placeholder_for_an_unrecognized_license_is_not_shown_as_a_license(
    tmp_path, load, story, license_id, shown
):
    editions = load(write_edition(tmp_path / "editions", license_id, **story))

    assert editions[0].entries[0].license_id == shown
