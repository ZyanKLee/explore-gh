import pytest
from builders import TODAY, make_snapshot
from fakes import InMemorySnapshotStore

from github_anti_ai.application.explain_assessment import ExplainAssessment, UnknownRepo
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.model import RepoId


def explain(name, *snapshots):
    store = InMemorySnapshotStore({TODAY: list(snapshots)})
    return ExplainAssessment(store, Assessor().assess).run(TODAY, RepoId.parse(name))


def test_names_section_score_exclusion_and_every_signal():
    text = explain("alice/tiny-editor", make_snapshot(owner_contributed_to=None))

    lines = text.splitlines()
    assert lines[0] == "alice/tiny-editor"
    assert lines[1] == "Sektion: Hauptliste"
    assert lines[2].startswith("Punktzahl: ")
    assert lines[3] == "Ausschluss: keiner"
    assert lines[4] == "Signale:"
    assert lines[5].endswith("+120 Sterne in 14 Tagen bei 812 insgesamt")


def test_shows_a_copy_among_the_repos_of_the_day():
    text = explain(
        "bob/player",
        make_snapshot("alice/player", description="Player"),
        make_snapshot("bob/player", description="Player"),
    )

    assert "Ausschluss: Kopie: 2 Repos" in text


def test_a_repo_without_snapshot_is_unknown():
    with pytest.raises(UnknownRepo, match="Keine Momentaufnahme von a/x"):
        explain("a/x", make_snapshot())
