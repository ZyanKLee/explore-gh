import pytest

from builders import TODAY, make_snapshot
from fakes import InMemorySnapshotStore
from github_anti_ai.application.explain_assessment import ExplainAssessment, UnknownRepo
from github_anti_ai.domain.model import Assessment, Exclusion, RepoId, Section, Signal

SIGNALS = (
    Signal(kind="momentum", weight=40.0, reason="+100 Sterne in 7 Tagen bei 100 insgesamt"),
    Signal(kind="ai_files", weight=-3.0, reason="Anweisungsdateien für AI-Agenten: AGENTS.md"),
    Signal(kind="ai_focus", weight=0, reason="Beschreibung nennt „LLM“"),
)


def explain(repo="alice/tiny-editor", *, section=Section.MAIN, exclusion=None, snapshots=None):
    def assess(snapshot):
        return Assessment(
            snapshot=snapshot, section=section, score=37.0, signals=SIGNALS, exclusion=exclusion
        )

    store = InMemorySnapshotStore(
        {TODAY: snapshots if snapshots is not None else [make_snapshot("alice/tiny-editor")]}
    )
    return ExplainAssessment(snapshot_store=store, assess=assess).run(TODAY, RepoId.parse(repo))


def test_explanation_names_repo_section_and_score():
    text = explain()

    assert "alice/tiny-editor" in text
    assert "Hauptliste" in text
    assert "37.0" in text


def test_explanation_names_the_ai_section():
    assert "AI-Sektion" in explain(section=Section.AI)


def test_explanation_lists_every_signal_with_weight_and_reason():
    text = explain()

    for line in (
        "+40.0  +100 Sterne in 7 Tagen bei 100 insgesamt",
        "-3.0  Anweisungsdateien für AI-Agenten: AGENTS.md",
        "0.0  Beschreibung nennt „LLM“",
    ):
        assert line in text


def test_explanation_states_an_exclusion():
    text = explain(exclusion=Exclusion(reason="Fork", kind="fork"))

    assert "Ausschluss: Fork" in text


def test_explanation_says_when_nothing_excludes_the_repo():
    assert "Ausschluss: keiner" in explain()


def test_repo_is_found_regardless_of_case():
    assert "alice/tiny-editor" in explain("Alice/Tiny-Editor")


def test_repo_without_snapshot_of_the_day_is_reported_as_unknown():
    with pytest.raises(UnknownRepo):
        explain("bob/rustbox")
