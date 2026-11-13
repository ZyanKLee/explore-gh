from github_anti_ai.domain.text import TermList


def test_term_list_can_leave_out_phrases_in_which_a_term_means_something_else():
    terms = TermList(["agent"], unless_in=["user agent", "ssh agent"])

    assert terms.find("Parses the User-Agent header") == []
    assert terms.find("forwards your ssh_agent to an agent") == ["agent"]
