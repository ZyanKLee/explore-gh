import httpx
import pytest
from builders import NOW, FixedClock
from http_fakes import FakeWeb, Sleeps

from github_anti_ai.adapters.github_http import (
    GatewayTimeout,
    RequestBudgetExceeded,
    make_github_client,
    send,
)
from github_anti_ai.application.ports import SourceUnavailable

OK = httpx.Response(200, json={"ok": True})


def call(web, sleep=None, **options):
    with web.github_client() as client:
        return send(
            client,
            "GET",
            "/x",
            sleep=sleep if sleep is not None else Sleeps(),
            clock=FixedClock(),
            **options,
        )


def test_the_client_talks_to_the_github_api_and_identifies_itself():
    web = FakeWeb({"api.github.com/x": OK})

    call(web)

    request = web.requests[0]
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.headers["User-Agent"].startswith("github-anti-ai")
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_the_client_refuses_requests_beyond_the_budget_of_a_run():
    web = FakeWeb({"api.github.com/x": OK})
    with make_github_client("t", max_requests=1, transport=httpx.MockTransport(web)) as client:
        client.get("/x")
        with pytest.raises(RequestBudgetExceeded):
            client.get("/x")
    assert issubclass(RequestBudgetExceeded, SourceUnavailable)


def test_a_rate_limit_is_waited_out_as_told():
    sleeps = Sleeps()
    web = FakeWeb({"api.github.com/x": [httpx.Response(429, headers={"retry-after": "7"}), OK]})

    assert call(web, sleeps).json() == {"ok": True}
    assert sleeps == [7.0]


def test_an_exhausted_rate_limit_waits_until_the_reset():
    sleeps = Sleeps()
    reset = str(int(NOW.timestamp()) + 60)
    limited = httpx.Response(
        403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}
    )
    web = FakeWeb({"api.github.com/x": [limited, OK]})

    call(web, sleeps)

    assert sleeps == [61.0]


def test_a_refusal_without_rate_limit_is_no_reason_to_wait():
    web = FakeWeb({"api.github.com/x": httpx.Response(403)})

    with pytest.raises(SourceUnavailable, match="HTTP 403"):
        call(web)
    assert len(web.requests) == 1


def test_server_errors_are_retried_with_growing_pauses_three_times_at_most():
    sleeps = Sleeps()
    web = FakeWeb({"api.github.com/x": httpx.Response(500)})

    with pytest.raises(SourceUnavailable):
        call(web, sleeps)
    assert len(web.requests) == 3
    assert sleeps == [2.0, 4.0]


def test_a_cut_off_answer_is_retried():
    web = FakeWeb({"api.github.com/x": [httpx.Response(200, text='{"items": ['), OK]})

    assert call(web).json() == {"ok": True}


def test_a_gateway_timeout_is_reported_at_once_when_asked_to():
    web = FakeWeb({"api.github.com/x": httpx.Response(504)})

    with pytest.raises(GatewayTimeout):
        call(web, retry_timeouts=False)
    assert len(web.requests) == 1
