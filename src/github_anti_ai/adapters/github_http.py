"""HTTP access to the GitHub API, shared by all GitHub adapters.

See docs/datensammlung.md, "Fehler und Rate Limits".
"""

from collections.abc import Callable

import httpx

from github_anti_ai.application.ports import Clock, SourceUnavailable

API_URL = "https://api.github.com"
USER_AGENT = "github-anti-ai (personal explore page)"
API_VERSION = "2022-11-28"
MAX_REQUESTS_PER_RUN = 4000
MAX_ATTEMPTS = 3
GATEWAY_TIMEOUTS = (502, 504)

Sleep = Callable[[float], None]


class RequestBudgetExceeded(SourceUnavailable):
    """Emergency brake: a run made far more requests than it ever should."""


class GatewayTimeout(SourceUnavailable):
    """HTTP 502 or 504: GitHub gave up on the request, usually after 10 seconds."""


def make_github_client(
    token: str,
    *,
    max_requests: int = MAX_REQUESTS_PER_RUN,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    """A client that counts its requests and refuses more than `max_requests`."""
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
    client: httpx.Client,
    method: str,
    url: str,
    *,
    sleep: Sleep,
    clock: Clock,
    retry_timeouts: bool = True,
    **options,
) -> httpx.Response:
    """Sends a request, waits out rate limits and retries server errors.

    Without `retry_timeouts` a gateway timeout is reported at once: the caller has a
    better answer than asking the same question again.
    """
    timed_out = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        timed_out = False
        backoff = 2.0**attempt
        try:
            response = client.request(method, url, **options)
        except httpx.TransportError as error:
            problem, wait = f"{method} {url}: {error}", backoff
        else:
            problem = f"{method} {url}: HTTP {response.status_code}"
            if not response.is_error:
                if _is_json(response):
                    return response
                # seen live: a 200 whose body ended in the middle
                problem, wait = f"{method} {url}: unlesbare Antwort", backoff
            elif response.status_code >= 500:
                wait = backoff
                timed_out = response.status_code in GATEWAY_TIMEOUTS
                if timed_out and not retry_timeouts:
                    break
            elif (wait := _rate_limit_wait(response, clock)) is None:
                raise SourceUnavailable(problem)
        if attempt < MAX_ATTEMPTS:
            sleep(wait)
    raise (GatewayTimeout if timed_out else SourceUnavailable)(problem)


def _is_json(response: httpx.Response) -> bool:
    try:
        response.json()
    except ValueError:
        return False
    return True


def _rate_limit_wait(response: httpx.Response, clock: Clock) -> float | None:
    """Seconds to wait for a rate limit, None if the response is no rate limit."""
    if response.status_code not in (403, 429):
        return None
    if "retry-after" in response.headers:
        return float(response.headers["retry-after"])
    if response.headers.get("x-ratelimit-remaining") == "0":
        reset = float(response.headers["x-ratelimit-reset"])
        return max(reset - clock.now().timestamp(), 0) + 1
    return None
