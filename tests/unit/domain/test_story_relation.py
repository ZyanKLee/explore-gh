"""Bezug zur Story: a repo found on a website must share a word with the story."""

from github_anti_ai.domain.community import relates_to_story, shared_words


def test_repo_named_in_the_story_title_relates_to_the_story():
    assert relates_to_story(
        title="Hijacking Samsung TV Smart Hub Ads",
        page_url="https://dvratil.cz/2026/11/hijacking-samsung-tv-smart-hub-ads/",
        repository_url="https://github.com/danvratil/samsung-tv-adspoofer",
    )


def test_repo_owner_named_in_the_website_host_relates_to_the_story():
    assert relates_to_story(
        title="Version 21.0 released",
        page_url="https://dyalog.com/dyalog/dyalog-versions/210.htm",
        repository_url="https://github.com/Dyalog/ride",
    )


def test_repo_and_host_split_at_hyphens_relate_to_the_story():
    assert relates_to_story(
        title="Announcing 1.100.0",
        page_url="https://blog.rust-lang.org/2026/11/12/Rust-1.100.0/",
        repository_url="https://github.com/rust-lang/rust",
    )


def test_repo_name_written_without_separators_relates_to_the_story():
    assert relates_to_story(
        title="ZigZag: embroidery without a subscription",
        page_url="https://example.org/",
        repository_url="https://github.com/someone/zig-zag",
    )


def test_last_path_part_of_a_gitlab_subgroup_repo_counts_as_its_name():
    assert relates_to_story(
        title="Tool 2.0 is out",
        page_url="https://example.org/",
        repository_url="https://gitlab.com/group/subgroup/tool",
    )


def test_blog_theme_without_shared_word_does_not_relate_to_the_story():
    assert not relates_to_story(
        title="How a false smoke alarm almost drowned Jane Street's only NYC datacenter",
        page_url="https://michael.bacarella.com/2026/11/10/false-smoke-alarm/",
        repository_url="https://github.com/bitbrain/jekyll-dash",
    )


def test_employer_repo_without_shared_word_does_not_relate_to_the_story():
    assert not relates_to_story(
        title='Contra "Glue work considered harmful"',
        page_url="https://sunshowers.io/posts/glue-work/",
        repository_url="https://github.com/oxidecomputer/omicron",
    )


def test_generic_words_do_not_make_a_relation():
    assert not relates_to_story(
        title="The new blog for open source code",
        page_url="https://blog.example.com/",
        repository_url="https://github.com/someone/blog-theme",
    )


def test_numbers_and_short_words_do_not_make_a_relation():
    assert not relates_to_story(
        title="Go 1.100 on TV",
        page_url="https://example.org/",
        repository_url="https://github.com/go-tv/tool-100",
    )


def test_website_repo_never_relates_to_the_story():
    assert not relates_to_story(
        title="Announcing the GraphQL over HTTP specification",
        page_url="https://graphql.org/blog/2026-11-12-announcing-the-graphql-over-http-spec/",
        repository_url="https://github.com/graphql/graphql.github.io",
    )


def test_gitlab_and_codeberg_pages_repos_never_relate_to_the_story():
    for repository_url in (
        "https://gitlab.com/tool/tool.gitlab.io",
        "https://codeberg.org/tool/tool.codeberg.page",
    ):
        assert not relates_to_story("Tool", "https://tool.example/", repository_url)


def test_short_repo_name_counts_when_the_title_names_it_in_full():
    assert relates_to_story(
        title="Adapting CPython for yk",
        page_url="https://tratt.net/laurie/blog/2026/adapting_cpython_for_yk.html",
        repository_url="https://github.com/ykjit/yk",
    )


def test_short_part_of_a_longer_repo_name_does_not_count():
    assert not relates_to_story(
        title="Yk and CPython",
        page_url="https://example.org/",
        repository_url="https://github.com/someone/yk-tools",
    )


def test_repo_named_in_the_path_of_the_website_relates_to_the_story():
    assert relates_to_story(
        title="Abandoned Quake 4 expansion finished by modders and now playable",
        page_url="https://www.moddb.com/mods/openq4/downloads/openq4-0141-windows-x64",
        repository_url="https://github.com/themuffinator/openQ4",
    )


def test_shared_words_name_every_word_repo_and_story_have_in_common():
    story = (
        "Announcing the GraphQL over HTTP specification",
        "https://graphql.org/blog/2026-11-12-announcing-the-graphql-over-http-spec/",
    )

    assert shared_words(*story, "https://github.com/graphql/graphql-over-http") == {
        "graphql", "over", "http",
    }
    assert shared_words(*story, "https://github.com/graphql/graphql-spec") == {"graphql", "spec"}


def test_website_repo_shares_no_words_with_the_story():
    website_repo = "https://github.com/graphql/graphql.github.io"

    assert shared_words("GraphQL", "https://graphql.org/", website_repo) == set()
