"""HTTP access to the GitHub API, shared by all GitHub adapters."""

from collections.abc import Callable

import httpx

from github_anti_ai.application.ports import Clock, SourceUnavailable

API_URL = "https://api.github.com"
USER_AGENT = "github-anti-ai (personal explore page)"
API_VERSION = "2022-11-28"
MAX_REQUESTS_PER_RUN = 4000
MAX_ATTEMPTS = 3

Sleep = Callable[[float], None]


class RequestBudgetExceeded(SourceUnavailable):
    """Emergency brake: a run made far more requests than it ever should."""


def make_github_client(
    token: str,
    *,
    max_requests: int = MAX_REQUESTS_PER_RUN,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    sent = 0

    def count_request(request: httpx.Request) -> None:
        nonlocal sent
        if sent >= max_requests:
            raise RequestBudgetExceeded(f"Mehr als {max_requests} Anfragen in einem Lauf")
        sent += 1

    return httpx.Client(
        base_url=API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        },
        event_hooks={"request": [count_request]},
        transport=transport,
        timeout=30,
    )


def send(
    client: httpx.Client, method: str, url: str, *, sleep: Sleep, clock: Clock, **options
) -> httpx.Response:
    """Sends a request, waits out rate limits and retries server errors."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.request(method, url, **options)
        except httpx.TransportError as error:
            problem, wait = f"{method} {url}: {error}", 2.0**attempt
        else:
            if not response.is_error:
                return response
            problem = f"{method} {url}: HTTP {response.status_code}"
            if response.status_code >= 500:
                wait = 2.0**attempt
            elif (wait := _rate_limit_wait(response, clock)) is None:
                raise SourceUnavailable(problem)
        if attempt < MAX_ATTEMPTS:
            sleep(wait)
    raise SourceUnavailable(problem)


def _rate_limit_wait(response: httpx.Response, clock: Clock) -> float | None:
    if response.status_code not in (403, 429):
        return None
    if "retry-after" in response.headers:
        return float(response.headers["retry-after"])
    if response.headers.get("x-ratelimit-remaining") == "0":
        reset = float(response.headers["x-ratelimit-reset"])
        return max(reset - clock.now().timestamp(), 0) + 1
    return None
