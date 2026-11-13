"""The rules against 102 real repos the project owner judged by hand on 2026-11-12.

The fixture is built by checks/make_labelled_examples.py. A change of the rules must not
make them agree less with these verdicts. If it makes them agree more, raise the numbers.
"""

import csv
from datetime import date
from pathlib import Path
from statistics import median

import pytest

from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.model import RepoId, Section

FIXTURES = Path(__file__).parent / "fixtures" / "labelled"
# Of 102. It was 88 until "agent" became an AI term on 2026-11-13: the owner accepted
# that TechTideOhio/binnacle ("The Evaluator Agent") moves to the AI section for it.
MIN_AI_FOCUS_AGREEMENT = 87
MIN_SLOP_EXCLUDED = 13  # of 18


@pytest.fixture(scope="module")
def judged():
    """Pairs of the owner's verdict and the Assessment of the rules."""
    with (FIXTURES / "urteile.csv").open(newline="") as file:
        verdicts = {RepoId.parse(row["repo"]): row for row in csv.DictReader(file)}
    snapshots = JsonSnapshotStore(FIXTURES).load(date(2026, 11, 12))
    assert len(snapshots) == len(verdicts) == 102
    assessor = Assessor()
    return [(verdicts[snapshot.repo], assessor.assess(snapshot)) for snapshot in snapshots]


def scores(judged, verdict):
    return [a.score for row, a in judged if row["urteil"] == verdict and a.exclusion is None]


def test_ai_focus_agrees_with_the_owner_as_often_as_before(judged):
    agreed = sum((row["ai_thema"] == "ja") == (a.section is Section.AI) for row, a in judged)

    assert agreed >= MIN_AI_FOCUS_AGREEMENT


def test_most_slop_is_excluded(judged):
    slop = [a for row, a in judged if row["urteil"] == "slop"]
    excluded = [a for a in slop if a.exclusion is not None]

    assert len(slop) == 18
    assert len(excluded) >= MIN_SLOP_EXCLUDED


def test_every_lure_for_malware_the_owner_marked_is_excluded_or_far_behind(judged):
    typical_gem = median(scores(judged, "edelstein"))
    for row, a in judged:
        if row["urteil"] == "slop" and any(s.kind in ("no_echo", "fork_farm") for s in a.signals):
            assert a.exclusion is not None or a.score < typical_gem - 30, a.repo


def test_no_gem_is_excluded_as_a_lure(judged):
    for row, a in judged:
        if row["urteil"] in ("edelstein", "ok"):
            assert a.exclusion is None or a.exclusion.kind != "lure", a.repo


def test_slop_that_stays_scores_lower_than_gems(judged):
    assert median(scores(judged, "edelstein")) > median(scores(judged, "slop"))


def test_no_repo_judged_as_slop_reaches_the_score_of_the_best_gems(judged):
    best_gems = sorted(scores(judged, "edelstein"))[-3:]

    assert max(scores(judged, "slop")) < min(best_gems)


def test_stars_without_echo_never_reach_the_score_of_a_typical_gem(judged):
    lures = [a.score for _, a in judged if any(s.kind == "no_echo" for s in a.signals)]

    assert len(lures) >= 10
    assert max(lures) < median(scores(judged, "edelstein"))


def test_fixture_holds_no_names_or_addresses_of_people(judged):
    for _, assessment in judged:
        for commit in assessment.snapshot.recent_commits:
            assert commit.headline == ""
            for co_author in commit.co_authors:
                assert "users.noreply.github.com" in co_author or co_author.endswith(
                    ("@anthropic.com>", "@openai.com>", "@cursor.com>", "@example.org>")
                ), co_author
