import pytest

from builders import make_snapshot
from github_anti_ai.domain.disliked_topics import DISLIKED_TOPICS, DislikedTopics


def signals(repo="alice/tiny-editor", **overrides):
    return DislikedTopics().signals(make_snapshot(repo, **overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "A native Linux Roblox Studio, written in Rust"},
        {"repo": "alice/Roblox-Account-Manager"},
        {"topics": ("roblox", "lua")},
    ],
)
def test_roblox_is_rated_down_heavily(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")
    [signal] = signals(repo, **overrides)

    assert signal.kind == "disliked_topic"
    assert signal.weight == -50
    assert "roblox" in signal.reason.lower()


def test_a_topic_named_in_several_places_is_rated_down_only_once():
    found = signals("alice/roblox-tools", description="Tools for Roblox", topics=("roblox",))

    assert len(found) == 1


def test_repo_without_a_disliked_topic_gets_no_signal():
    assert signals() == ()
    assert signals(description="Robloxian is not a word we look for") == ()


def test_every_disliked_topic_has_a_penalty():
    assert DISLIKED_TOPICS["roblox"] == 50
    assert all(penalty > 0 for penalty in DISLIKED_TOPICS.values())


def test_the_assessor_includes_disliked_topics_in_the_score():
    from github_anti_ai.domain.assessor import Assessor

    plain = Assessor().assess(make_snapshot())
    roblox = Assessor().assess(make_snapshot(topics=("editor", "terminal", "roblox")))

    assert roblox.score == pytest.approx(plain.score - 50)
