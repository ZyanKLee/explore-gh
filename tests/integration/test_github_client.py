import httpx
import pytest

from github_anti_ai.adapters.github_http import RequestBudgetExceeded, make_github_client
from github_anti_ai.application.ports import SourceUnavailable


def client_recording(requests, max_requests=2000):
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})

    return make_github_client(
        "github_pat_test", max_requests=max_requests, transport=httpx.MockTransport(handler)
    )


def test_client_talks_to_the_github_api():
    requests = []

    client_recording(requests).get("/rate_limit")

    assert str(requests[0].url) == "https://api.github.com/rate_limit"


def test_client_authenticates_and_identifies_itself():
    requests = []

    client_recording(requests).get("/rate_limit")

    headers = requests[0].headers
    assert headers["authorization"] == "Bearer github_pat_test"
    assert headers["user-agent"].startswith("github-anti-ai")
    assert headers["accept"] == "application/vnd.github+json"
    assert headers["x-github-api-version"] == "2022-11-28"


def test_client_refuses_requests_beyond_the_budget_of_a_run():
    requests = []
    client = client_recording(requests, max_requests=2)
    client.get("/rate_limit")
    client.get("/rate_limit")

    with pytest.raises(RequestBudgetExceeded):
        client.get("/rate_limit")

    assert len(requests) == 2


def test_exceeded_budget_counts_as_unavailable_source():
    assert issubclass(RequestBudgetExceeded, SourceUnavailable)
