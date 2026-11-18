from datetime import timedelta

from builders import NOW, make_assessment, make_snapshot

from explore_gh.domain.copies import CopyCheck
from explore_gh.domain.model import Exclusion, RepoId

check = CopyCheck()
LONG_README = "# IPTV Player\n\n" + "Watch your playlists on any screen. " * 20


def copies(*snapshots):
    return {str(repo): exclusion for repo, exclusion in check.find(snapshots).items()}


def test_the_same_name_and_description_under_two_owners_are_copies():
    found = copies(
        make_snapshot("alice/player", description="IPTV Player 2.0"),
        make_snapshot("bob/player", description="iptv  player 2.0"),
    )

    assert set(found) == {"alice/player", "bob/player"}
    assert found["bob/player"] == Exclusion(
        "Kopie: 2 Repos mit gleichem Namen und gleicher Beschreibung, fast gleichzeitig angelegt",
        "copy",
    )


def test_the_same_description_and_topics_catch_a_changed_name():
    found = copies(
        make_snapshot("alice/IPTV_Player_2.0", description="Player", topics=("iptv", "tv")),
        make_snapshot("bob/IPTV_Player2.0", description="Player", topics=("tv", "iptv")),
    )

    assert "gleicher Beschreibung und gleichen Topics" in found["alice/IPTV_Player_2.0"].reason


def test_the_same_long_readme_makes_copies():
    found = copies(
        make_snapshot("alice/one", readme=LONG_README),
        make_snapshot("bob/two", readme=LONG_README),
    )

    assert "gleichem README" in found["bob/two"].reason


def test_a_short_readme_in_common_proves_nothing():
    assert (
        copies(
            make_snapshot("alice/one", readme="# TODO"), make_snapshot("bob/two", readme="# TODO")
        )
        == {}
    )


def test_the_same_description_alone_makes_no_copies():
    assert (
        copies(
            make_snapshot("alice/one", description="Switch 2 emulator", topics=("a",)),
            make_snapshot("bob/two", description="Switch 2 emulator", topics=("b",)),
        )
        == {}
    )


def test_repos_of_the_same_owner_are_no_copies():
    assert (
        copies(
            make_snapshot("alice/player", description="Player"),
            make_snapshot("Alice/Player", description="Player"),
        )
        == {}
    )


def test_repos_without_description_or_topics_are_not_compared_by_them():
    assert (
        copies(
            make_snapshot("alice/player", description="", topics=()),
            make_snapshot("bob/player", description="", topics=()),
        )
        == {}
    )


def test_forks_are_left_out():
    assert (
        copies(
            make_snapshot("alice/player", description="Player"),
            make_snapshot("bob/player", description="Player", is_fork=True),
        )
        == {}
    )


def test_a_repo_a_week_older_stays_as_the_original():
    found = copies(
        make_snapshot("alice/player", description="Player", created_at=NOW - timedelta(days=30)),
        make_snapshot("bob/player", description="Player", created_at=NOW - timedelta(days=23)),
        make_snapshot("carol/player", description="Player", created_at=NOW - timedelta(days=22)),
    )

    assert set(found) == {"bob/player", "carol/player"}
    assert found["bob/player"] == Exclusion("Kopie von alice/player", "copy")


def test_apply_excludes_copies_but_keeps_an_earlier_reason():
    assessments = [
        make_assessment("alice/player", description="Player"),
        make_assessment(
            "bob/player", description="Player", exclusion=Exclusion("Archiviert", "archived")
        ),
        make_assessment("carol/editor"),
    ]

    applied = {str(a.repo): a.exclusion for a in check.apply(assessments)}

    assert applied["alice/player"].kind == "copy"
    assert applied["bob/player"].kind == "archived"
    assert applied["carol/editor"] is None


def test_find_returns_repo_ids():
    found = check.find(
        [make_snapshot("alice/p", description="P"), make_snapshot("bob/p", description="P")]
    )

    assert RepoId.parse("ALICE/P") in found
