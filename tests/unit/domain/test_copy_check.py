from datetime import UTC, datetime, timedelta

from builders import make_snapshot
from github_anti_ai.domain.copies import COPY_ORIGINAL_MIN_LEAD, CopyCheck
from github_anti_ai.domain.model import Assessment, Exclusion, RepoId, Section

CREATED = datetime(2026, 11, 14, 19, 15, tzinfo=UTC)
DESCRIPTION = "A powerful, intuitive IPTV streaming app"


def copy(repo, *, created_at=CREATED, description=DESCRIPTION, **overrides):
    return make_snapshot(repo, created_at=created_at, description=description, **overrides)


def find(*snapshots):
    return {str(repo): exclusion for repo, exclusion in CopyCheck().find(snapshots).items()}


def test_copies_created_at_almost_the_same_time_are_all_excluded():
    found = find(
        copy("warrior/IPTV_Player"),
        copy("tornado/IPTV_Player", created_at=CREATED + timedelta(minutes=10)),
        copy("watt/IPTV_Player", created_at=CREATED + timedelta(minutes=10)),
    )

    assert set(found) == {"warrior/IPTV_Player", "tornado/IPTV_Player", "watt/IPTV_Player"}
    assert all(exclusion.kind == "copy" for exclusion in found.values())
    assert found["warrior/IPTV_Player"].reason == (
        "Kopie: 3 Repos mit gleichem Namen und gleicher Beschreibung, "
        "fast gleichzeitig angelegt"
    )


def test_a_clearly_older_repo_stays_as_the_original_and_only_its_copies_are_excluded():
    found = find(
        copy("alice/IPTV_Player", created_at=CREATED - COPY_ORIGINAL_MIN_LEAD),
        copy("tornado/IPTV_Player"),
        copy("watt/IPTV_Player", created_at=CREATED + timedelta(minutes=10)),
    )

    assert set(found) == {"tornado/IPTV_Player", "watt/IPTV_Player"}
    assert found["tornado/IPTV_Player"] == Exclusion("Kopie von alice/IPTV_Player", "copy")


def test_a_repo_that_is_not_older_by_enough_is_no_original():
    found = find(
        copy("alice/IPTV_Player", created_at=CREATED - COPY_ORIGINAL_MIN_LEAD + timedelta(hours=1)),
        copy("tornado/IPTV_Player"),
    )

    assert set(found) == {"alice/IPTV_Player", "tornado/IPTV_Player"}


def test_same_name_with_another_description_is_no_copy():
    assert not find(
        copy("alice/editor", description="A tiny terminal text editor"),
        copy("bob/editor", description="Editor for hex files"),
    )


def test_same_description_with_another_name_is_no_copy():
    assert not find(copy("alice/IPTV_Player"), copy("bob/tv-streamer"))


def test_name_and_description_compare_without_case_and_spacing():
    found = find(
        copy("alice/IPTV_Player", description="A powerful  IPTV app "),
        copy("bob/iptv_player", description="a powerful iptv app"),
    )

    assert set(found) == {"alice/IPTV_Player", "bob/iptv_player"}


def test_repos_without_description_are_no_copies():
    assert not find(copy("alice/demo", description=""), copy("bob/demo", description=" "))


def test_a_fork_does_not_make_the_original_a_copy():
    assert not find(copy("alice/IPTV_Player"), copy("bob/IPTV_Player", is_fork=True))


def assessment(snapshot, exclusion=None):
    return Assessment(
        snapshot=snapshot, section=Section.MAIN, score=1.0, signals=(), exclusion=exclusion
    )


def test_apply_excludes_the_copies_among_the_assessments():
    lone = assessment(make_snapshot("alice/tiny-editor"))
    applied = CopyCheck().apply(
        [lone, assessment(copy("tornado/IPTV_Player")), assessment(copy("watt/IPTV_Player"))]
    )

    assert applied[0] is lone
    assert [a.exclusion.kind for a in applied[1:]] == ["copy", "copy"]
    assert applied[1].repo == RepoId.parse("tornado/IPTV_Player")


def test_apply_keeps_an_earlier_exclusion():
    lure = Exclusion("Köder für Schadsoftware („full version“)", "lure")
    applied = CopyCheck().apply(
        [assessment(copy("tornado/IPTV_Player"), lure), assessment(copy("watt/IPTV_Player"))]
    )

    assert applied[0].exclusion == lure
    assert applied[1].exclusion.kind == "copy"
