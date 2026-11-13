from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from github_anti_ai.domain.community import (
    CommunityCurator,
    check_community_edition,
    owner_key,
    recently_shown,
    repository_key,
)


@dataclass(frozen=True)
class Project:
    """Stands in for an HN or Lobsters project: only what the shared rules look at."""

    repository_url: str
    points: int
    license_id: str | None = "MIT"
    has_code: bool = True
    is_fork: bool = False
    is_archived: bool = False
    language: str | None = "Rust"
    description: str = "A small tool"
    topics: tuple[str, ...] = ()
    readme: str | None = None  # None: not read, so no reason to exclude

    @property
    def is_open_source(self) -> bool:
        return self.license_id == "MIT"


def by_points(project: Project) -> tuple[int]:
    return (-project.points,)


def select(*projects: Project) -> list[str]:
    """The repository addresses in the main section."""
    chosen = CommunityCurator().select(projects, rank=by_points).main
    return [project.repository_url for project in chosen]


def ai_project(url: str, points: int, **overrides) -> Project:
    return Project(url, points, description="An LLM agent for your MCP tools", **overrides)


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
    ).main

    assert [project.points for project in chosen] == [90]


def test_community_curator_stops_after_20_projects():
    languages = ["Rust", "Go", "C", "Zig", "Python", "Lua", None]
    projects = [
        Project(f"https://codeberg.org/owner{n}/tool", n, language=languages[n % 7])
        for n in range(25)
    ]

    chosen = select(*projects)

    assert len(chosen) == 20
    assert chosen[0] == "https://codeberg.org/owner24/tool"


def test_repository_key_ignores_case_and_trailing_slash():
    assert repository_key("https://github.com/A/Tool/") == repository_key("https://github.com/a/tool")


@dataclass(frozen=True)
class PastEdition:
    day: date
    projects: tuple[Project, ...]
    ai_projects: tuple[Project, ...] = ()


TODAY = date(2026, 11, 13)


def shown(days_ago: int, url: str) -> PastEdition:
    return PastEdition(TODAY - timedelta(days=days_ago), (Project(url, 10),))


def test_community_curator_drops_a_repo_under_cooldown():
    chosen = CommunityCurator().select(
        [Project("https://github.com/a/old", 90), Project("https://github.com/a/new", 10)],
        rank=by_points,
        cooled_down={repository_key("https://github.com/A/Old")},
    ).main

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


def test_community_curator_takes_at_most_4_projects_of_one_language():
    rust = [Project(f"https://github.com/owner{n}/tool", 100 - n) for n in range(5)]
    go = Project("https://github.com/gopher/tool", 1, language="Go")

    chosen = select(*rust, go)

    assert chosen == [project.repository_url for project in rust[:4]] + [go.repository_url]


def test_community_curator_treats_projects_without_language_as_one_language():
    unknown = [Project(f"https://github.com/owner{n}/tool", 100 - n, language=None) for n in range(5)]

    assert len(select(*unknown)) == 4


def test_community_curator_takes_at_most_2_projects_of_one_owner():
    chosen = select(
        Project("https://github.com/rust-lang/rust", 90, language="Rust"),
        Project("https://github.com/Rust-Lang/cargo", 80, language="Rust"),
        Project("https://github.com/rust-lang/clippy", 70, language="Rust"),
        Project("https://github.com/alice/tool", 10, language="Go"),
    )

    assert chosen == [
        "https://github.com/rust-lang/rust",
        "https://github.com/Rust-Lang/cargo",
        "https://github.com/alice/tool",
    ]


def test_owners_of_the_same_name_on_different_forges_are_different_owners():
    assert owner_key("https://github.com/alice/a") != owner_key("https://codeberg.org/alice/b")
    assert owner_key("https://github.com/Alice/a") == owner_key("https://github.com/alice/b")


def test_community_edition_accepts_a_varied_selection():
    check_community_edition(
        [Project("https://github.com/a/one", 1), Project("https://github.com/b/two", 1)], "HN"
    )


@pytest.mark.parametrize(
    ("projects", "message"),
    [
        ([Project(f"https://github.com/o{n}/t", 1, language=f"L{n}") for n in range(21)],
         "mehr als 20"),
        ([Project(f"https://github.com/o{n}/t", 1) for n in range(5)], "Sprache"),
        ([Project(f"https://github.com/o/t{n}", 1, language=f"L{n}") for n in range(3)],
         "Besitzer"),
        ([Project("https://github.com/o/t", 1), Project("https://github.com/O/T/", 1)],
         "mehrfach"),
    ],
)
def test_community_edition_rejects_a_selection_breaking_its_rules(projects, message):
    with pytest.raises(ValueError, match=message):
        check_community_edition(projects, "HN")


def test_community_curator_puts_an_ai_focused_project_into_the_ai_section():
    selection = CommunityCurator().select(
        [ai_project("https://github.com/a/agent", 90), Project("https://github.com/b/editor", 10)],
        rank=by_points,
    )

    assert [project.repository_url for project in selection.main] == ["https://github.com/b/editor"]
    assert [project.repository_url for project in selection.ai] == ["https://github.com/a/agent"]


def test_community_curator_keeps_a_project_mentioning_ai_once_in_the_main_section():
    editor = Project("https://github.com/b/editor", 10, description="Video editor with AI captions")

    selection = CommunityCurator().select([editor], rank=by_points)

    assert selection.main == (editor,)
    assert selection.ai == ()


def test_community_curator_applies_diversity_to_each_section_on_its_own():
    rust = [Project(f"https://github.com/o{n}/tool", 100 - n) for n in range(4)]
    rust_ai = [ai_project(f"https://github.com/ai{n}/agent", 50 - n) for n in range(4)]

    selection = CommunityCurator().select(rust + rust_ai, rank=by_points)

    assert len(selection.main) == 4
    assert len(selection.ai) == 4


def test_community_curator_applies_the_cooldown_to_the_ai_section_too():
    selection = CommunityCurator().select(
        [ai_project("https://github.com/a/agent", 90)],
        rank=by_points,
        cooled_down={repository_key("https://github.com/a/agent")},
    )

    assert selection.ai == ()


def test_community_edition_rejects_a_repo_in_both_sections():
    with pytest.raises(ValueError, match="mehrfach"):
        check_community_edition(
            [Project("https://github.com/a/tool", 1)], "HN",
            ai_projects=[Project("https://github.com/a/tool", 1)],
        )


def test_community_curator_drops_a_project_the_github_exclusions_remove():
    assert select(
        Project("https://github.com/a/awesome-rust", 90),
        Project("https://github.com/a/coin", 80, topics=("blockchain",)),
        Project("https://github.com/a/empty", 70, readme=""),
    ) == []


def test_community_curator_keeps_a_project_whose_readme_could_not_be_read():
    assert select(Project("https://github.com/a/tool", 10, readme=None)) == [
        "https://github.com/a/tool"
    ]
