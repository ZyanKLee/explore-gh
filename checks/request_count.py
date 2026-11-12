"""Counts the API requests of one full collection run against a fake GitHub.

    python checks/request_count.py                 prints the request count (the score)
    python checks/request_count.py --verify        guard: the collected data must be right
    python checks/request_count.py --mix FILE      uses the repo mix of FILE instead of the synthetic one
    python checks/request_count.py --write-reference   stores the reference output (once, before a climb)

No network, no token. The real adapters and the real use case run, only the HTTP
transport is replaced. Repo names and their order change on every run, the mix does not.
"""

import argparse
import dataclasses
import json
import random
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.adapters.github_search import GitHubSearchCandidates
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.application.collect_snapshots import CollectSnapshots

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)
TODAY = NOW.date()
HISTORY_DAYS = 35
REFERENCE = Path(__file__).with_name("reference_snapshots.json")
REFERENCE_SEED = 1

# Synthetic mix, taken from 880 real candidates collected on 2026-11-12:
# 1000 repos over 30 creation days, 118 of them without any recognized code.
SYNTHETIC_REPOS = 1000
SYNTHETIC_WITHOUT_LANGUAGE = 118
LANGUAGES = ["Python", "TypeScript", "Rust", "JavaScript", "C", "Go", "C++", "Swift", "HTML"]


class Clock:
    def now(self):
        return NOW


def synthetic_mix():
    """One entry per repo: age in days and whether GitHub recognizes a language."""
    ages = [i % 30 for i in range(SYNTHETIC_REPOS)]
    return [
        {"age": age, "language": index >= SYNTHETIC_WITHOUT_LANGUAGE,
         "fork": False, "archived": False, "mirror": False}
        for index, age in enumerate(ages)
    ]


def build_world(mix, seed):
    """Ground truth of the fake GitHub: repo facts and the stars of each day."""
    rng = random.Random(seed)
    mix = list(mix)
    rng.shuffle(mix)
    world = {}
    for index, entry in enumerate(mix):
        owner = f"u{rng.randrange(10**6)}x{index}"
        name = f"p{rng.randrange(10**6)}"
        created = TODAY - timedelta(days=entry["age"])
        daily = {}
        for back in range(min(entry["age"], HISTORY_DAYS - 1), -1, -1):
            daily[TODAY - timedelta(days=back)] = rng.randrange(0, 60)
        daily[TODAY] = daily.get(TODAY, 0) + 50  # every candidate has at least 50 stars
        world[f"{owner}/{name}".lower()] = {
            "repo": f"{owner}/{name}",
            "created": created,
            "language": rng.choice(LANGUAGES) if entry["language"] else None,
            "fork": entry["fork"], "archived": entry["archived"], "mirror": entry["mirror"],
            "daily": daily,
            "stars": sum(daily.values()),
            "forks": rng.randrange(0, 40),
        }
    return world


def node(truth):
    return {
        "nameWithOwner": truth["repo"],
        "description": f"Project {truth['repo']}",
        "homepageUrl": "",
        "repositoryTopics": {"nodes": [{"topic": {"name": "tool"}}]},
        "primaryLanguage": {"name": truth["language"]} if truth["language"] else None,
        "createdAt": f"{truth['created'].isoformat()}T00:00:00Z",
        "pushedAt": "2026-11-11T12:00:00Z",
        "stargazerCount": truth["stars"],
        "forkCount": truth["forks"],
        "issues": {"totalCount": 3},
        "watchers": {"totalCount": 2},
        "pullRequests": {"totalCount": 4},
        "recentIssues": {"nodes": [{"author": {"__typename": "User", "login": "someone"}}]},
        "isFork": truth["fork"], "isArchived": truth["archived"], "isMirror": truth["mirror"],
        "isTemplate": False,
        "licenseInfo": {"spdxId": "MIT"},
        "rootTree": {"entries": [{"name": "README.md"}, {"name": "src"}]},
        "readmeMd": {"text": f"# {truth['repo']}\n\nA project.\n"},
        "defaultBranchRef": {"target": {"history": {"nodes": [{
            "committedDate": "2026-11-11T12:00:00Z", "messageHeadline": "Work",
            "message": "Work", "author": {"name": "Someone", "user": {"login": "someone"}},
        }]}}},
    }


def history_weeks(truth, per_page):
    """Weeks newest first, each starting on Sunday, as GitHub returns them."""
    weeks = {}
    for day, stars in truth["daily"].items():
        sunday = day - timedelta(days=(day.weekday() + 1) % 7)
        weeks.setdefault(sunday, [0] * 7)[(day - sunday).days] = stars
    result = [
        {"week": int(datetime(s.year, s.month, s.day, tzinfo=UTC).timestamp()),
         "total": sum(days), "days": days}
        for s, days in sorted(weeks.items(), reverse=True)
    ]
    return result[:per_page]


class FakeGitHub:
    def __init__(self, world):
        self.world = world
        self.requests = 0

    def __call__(self, request):
        self.requests += 1
        path = request.url.path
        if path == "/search/repositories":
            return self._search(request)
        if path == "/graphql":
            return self._graphql(request)
        parts = path.strip("/").split("/")
        if len(parts) == 5 and parts[0] == "repos" and parts[3:] == ["stargazers", "history"]:
            truth = self.world.get(f"{parts[1]}/{parts[2]}".lower())
            if truth is None:
                return httpx.Response(404, json={"message": "Not Found"})
            per_page = int(request.url.params.get("per_page", 30))
            return httpx.Response(200, json=history_weeks(truth, min(per_page, 30)))
        return httpx.Response(404, json={"message": "Not Found"})

    def _search(self, request):
        query = request.url.params["q"]
        day = date.fromisoformat(query.split("created:")[1].split()[0])
        found = [t for t in self.world.values() if t["created"] == day]
        found.sort(key=lambda t: -t["stars"])
        per_page = int(request.url.params.get("per_page", 30))
        page = int(request.url.params.get("page", 1))
        items = found[(page - 1) * per_page : page * per_page]
        return httpx.Response(200, json={
            "total_count": len(found), "incomplete_results": False,
            "items": [{"full_name": t["repo"]} for t in items],
        })

    def _graphql(self, request):
        variables = json.loads(request.content)["variables"]
        data, errors = {}, []
        for key in variables:
            if not key.startswith("owner"):
                continue
            suffix = key[len("owner"):]
            truth = self.world.get(f"{variables[key]}/{variables['name' + suffix]}".lower())
            data["r" + suffix] = node(truth) if truth else None
            if truth is None:
                errors.append({"type": "NOT_FOUND", "path": ["r" + suffix], "message": "Could not resolve"})
        payload = {"data": data}
        if errors:
            payload["errors"] = errors
        return httpx.Response(200, json=payload)


def collect(world):
    """Runs the real collection against the fake. Returns (request count, snapshots)."""
    fake = FakeGitHub(world)
    client = httpx.Client(transport=httpx.MockTransport(fake), base_url="https://api.github.com")
    clock, sleep = Clock(), lambda seconds: None
    with tempfile.TemporaryDirectory() as directory:
        store = JsonSnapshotStore(Path(directory))
        report = CollectSnapshots(
            candidate_sources=[GitHubSearchCandidates(client, sleep=sleep, clock=clock)],
            repo_source=GitHubRepoSource(client, sleep=sleep, clock=clock),
            snapshot_store=store,
            clock=clock,
        ).run()
        snapshots = store.load(TODAY)
    if report.failed or report.missing or report.source_errors:
        raise SystemExit(f"Lauf unvollständig: {len(report.failed)} fehlgeschlagen, "
                         f"{len(report.missing)} fehlend, {report.source_errors}")
    return fake.requests, snapshots


def can_be_shown(truth):
    """Repos that are excluded whatever their stars may leave out the star history."""
    return bool(truth["language"]) and not (truth["fork"] or truth["archived"] or truth["mirror"])


def as_json(snapshot):
    data = dataclasses.asdict(snapshot)
    data["repo"] = str(snapshot.repo)
    return json.loads(json.dumps(data, default=str, sort_keys=True))


def verify(mix):
    problems = []

    # 1. Fresh names and order: every repo is there, its facts and its stars per day are right.
    world = build_world(mix, seed=random.randrange(10**9))
    _, snapshots = collect(world)
    by_repo = {str(s.repo).lower(): s for s in snapshots}
    if set(by_repo) != set(world):
        problems.append(f"{len(set(world) - set(by_repo))} Repos fehlen, {len(set(by_repo) - set(world))} zu viel")
    for key, truth in world.items():
        snapshot = by_repo.get(key)
        if snapshot is None:
            continue
        if (snapshot.stars, snapshot.forks, snapshot.primary_language) != (
            truth["stars"], truth["forks"], truth["language"]
        ) or snapshot.created_at.date() != truth["created"]:
            problems.append(f"{truth['repo']}: Fakten falsch")
        if can_be_shown(truth):
            expected = tuple(
                truth["daily"].get(TODAY - timedelta(days=back), 0)
                for back in reversed(range(HISTORY_DAYS))
            )
            if snapshot.star_history.daily != expected:
                problems.append(f"{truth['repo']}: Sternverlauf falsch")

    # 2. Fixed names: the output equals the stored reference field by field.
    _, snapshots = collect(build_world(mix, seed=REFERENCE_SEED))
    reference = json.loads(REFERENCE.read_text())
    current = {str(s.repo).lower(): as_json(s) for s in snapshots}
    if set(current) != set(reference):
        problems.append("andere Repos als in der Referenz")
    for key, expected in reference.items():
        got = current.get(key)
        if got is None:
            continue
        if not expected["_can_be_shown"]:
            expected, got = dict(expected), dict(got)
            expected.pop("star_history"), got.pop("star_history")
        expected = {k: v for k, v in expected.items() if k != "_can_be_shown"}
        if got != expected:
            fields = [k for k in expected if got.get(k) != expected[k]]
            problems.append(f"{key}: weicht von der Referenz ab in {fields}")

    for problem in problems[:10]:
        print(problem)
    print(f"{len(problems)} Abweichungen")
    return 1 if problems else 0


def write_reference(mix):
    world = build_world(mix, seed=REFERENCE_SEED)
    _, snapshots = collect(world)
    reference = {}
    for snapshot in snapshots:
        key = str(snapshot.repo).lower()
        reference[key] = {**as_json(snapshot), "_can_be_shown": can_be_shown(world[key])}
    REFERENCE.write_text(json.dumps(reference, indent=0, sort_keys=True) + "\n")
    print(f"Referenz mit {len(reference)} Repos geschrieben")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--write-reference", action="store_true")
    parser.add_argument("--mix", type=Path)
    args = parser.parse_args()
    mix = json.loads(args.mix.read_text()) if args.mix else synthetic_mix()
    if args.write_reference:
        return write_reference(synthetic_mix())
    if args.verify:
        return verify(synthetic_mix())
    requests, snapshots = collect(build_world(mix, seed=random.randrange(10**9)))
    print(f"{len(snapshots)} Momentaufnahmen")
    print(requests)


if __name__ == "__main__":
    sys.exit(main())
