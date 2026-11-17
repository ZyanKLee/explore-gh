"""A fake web for adapter tests: answers by address, remembers every request."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx

from github_anti_ai.adapters.github_http import make_github_client

FIXTURES = Path(__file__).parent / "integration" / "fixtures"

Answer = httpx.Response | Callable[[httpx.Request], httpx.Response]


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class FakeWeb:
    """`routes` maps "METHOD host/path" (or "host/path" for GET) to answers.

    An answer is a response, a function of the request, or a list of them for repeated
    requests (the last one stays). Unknown addresses get a 404.
    """

    def __init__(self, routes: dict[str, Answer | list[Answer]] | None = None):
        self.routes = dict(routes or {})
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.url.host}{_raw_path(request)}"
        answer = self.routes.get(f"{request.method} {key}", self.routes.get(key))
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if answer is None:
            return httpx.Response(404, json={"message": "Not Found"})
        return answer(request) if callable(answer) else answer

    @property
    def paths(self) -> list[str]:
        return [f"{r.url.host}{_raw_path(r)}" for r in self.requests]

    def client(self, **options) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), **options)

    def github_client(self, **options) -> httpx.Client:
        return make_github_client("test-token", transport=httpx.MockTransport(self), **options)


def _raw_path(request: httpx.Request) -> str:
    """The path as sent, with %2F left as it is: GitLab needs it."""
    return request.url.raw_path.decode().partition("?")[0]


class Sleeps(list):
    """A sleep function that remembers how long it was asked to wait."""

    def __call__(self, seconds: float) -> None:
        self.append(seconds)
