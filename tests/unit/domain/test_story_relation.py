import pytest

from github_anti_ai.domain.story_relation import relates_to_story, shared_words


def test_repo_and_story_share_words_of_the_title():
    words = shared_words(
        "Announcing the GraphQL over HTTP specification",
        "https://graphql.org/blog/2026-11-12-http",
        "https://github.com/graphql/graphql-over-http",
    )

    assert words == {"graphql", "over", "http"}


def test_the_host_counts_also_without_separators():
    words = shared_words(
        "Faster compile times",
        "https://blog.rust-lang.org/2026/11/12/x",
        "https://github.com/rust-lang/rust",
    )

    assert words == {"rust", "lang", "rustlang"}


def test_the_path_of_the_page_counts():
    assert relates_to_story(
        "A mod release",
        "https://www.moddb.com/mods/openq4/news",
        "https://github.com/themuffinator/openQ4",
    )


def test_a_short_repo_name_counts_in_full():
    assert shared_words(
        "Adapting CPython for yk", "https://example.org/post", "https://github.com/ykjit/yk"
    ) == {"yk"}


def test_a_short_part_of_a_name_does_not():
    assert not relates_to_story(
        "Adapting CPython for yk", "https://example.org/", "https://github.com/a/yk-tools"
    )


@pytest.mark.parametrize("repo", ["https://github.com/someone/blog", "https://github.com/x/source"])
def test_generic_words_do_not_count(repo):
    assert not relates_to_story("My new blog about open source", "https://blog.example.org/", repo)


@pytest.mark.parametrize(
    "repo",
    [
        "https://github.com/rust-lang/rust-lang.github.io",
        "https://codeberg.org/rust/rust.codeberg.page",
    ],
)
def test_website_repos_never_count(repo):
    assert shared_words("Rust news", "https://blog.rust-lang.org/", repo) == set()


def test_a_blog_theme_has_nothing_to_do_with_the_story():
    assert not relates_to_story(
        "Inside a data center",
        "https://example.org/datacenter",
        "https://github.com/bitbrain/jekyll-dash",
    )
