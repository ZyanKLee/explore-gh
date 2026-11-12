import json
from datetime import timedelta

import pytest

from builders import TODAY, make_edition, make_entry
from github_anti_ai.adapters.json_edition_store import JsonEditionStore
from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.edition import Edition, EditionStats
from github_anti_ai.domain.model import Section, Signal


def signalled_edition():
    signal = Signal(kind="ai_assistance", weight=-0.2, reason="CLAUDE.md im Hauptverzeichnis")
    return Edition(
        day=TODAY,
        main=(
            make_entry("alice/tiny-editor", score=0.83, gained=120, signals=(signal,)),
            make_entry("carol/plotter", language=None),
        ),
        ai=(make_entry("bob/agent-kit", section=Section.AI, language="Python"),),
        stats=EditionStats(assessed=1834, excluded=420, ai_focused=212),
    )


def test_saved_edition_is_loaded_unchanged(tmp_path):
    store = JsonEditionStore(tmp_path)
    edition = signalled_edition()

    store.save(edition)

    assert store.load(TODAY) == edition


def test_edition_is_stored_in_the_agreed_format(tmp_path):
    JsonEditionStore(tmp_path).save(signalled_edition())

    stored = json.loads((tmp_path / "2026-11-12.json").read_text())
    assert stored["format_version"] == 1
    assert stored["day"] == "2026-11-12"
    assert stored["stats"] == {"assessed": 1834, "excluded": 420, "ai_focused": 212}
    first = stored["sections"]["main"][0]
    assert first == {
        "rank": 1,
        "repo": "alice/tiny-editor",
        "url": "https://github.com/alice/tiny-editor",
        "description": "A tiny terminal text editor",
        "homepage": None,
        "language": "Rust",
        "topics": ["editor", "terminal"],
        "stars": 812,
        "stars_gained": 120,
        "star_history": [0] * 34 + [120],
        "created_at": "2026-10-20T12:00:00Z",
        "pushed_at": "2026-11-10T19:02:11Z",
        "license": "MIT",
        "forks": 31,
        "active_authors": 1,
        "score": 0.83,
        "signals": [
            {"kind": "ai_assistance", "weight": -0.2, "reason": "CLAUDE.md im Hauptverzeichnis"}
        ],
    }
    assert stored["sections"]["main"][1]["rank"] == 2
    assert stored["sections"]["ai"][0]["repo"] == "bob/agent-kit"


def test_edition_file_is_readable_for_humans(tmp_path):
    JsonEditionStore(tmp_path).save(signalled_edition())

    text = (tmp_path / "2026-11-12.json").read_text()
    assert "\n  " in text
    assert "Hauptverzeichnis" in text  # umlauts and the like stay readable, unescaped


def test_published_edition_cannot_be_overwritten(tmp_path):
    store = JsonEditionStore(tmp_path)
    store.save(make_edition(main=["alice/tiny-editor"]))

    with pytest.raises(AlreadyPublished):
        store.save(make_edition(main=["bob/rustbox"]))

    assert [str(e.repo) for e in store.load(TODAY).entries(Section.MAIN)] == ["alice/tiny-editor"]


def test_day_without_edition_loads_as_none(tmp_path):
    assert JsonEditionStore(tmp_path).load(TODAY) is None


def test_editions_since_a_day_are_listed_in_date_order(tmp_path):
    store = JsonEditionStore(tmp_path)
    for days_ago in (31, 2, 30, 0):
        store.save(make_edition(day=TODAY - timedelta(days=days_ago), main=[f"user{days_ago}/project"]))
    (tmp_path / "README.md").write_text("not an edition")

    editions = store.since(TODAY - timedelta(days=30))

    assert [e.day for e in editions] == [
        TODAY - timedelta(days=30),
        TODAY - timedelta(days=2),
        TODAY,
    ]


def test_store_directory_is_created_on_first_save(tmp_path):
    store = JsonEditionStore(tmp_path / "data" / "editions")

    store.save(make_edition(main=["alice/tiny-editor"]))

    assert store.load(TODAY) is not None
