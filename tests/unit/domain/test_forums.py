"""The weekly forums list: several origins, ranked by the multiple of their threshold."""

from datetime import date

from builders import TODAY, make_project, make_story

from github_anti_ai.domain.community import (
    FORUMS,
    HN,
    CommunityCurator,
    Origin,
    edition_day,
)

LOBSTERS_ORIGIN = Origin("Lobsters", reference_points=10, min_points=10)
LEMMY_RUST = Origin("Lemmy c/rust", reference_points=15, min_points=15)
MASTODON_RUST = Origin(
    "Mastodon #rust", reference_points=5, min_points=0, points_label="Reaktionen"
)


def project(name, origin, points, comments=3, language=None, **overrides):
    story = make_story(name, platform=FORUMS, origin=origin, points=points, comments=comments)
    return make_project(
        f"https://github.com/{name}",
        story=story,
        description=f"A tool called {name}",
        language=language or "Rust",
        **overrides,
    )


def curate(*candidates):
    return CommunityCurator().curate(FORUMS, TODAY, candidates)


def urls(projects):
    return [p.repository_url for p in projects]


def test_the_multiple_of_the_threshold_decides_the_rank_across_origins():
    edition = curate(
        project("a/lemmy", LEMMY_RUST, points=45, language="Go"),
        project("b/lobsters", LOBSTERS_ORIGIN, points=34),
    )

    assert urls(edition.main) == ["https://github.com/b/lobsters", "https://github.com/a/lemmy"]


def test_the_reason_names_points_origin_and_multiple():
    (chosen,) = curate(project("a/x", LOBSTERS_ORIGIN, points=34)).main

    assert "34 Punkte auf Lobsters, das 3,4-Fache der Schwelle von 10." in chosen.reasons


def test_a_story_below_the_threshold_of_its_origin_is_left_out():
    assert curate(project("a/x", LEMMY_RUST, points=14)).main == ()


def test_a_story_on_the_threshold_of_its_origin_stays():
    assert len(curate(project("a/x", LEMMY_RUST, points=15)).main) == 1


def test_mastodon_has_no_threshold_for_now():
    (chosen,) = curate(project("a/x", MASTODON_RUST, points=0)).main

    assert (
        "0 Reaktionen auf Mastodon #rust, das 0,0-Fache der Bezugsgröße von 5. "
        "Testweise ohne Schwelle."
    ) in chosen.reasons


def test_a_repo_on_two_origins_appears_once_under_the_higher_multiple():
    edition = curate(
        project("a/x", LEMMY_RUST, points=22),
        project("a/x", LOBSTERS_ORIGIN, points=34),
    )

    (chosen,) = edition.main
    assert chosen.story.origin == LOBSTERS_ORIGIN
    assert "Auch auf Lemmy c/rust, 22 Punkte." in chosen.reasons


def test_a_repo_on_one_origin_names_no_other():
    (chosen,) = curate(project("a/x", LOBSTERS_ORIGIN, points=34)).main

    assert not any(reason.startswith("Auch auf") for reason in chosen.reasons)


def test_a_project_named_in_the_first_post_says_so():
    found = project("a/x", LOBSTERS_ORIGIN, points=34, linked_directly=False, found_in_post=True)

    (chosen,) = curate(found).main

    assert chosen.reasons[0].startswith("Gefunden im ersten Beitrag.")


def test_a_weekly_edition_belongs_to_the_monday_of_its_week():
    assert edition_day(FORUMS, date(2026, 11, 18)) == date(2026, 11, 16)
    assert edition_day(FORUMS, date(2026, 11, 16)) == date(2026, 11, 16)


def test_a_daily_edition_belongs_to_its_day():
    assert edition_day(HN, date(2026, 11, 18)) == date(2026, 11, 18)
