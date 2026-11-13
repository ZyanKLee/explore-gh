from dataclasses import dataclass
from datetime import date, timedelta

from github_anti_ai.domain.community import CommunityCurator, recently_shown, repository_key


@dataclass(frozen=True)
class Project:
    """Stands in for an HN or Lobsters project: only what the shared rules look at."""

    repository_url: str
    points: int
    license_id: str | None = "MIT"
    has_code: bool = True
    is_fork: bool = False
    is_archived: bool = False

    @property
    def is_open_source(self) -> bool:
        return self.license_id == "MIT"


def by_points(project: Project) -> tuple[int]:
    return (-project.points,)


def select(*projects: Project) -> list[str]:
    chosen = CommunityCurator().select(projects, rank=by_points)
    return [project.repository_url for project in chosen]


def test_community_curator_keeps_an_open_source_project_with_code():
    assert select(Project("https://codeberg.org/a/tool", 10)) == ["https://codeberg.org/a/tool"]


def test_community_curator_drops_a_project_without_open_source_license():
    assert select(Project("https://codeberg.org/a/tool", 10, license_id=None)) == []


def test_community_curator_drops_a_project_without_code():
    assert select(Project("https://codeberg.org/a/tool", 10, has_code=False)) == []


def test_community_curator_drops_forks_and_archived_repos():
    assert select(
        Project("https://codeberg.org/a/fork", 10, is_fork=True),
        Project("https://codeberg.org/a/old", 10, is_archived=True),
    ) == []


def test_community_curator_orders_by_the_platform_rank():
    assert select(
        Project("https://codeberg.org/a/lower", 10),
        Project("https://codeberg.org/a/higher", 50),
    ) == ["https://codeberg.org/a/higher", "https://codeberg.org/a/lower"]


def test_community_curator_keeps_one_repo_once_with_its_best_ranked_story():
    chosen = CommunityCurator().select(
        [
            Project("https://github.com/a/tool", 10),
            Project("https://github.com/A/Tool/", 90),
        ],
        rank=by_points,
    )

    assert [project.points for project in chosen] == [90]


def test_community_curator_stops_after_20_projects():
    projects = [Project(f"https://codeberg.org/a/tool{n}", n) for n in range(25)]

    chosen = select(*projects)

    assert len(chosen) == 20
    assert chosen[0] == "https://codeberg.org/a/tool24"


def test_repository_key_ignores_case_and_trailing_slash():
    assert repository_key("https://github.com/A/Tool/") == repository_key("https://github.com/a/tool")


@dataclass(frozen=True)
class PastEdition:
    day: date
    projects: tuple[Project, ...]


TODAY = date(2026, 11, 13)


def shown(days_ago: int, url: str) -> PastEdition:
    return PastEdition(TODAY - timedelta(days=days_ago), (Project(url, 10),))


def test_community_curator_drops_a_repo_under_cooldown():
    chosen = CommunityCurator().select(
        [Project("https://github.com/a/old", 90), Project("https://github.com/a/new", 10)],
        rank=by_points,
        cooled_down={repository_key("https://github.com/A/Old")},
    )

    assert [project.repository_url for project in chosen] == ["https://github.com/a/new"]


def test_cooldown_blocks_a_repo_shown_29_days_ago():
    assert recently_shown(TODAY, [shown(29, "https://github.com/a/tool")]) == {
        "https://github.com/a/tool"
    }


def test_cooldown_releases_a_repo_shown_30_days_ago():
    assert recently_shown(TODAY, [shown(30, "https://github.com/a/tool")]) == set()


def test_cooldown_compares_repos_by_repository_key():
    assert recently_shown(TODAY, [shown(1, "https://github.com/A/Tool/")]) == {
        repository_key("https://github.com/a/tool")
    }
