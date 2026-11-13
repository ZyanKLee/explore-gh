"""CollectSnapshots reuses the snapshots of the last days instead of fetching everything."""

from datetime import timedelta

from builders import NOW, TODAY, FixedClock, make_snapshot, star_history
from fakes import InMemorySnapshotStore
from github_anti_ai.application.collect_snapshots import (
    FRESH_LEADERS_PER_SECTION,
    REFRESH_AFTER_DAYS,
    CollectSnapshots,
)
from github_anti_ai.application.ports import SourceUnavailable
from github_anti_ai.domain.model import (
    Assessment,
    Candidate,
    Exclusion,
    RepoId,
    Section,
    StarHistory,
)

FRESH_STARS = 950


def days_ago(days):
    return NOW - timedelta(days=days)


class FakeSearch:
    """A candidate source that knows the star counts, like the GitHub search."""

    name = "search"

    def __init__(self, stars_by_repo):
        self.candidates = [Candidate(RepoId.parse(r), s) for r, s in stars_by_repo.items()]

    def discover(self, today, limit=None):
        return list(self.candidates[:limit])


class FakeRepoSource:
    def __init__(self, unknown=(), failing=()):
        self.unknown = {RepoId.parse(r) for r in unknown}
        self.failing = {RepoId.parse(r) for r in failing}
        self.requests = []  # (repo names, with_star_history)

    def fetch(self, repos, now, with_star_history=True):
        self.requests.append(([str(r) for r in repos], with_star_history))
        if any(r in self.failing for r in repos):
            raise SourceUnavailable("HTTP 502")
        return [
            make_snapshot(
                str(r),
                taken_at=now,
                stars=FRESH_STARS,
                description="fresh from GitHub",
                star_history=star_history(120) if with_star_history else StarHistory(daily=()),
            )
            for r in repos
            if r not in self.unknown
        ]

    def requested(self, with_star_history):
        return [r for repos, flag in self.requests if flag is with_star_history for r in repos]


def earlier(repo="alice/tiny-editor", *, taken=1, facts=None, **fields):
    """A snapshot of an earlier day. Its facts may be older than the snapshot."""
    fields.setdefault("stars", 812)
    fields.setdefault("description", "from an earlier day")
    return make_snapshot(
        repo, taken_at=days_ago(taken), facts_at=days_ago(taken if facts is None else facts), **fields
    )


def store_with(*snapshots):
    store = InMemorySnapshotStore()
    for snapshot in snapshots:
        store.append(snapshot.taken_at.date(), [snapshot])
    return store


def collect(stars_by_repo, store, repo_source=None, assess=None):
    repo_source = repo_source or FakeRepoSource()
    report = CollectSnapshots(
        candidate_sources=[FakeSearch(stars_by_repo)],
        repo_source=repo_source,
        snapshot_store=store,
        clock=FixedClock(NOW),
        assess=assess,
    ).run()
    return report, repo_source


def today(store, repo="alice/tiny-editor"):
    [snapshot] = [s for s in store.load(TODAY) if s.repo == RepoId.parse(repo)]
    return snapshot


def test_repo_seen_for_the_first_time_is_fetched_with_its_star_history():
    store = InMemorySnapshotStore()

    report, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == [(["alice/tiny-editor"], True)]
    assert today(store).star_history == star_history(120)
    assert (report.fetched, report.refreshed, report.carried_over) == (1, 0, 0)


def test_snapshot_of_yesterday_is_carried_over_without_asking_github():
    store = store_with(earlier(taken=1, stars=812, star_history=star_history(120)))

    report, source = collect({"alice/tiny-editor": 900}, store)

    snapshot = today(store)
    assert source.requests == []
    assert snapshot.taken_at == NOW
    assert snapshot.facts_at == days_ago(1)
    assert snapshot.description == "from an earlier day"
    assert snapshot.stars == 900
    assert snapshot.star_history.daily[-2:] == (120, 88)
    assert (report.fetched, report.refreshed, report.carried_over) == (0, 0, 1)
    assert report.collected == 1


def test_facts_younger_than_the_refresh_age_are_kept():
    store = store_with(earlier(taken=1, facts=REFRESH_AFTER_DAYS - 1))

    _, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == []
    assert today(store).facts_at == days_ago(REFRESH_AFTER_DAYS - 1)


def test_facts_of_the_refresh_age_are_fetched_again_without_the_star_history():
    old = earlier(taken=1, facts=REFRESH_AFTER_DAYS, stars=812, star_history=star_history(120))
    store = store_with(old)

    report, source = collect({"alice/tiny-editor": 900}, store)

    snapshot = today(store)
    assert source.requests == [(["alice/tiny-editor"], False)]
    assert snapshot.description == "fresh from GitHub"
    assert snapshot.facts_at == NOW
    assert snapshot.stars == FRESH_STARS
    # the star history is our own: yesterday's history plus the stars gained since
    assert snapshot.star_history.daily[-2:] == (120, FRESH_STARS - 812)
    assert (report.fetched, report.refreshed, report.carried_over) == (0, 1, 0)


def test_a_day_without_snapshot_is_bridged():
    # the search has gaps: the repo was missing yesterday
    store = store_with(earlier(taken=2, stars=812, star_history=star_history(120)))

    _, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == []
    assert today(store).star_history.daily[-3:] == (120, 0, 88)


def test_the_latest_of_several_earlier_snapshots_is_used():
    store = store_with(earlier(taken=2, stars=700), earlier(taken=1, stars=812))

    collect({"alice/tiny-editor": 900}, store)

    assert today(store).star_history.daily[-1] == 88


def test_repo_not_seen_for_longer_than_the_refresh_age_counts_as_new():
    store = store_with(earlier(taken=REFRESH_AFTER_DAYS + 1))

    report, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == [(["alice/tiny-editor"], True)]
    assert report.fetched == 1


def test_candidate_without_star_count_cannot_be_carried_over():
    # sources like Hacker News will not know the stars
    store = store_with(earlier(taken=1))

    report, source = collect({"alice/tiny-editor": None}, store)

    assert source.requests == [(["alice/tiny-editor"], False)]
    assert report.refreshed == 1


def test_snapshot_without_star_history_is_fetched_in_full():
    # it was a fork or had no code when we saw it, so its history was never collected
    store = store_with(earlier(taken=1, star_history=StarHistory(daily=())))

    _, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == [(["alice/tiny-editor"], True)]


def test_repo_the_sources_no_longer_find_gets_no_snapshot_today():
    store = store_with(earlier("gone/deleted-repo", taken=1), earlier("alice/tiny-editor", taken=1))

    report, source = collect({"alice/tiny-editor": 900}, store)

    assert [str(s.repo) for s in store.load(TODAY)] == ["alice/tiny-editor"]
    assert source.requests == []
    assert report.discovered == 1


def test_repo_that_vanished_between_search_and_refresh_is_reported_as_missing():
    store = store_with(earlier(taken=1, facts=REFRESH_AFTER_DAYS))

    report, _ = collect(
        {"alice/tiny-editor": 900}, store, FakeRepoSource(unknown=["alice/tiny-editor"])
    )

    assert store.load(TODAY) == []
    assert report.missing == (RepoId.parse("alice/tiny-editor"),)


def test_failed_refresh_falls_back_to_the_older_facts():
    store = store_with(earlier(taken=1, facts=REFRESH_AFTER_DAYS))

    report, _ = collect(
        {"alice/tiny-editor": 900}, store, FakeRepoSource(failing=["alice/tiny-editor"])
    )

    snapshot = today(store)
    assert snapshot.description == "from an earlier day"
    assert snapshot.stars == 900
    assert report.failed == ()
    assert report.carried_over == 1
    assert "HTTP 502" in report.fetch_errors[0]


def test_second_run_of_the_day_asks_github_for_nothing():
    store = store_with(earlier("alice/tiny-editor", taken=1), earlier("bob/rustbox", taken=1, facts=5))
    candidates = {"alice/tiny-editor": 900, "bob/rustbox": 100, "carol/plotter": 60}
    collect(candidates, store)

    report, source = collect(candidates, store)

    assert source.requests == []
    assert report.collected == 3


# --- the leaders are refreshed before publishing ---------------------------------------


def by_stars(snapshot, section=Section.MAIN, exclusion=None):
    """An assessor for tests: the score is the star count."""
    return Assessment(
        snapshot=snapshot, section=section, score=snapshot.stars, signals=(), exclusion=exclusion
    )


def carried_repos(count, prefix="user"):
    """Repos with a snapshot of yesterday, the first one has the most stars today."""
    names = [f"{prefix}{i}/project{i}" for i in range(count)]
    store = store_with(*(earlier(name, taken=1) for name in names))
    return names, store, {name: 5000 - i for i, name in enumerate(names)}


def test_leaders_are_refreshed_so_that_nothing_published_is_older_than_a_day():
    names, store, stars = carried_repos(FRESH_LEADERS_PER_SECTION + 5)

    report, source = collect(stars, store, assess=by_stars)

    assert sorted(source.requested(with_star_history=False)) == sorted(
        names[:FRESH_LEADERS_PER_SECTION]
    )
    assert source.requested(with_star_history=True) == []
    assert today(store, names[0]).facts_at == NOW
    assert today(store, names[-1]).facts_at == days_ago(1)
    assert report.refreshed == FRESH_LEADERS_PER_SECTION
    assert report.carried_over == 5


def test_refreshed_leader_keeps_its_own_star_history():
    store = store_with(earlier(taken=1, stars=812, star_history=star_history(120)))

    collect({"alice/tiny-editor": 900}, store, assess=by_stars)

    snapshot = today(store)
    assert snapshot.stars == FRESH_STARS
    assert snapshot.star_history.daily[-2:] == (120, FRESH_STARS - 812)
    assert len(snapshot.star_history.daily) == 35


def test_each_section_has_its_own_leaders():
    names, store, stars = carried_repos(FRESH_LEADERS_PER_SECTION + 1)
    store.append(TODAY - timedelta(days=1), [earlier("dora/llm-proxy", taken=1)])
    stars["dora/llm-proxy"] = 51  # fewer stars than every repo of the main list

    def assess(snapshot):
        section = Section.AI if snapshot.repo.owner == "dora" else Section.MAIN
        return by_stars(snapshot, section)

    _, source = collect(stars, store, assess=assess)

    assert "dora/llm-proxy" in source.requested(with_star_history=False)
    assert names[-1] not in source.requested(with_star_history=False)


def test_excluded_repos_are_no_leaders():
    store = store_with(earlier("alice/tiny-editor", taken=1), earlier("mallory/lure", taken=1))

    def assess(snapshot):
        excluded = Exclusion("Köder", "lure") if snapshot.repo.owner == "mallory" else None
        return by_stars(snapshot, exclusion=excluded)

    _, source = collect({"alice/tiny-editor": 60, "mallory/lure": 5000}, store, assess=assess)

    assert source.requested(with_star_history=False) == ["alice/tiny-editor"]


def test_leader_fetched_today_is_not_fetched_twice():
    _, source = collect({"alice/tiny-editor": 900}, InMemorySnapshotStore(), assess=by_stars)

    assert source.requests == [(["alice/tiny-editor"], True)]


def test_leader_whose_refresh_fails_stays_carried_over():
    store = store_with(earlier(taken=1))

    report, _ = collect(
        {"alice/tiny-editor": 900},
        store,
        FakeRepoSource(failing=["alice/tiny-editor"]),
        assess=by_stars,
    )

    assert today(store).facts_at == days_ago(1)
    assert report.failed == ()
    assert report.collected == 1


def test_without_an_assessor_no_leaders_are_refreshed():
    store = store_with(earlier(taken=1))

    _, source = collect({"alice/tiny-editor": 900}, store)

    assert source.requests == []
