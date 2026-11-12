"""Command line entry point and composition root: plugs adapters into the use cases."""

import argparse
import logging
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from github_anti_ai.adapters.clock import SystemClock
from github_anti_ai.adapters.github_http import make_github_client
from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.adapters.github_search import GitHubSearchCandidates
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.application.collect_snapshots import CollectionReport, CollectSnapshots
from github_anti_ai.application.ports import SourceUnavailable


class MissingToken(Exception):
    pass


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="github-anti-ai", description="Explore-Seite für menschengemachte GitHub-Repos"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("collect", "Momentaufnahmen sammeln"),
        ("publish", "heutige Ausgabe erzeugen"),
        ("daily", "sammeln und Ausgabe erzeugen"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--data-dir", type=Path, default=Path("data"))
        if name != "publish":
            command.add_argument(
                "--limit",
                type=int,
                default=None,
                help="höchstens so viele Kandidaten (für Probeläufe)",
            )
        if name != "collect":
            command.add_argument(
                "--ignore-cooldown",
                action="store_true",
                help="Sperre ignorieren (nur für die Entwicklung)",
            )
    return parser.parse_args(argv)


def load_token(environ: Mapping[str, str], dotenv_path: Path) -> str:
    if environ.get("GITHUB_TOKEN"):
        return environ["GITHUB_TOKEN"].strip()
    if dotenv_path.exists():
        for line in dotenv_path.read_text().splitlines():
            key, separator, value = line.partition("=")
            value = value.strip().strip("\"'")
            if separator and key.strip() == "GITHUB_TOKEN" and value:
                return value
    raise MissingToken("GITHUB_TOKEN fehlt: als Umgebungsvariable setzen oder in .env eintragen")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S", stream=sys.stderr
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    complete = True
    try:
        if args.command in ("collect", "daily"):
            report = collect(args.data_dir, load_token(os.environ, Path(".env")), args.limit)
            complete = not report.failed
        if args.command in ("publish", "daily"):
            # PublishEdition needs the Assessment context, which does not exist yet.
            # "daily" must then publish for report.day, not for the day the clock shows.
            print("Ausgabe erzeugen geht erst, wenn es die Bewertung gibt.", file=sys.stderr)
            return 2
    except (MissingToken, SourceUnavailable) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1
    return 0 if complete else 1


def collect(data_dir: Path, token: str, limit: int | None) -> CollectionReport:
    clock = SystemClock()
    with make_github_client(token) as client:
        use_case = CollectSnapshots(
            candidate_sources=[GitHubSearchCandidates(client, sleep=time.sleep, clock=clock)],
            repo_source=GitHubRepoSource(client, sleep=time.sleep, clock=clock),
            snapshot_store=JsonSnapshotStore(data_dir / "snapshots"),
            clock=clock,
            limit=limit,
        )
        report = use_case.run()
    print(f"{report.day}: {report.discovered} Kandidaten, {report.collected} Momentaufnahmen")
    if report.missing:
        print(f"  {len(report.missing)} nicht gefunden: {_names(report.missing)}")
    if report.failed:
        print(f"  {len(report.failed)} fehlgeschlagen, ein erneuter Lauf holt sie nach")
    for error in report.source_errors + report.fetch_errors:
        print(f"  Fehler: {error}")
    return report


def _names(repos: Sequence, shown: int = 5) -> str:
    names = ", ".join(str(repo) for repo in repos[:shown])
    return names + (" …" if len(repos) > shown else "")


if __name__ == "__main__":
    sys.exit(main())
