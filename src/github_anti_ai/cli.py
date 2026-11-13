"""Command line entry point and composition root: plugs adapters into the use cases."""

import argparse
import logging
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from github_anti_ai.adapters.clock import SystemClock
from github_anti_ai.adapters.github_http import make_github_client
from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.adapters.github_search import GitHubSearchCandidates
from github_anti_ai.adapters.json_collection_status_store import JsonCollectionStatusStore
from github_anti_ai.adapters.json_edition_store import JsonEditionStore
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.application.collect_snapshots import CollectionReport, CollectSnapshots
from github_anti_ai.application.explain_assessment import ExplainAssessment, UnknownRepo
from github_anti_ai.application.ports import (
    AlreadyPublished,
    IncompleteCollection,
    NothingToPublish,
    SourceUnavailable,
)
from github_anti_ai.application.publish_edition import PublishEdition
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.edition import Edition
from github_anti_ai.domain.model import RepoId


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
        ("site", "Website aus den Ausgaben bauen"),
        ("explain", "Bewertung eines Repos erklären"),
        ("serve", "Vorschau der Website mit automatischem Neuladen"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--data-dir", type=Path, default=Path("data"))
        if name in ("site", "serve"):
            command.add_argument("--output", type=Path, default=Path("output"))
        if name == "serve":
            command.add_argument("--port", type=int, default=8000)
        if name == "site":
            command.add_argument(
                "--site-url",
                default=None,
                help="öffentliche Adresse der Seite, für vollständige Links in den Feeds",
            )
            command.add_argument(
                "--plausible",
                default=None,
                help="Adresse eines Plausible-Skripts, das die Besuche zählt",
            )
        if name == "explain":
            command.add_argument("repo", help="owner/name")
        if name in ("publish", "explain"):
            command.add_argument(
                "--day",
                type=date.fromisoformat,
                default=None,
                help="Tag der Sammlung als JJJJ-MM-TT (Standard: heute)",
            )
        if name in ("collect", "daily"):
            command.add_argument(
                "--limit",
                type=int,
                default=None,
                help="höchstens so viele Kandidaten (für Probeläufe)",
            )
        if name in ("publish", "daily"):
            command.add_argument(
                "--ignore-cooldown",
                action="store_true",
                help="Sperre ignorieren (nur für die Entwicklung)",
            )
            command.add_argument(
                "--allow-incomplete",
                action="store_true",
                help="Ausgabe auch aus einer unvollständigen Sammlung erzeugen",
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
    if args.command == "site":
        # imported here: only this command needs Pelican
        from github_anti_ai.publication.site import build_site

        build_site(args.data_dir / "editions", args.output, args.site_url, args.plausible)
        print(f"Website gebaut: {args.output}/index.html")
        return 0
    if args.command == "serve":
        from github_anti_ai.publication.dev_server import serve
        from github_anti_ai.publication.site import THEME, build_site

        logging.getLogger().setLevel(logging.WARNING)  # Pelican is chatty on every rebuild
        editions = args.data_dir / "editions"
        serve(
            build=lambda: build_site(editions, args.output),
            watch=[editions, THEME],
            output_dir=args.output,
            port=args.port,
        )
        return 0
    try:
        if args.command == "explain":
            print(explain(args.data_dir, args.day, args.repo))
            return 0
        day = getattr(args, "day", None)
        if args.command in ("collect", "daily"):
            report = collect(args.data_dir, load_token(os.environ, Path(".env")), args.limit)
            complete = not report.failed
            day = report.day  # a run across midnight still belongs to the day it started
        if args.command in ("publish", "daily"):
            publish(args.data_dir, day, args.ignore_cooldown, args.allow_incomplete)
    except AlreadyPublished as error:
        print(f"Fehler: Für den {error} gibt es schon eine Ausgabe.", file=sys.stderr)
        return 1
    except IncompleteCollection as error:
        print(f"Fehler: {error}", file=sys.stderr)
        print(
            "  Mit 'collect' holt ein erneuter Lauf nach, was fehlt. "
            "Mit --allow-incomplete entsteht die Ausgabe trotzdem.",
            file=sys.stderr,
        )
        return 1
    except NothingToPublish as error:
        print(f"Fehler: Für den {error} gibt es keine Momentaufnahmen.", file=sys.stderr)
        return 1
    except (MissingToken, SourceUnavailable, UnknownRepo, ValueError) as error:
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
            assess=Assessor().assess,
            limit=limit,
            status_store=JsonCollectionStatusStore(data_dir / "snapshots"),
        )
        report = use_case.run()
    print(f"{report.day}: {report.discovered} Kandidaten, {report.collected} Momentaufnahmen")
    print(
        f"  {report.fetched} neu geholt, {report.refreshed} aufgefrischt, "
        f"{report.carried_over} übernommen"
    )
    if report.missing:
        print(f"  {len(report.missing)} nicht gefunden: {_names(report.missing)}")
    if report.failed:
        print(f"  {len(report.failed)} fehlgeschlagen, ein erneuter Lauf holt sie nach")
    for error in report.source_errors + report.fetch_errors:
        print(f"  Fehler: {error}")
    return report


def publish(
    data_dir: Path, day: date | None, ignore_cooldown: bool, allow_incomplete: bool = False
) -> Edition:
    use_case = PublishEdition(
        snapshot_store=JsonSnapshotStore(data_dir / "snapshots"),
        edition_store=JsonEditionStore(data_dir / "editions"),
        collection_status_store=JsonCollectionStatusStore(data_dir / "snapshots"),
        assess=Assessor().assess,
        clock=SystemClock(),
        ignore_cooldown=ignore_cooldown,
        allow_incomplete=allow_incomplete,
    )
    edition = use_case.run(day)
    stats = edition.stats
    print(
        f"Ausgabe {edition.day}: {len(edition.main)} in der Hauptliste, "
        f"{len(edition.ai)} in der AI-Sektion "
        f"({stats.assessed} geprüft, {stats.excluded} ausgeschlossen)"
    )
    return edition


def explain(data_dir: Path, day: date | None, repo: str) -> str:
    use_case = ExplainAssessment(
        snapshot_store=JsonSnapshotStore(data_dir / "snapshots"), assess=Assessor().assess
    )
    return use_case.run(day or SystemClock().now().date(), RepoId.parse(repo))


def _names(repos: Sequence, shown: int = 5) -> str:
    names = ", ".join(str(repo) for repo in repos[:shown])
    return names + (" …" if len(repos) > shown else "")


if __name__ == "__main__":
    sys.exit(main())
