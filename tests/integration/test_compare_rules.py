"""checks/compare_rules.py: what a change of the rules does to the stored snapshots."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("compare_rules", ROOT / "checks/compare_rules.py")
compare_rules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare_rules)
compare = compare_rules.compare


def repo(section="main", score=40.0, exclusion=None, reason=None, rank=None, signals=None):
    return {
        "section": section,
        "score": score,
        "exclusion": exclusion,
        "reason": reason,
        "rank": rank,
        "signals": signals if signals is not None else [["momentum", score, "…"]],
    }


def day(**repos):
    return {"2026-11-15": {name.replace("__", "/"): data for name, data in repos.items()}}


def test_the_same_assessments_show_no_differences():
    same = day(a__x=repo(rank=1))

    assert compare(same, same).splitlines()[-1] == "Keine Unterschiede."


def test_a_change_of_section_is_listed():
    report = compare(day(a__x=repo()), day(a__x=repo(section="ai")))

    assert "Sektion gewechselt: 1" in report
    assert "a/x  Hauptliste → AI-Sektion" in report


def test_new_and_lifted_exclusions_are_listed_with_their_reason():
    before = day(a__x=repo(), b__y=repo(exclusion="crypto", reason="Kryptowährungen („nft“)"))
    after = day(a__x=repo(exclusion="lure", reason="Köder für Schadsoftware"), b__y=repo())

    report = compare(before, after)

    assert "Neu ausgeschlossen: 1" in report
    assert "a/x  lure: Köder für Schadsoftware" in report
    assert "Nicht mehr ausgeschlossen: 1" in report
    assert "b/y  war crypto: Kryptowährungen („nft“)" in report


def test_another_reason_for_an_exclusion_is_listed():
    before = day(a__x=repo(exclusion="young", reason="jung"))
    after = day(a__x=repo(exclusion="copy", reason="Kopie"))

    assert "a/x  young → copy" in compare(before, after)


def test_score_changes_name_the_signals_that_changed_biggest_first():
    before = day(
        a__x=repo(score=40.0, signals=[["momentum", 40.0, "…"]]),
        b__y=repo(score=30.0, signals=[["momentum", 30.0, "…"], ["windows", -10.0, "…"]]),
    )
    after = day(
        a__x=repo(score=38.0, signals=[["momentum", 40.0, "…"], ["ai_files", -2.0, "…"]]),
        b__y=repo(score=20.0, signals=[["momentum", 30.0, "…"], ["windows", -20.0, "…"]]),
    )

    report = compare(before, after)

    assert "Punktzahl geändert: 2" in report
    assert report.index("b/y  30,0 → 20,0  (windows −10,0 → −20,0)") < report.index(
        "a/x  40,0 → 38,0  (ai_files – → −2,0)"
    )


def test_tiny_score_changes_do_not_count():
    assert compare(day(a__x=repo(score=40.0)), day(a__x=repo(score=40.004))).endswith(
        "Keine Unterschiede."
    )


def test_changes_of_the_edition_are_listed():
    before = day(a__x=repo(rank=3), b__y=repo(), c__z=repo(rank=1))
    after = day(a__x=repo(), b__y=repo(section="ai", rank=7), c__z=repo(rank=2))

    report = compare(before, after)

    assert "Neu in der Ausgabe: 1" in report
    assert "Nicht mehr in der Ausgabe: 1" in report
    assert "Anderer Platz in der Ausgabe: 1" in report
    assert report.index("Neu in der Ausgabe") < report.index("Sektion gewechselt")
    assert "+ b/y  AI-Sektion Platz 7" in report
    assert "− a/x  war Hauptliste Platz 3" in report
    assert "c/z  Hauptliste Platz 1 → 2" in report


def test_a_repo_shown_in_the_other_section_names_both():
    report = compare(day(a__x=repo(rank=2)), day(a__x=repo(section="ai", rank=5)))

    assert "a/x  Hauptliste Platz 2 → AI-Sektion Platz 5" in report


def test_long_lists_are_cut_after_show_lines():
    many = 15
    before = day(**{f"o{i}__r": repo() for i in range(many)})
    after = day(**{f"o{i}__r": repo(section="ai") for i in range(many)})

    report = compare(before, after, show=10)

    assert "Sektion gewechselt: 15" in report
    assert "… und 5 weitere" in report


def test_the_summary_counts_repos_and_days():
    report = compare(day(a__x=repo(), b__y=repo()), day(a__x=repo(section="ai"), b__y=repo()))

    assert report.splitlines()[-1] == "Insgesamt: 1 Repo mit Unterschieden an 1 Tag."


@pytest.mark.parametrize("day_text", ["2026-11-12"])
def test_assessing_the_labelled_examples_with_the_own_rules_gives_no_differences(day_text):
    snapshots = ROOT / "tests/integration/fixtures/labelled"

    result = compare_rules.assess_with(ROOT / "src", snapshots, [day_text])

    assert len(result[day_text]) == 102
    assert compare(result, result).endswith("Keine Unterschiede.")
