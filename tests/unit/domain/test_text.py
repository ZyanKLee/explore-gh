import pytest

from github_anti_ai.domain.text import TermList, labels, number, quoted


class TestTermList:
    def test_finds_terms_as_whole_words_only(self):
        terms = TermList(["ai"])

        assert terms.find("An AI tool") == ["ai"]
        assert terms.find("A tool for email and chairs") == []

    @pytest.mark.parametrize("text", ["text-to-image", "text_to_image", "Text  To\nImage"])
    def test_hyphens_underscores_case_and_spacing_do_not_matter(self, text):
        assert TermList(["text to image"]).find(text) == ["text to image"]

    def test_a_plural_s_counts(self):
        assert TermList(["agent"]).find("Agents for everyone") == ["agent"]

    def test_prefers_the_longer_term(self):
        assert TermList(["ai", "ai agent"]).find("an AI agent") == ["ai agent"]

    def test_finds_nothing_inside_an_excepted_phrase(self):
        terms = TermList(["agent"], unless_in=["user agent"])

        assert terms.find("Parse the User-Agent header") == []
        assert terms.find("A coding agent") == ["agent"]

    def test_distinct_keeps_the_order_of_the_text(self):
        assert TermList(["b", "a"]).distinct("a b a b") == ["a", "b"]


def test_labels_join_name_description_and_topics():
    assert labels("tiny", "An editor", ["rust", "tui"]) == "tiny . An editor . rust . tui"


def test_number_uses_the_german_thousands_separator():
    assert number(91943) == "91.943"
    assert number(12) == "12"


def test_quoted_shows_four_terms_and_hints_at_more():
    assert quoted(["a", "b"]) == "„a“, „b“"
    assert quoted(["a", "b", "c", "d", "e"]) == "„a“, „b“, „c“, „d“ …"
