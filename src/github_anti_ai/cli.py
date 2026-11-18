"""Command line and composition root: plugs the adapters into the use cases.

See README.md for the commands.
"""

import argparse
import logging
import os
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from datetime import date
from pathlib import Path

import httpx

from github_anti_ai.adapters.clock import SystemClock
from github_anti_ai.adapters.copilot_reviewer import CopilotReviewer
from github_anti_ai.adapters.forum_sources import (
    LEMMY_URL,
    LOBSTERS_URL,
    MASTODON_URL,
    ForumStories,
    LemmyCommunities,
    LobstersNewest,
    MastodonTags,
)
from github_anti_ai.adapters.github_http import make_github_client
from github_anti_ai.adapters.github_repo_source import GitHubRepoSource
from github_anti_ai.adapters.github_search import GitHubSearchCandidates
from github_anti_ai.adapters.json_collection_status_store import JsonCollectionStatusStore
from github_anti_ai.adapters.json_community_edition_store import JsonCommunityEditionStore
from github_anti_ai.adapters.json_daily_record_store import JsonDailyRecordStore
from github_anti_ai.adapters.json_edition_store import JsonEditionStore
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.adapters.project_resolver import ProjectResolver
from github_anti_ai.adapters.story_sources import HN_API_URL, HackerNewsSearch
from github_anti_ai.application.collect_community_edition import CollectCommunityEdition
from github_anti_ai.application.collect_snapshots import CollectionReport, CollectSnapshots
from github_anti_ai.application.explain_assessment import ExplainAssessment, UnknownRepo
from github_anti_ai.application.ports import (
    AlreadyPublished,
    IncompleteCollection,
    NothingToPublish,
    SourceUnavailable,
)
from github_anti_ai.application.publish_edition import PublishEdition, reviewed_entries
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.community import (
    FORUMS,
    HN,
    LEMMY_COMMUNITIES,
    MASTODON_TAGS,
    Platform,
)
from github_anti_ai.domain.model import RepoId

USER_AGENT = "github-anti-ai"


class MissingToken(Exception):
    pass


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="github-anti-ai", description="Explore-Seite für menschengemachte Open-Source-Projekte"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help)
        sub.add_argument("--data-dir", type=Path, default=Path("data"))
        return sub

    def limit(sub):
        sub.add_argument("--limit", type=int, help="höchstens so viele Kandidaten (für Probeläufe)")

    def day(sub):
        sub.add_argument(
            "--day",
            type=date.fromisoformat,
            help="Tag der Sammlung als JJJJ-MM-TT (Standard: heute)",
        )

    def publishing(sub):
        sub.add_argument(
            "--ignore-cooldown",
            action="store_true",
            help="Sperre ignorieren (nur für die Entwicklung)",
        )
        sub.add_argument(
            "--allow-incomplete",
            action="store_true",
            help="Ausgabe auch aus einer unvollständigen Sammlung erzeugen",
        )
        sub.add_argument(
            "--review",
            action="store_true",
            help="die Repos der Ausgabe von der Copilot-CLI gegenlesen lassen",
        )

    def output(sub):
        sub.add_argument("--output", type=Path, default=Path("output"))

    limit(command("collect", "Momentaufnahmen von GitHub sammeln"))
    publish = command("publish", "Ausgabe des Tages erzeugen")
    day(publish)
    publishing(publish)
    daily = command("daily", "sammeln und Ausgabe erzeugen")
    limit(daily)
    publishing(daily)
    limit(command("collect-hn", "HN-Ausgabe erzeugen"))
    limit(command("collect-forums", "Wochenausgabe der Foren erzeugen (Lobsters, Lemmy, Mastodon)"))
    explain = command("explain", "Bewertung eines Repos erklären")
    explain.add_argument("repo", help="besitzer/name")
    day(explain)
    site = command("site", "Website aus den Ausgaben bauen")
    output(site)
    site.add_argument(
        "--site-url", help="öffentliche Adresse der Seite, für vollständige Links in den Feeds"
    )
    site.add_argument("--plausible", help="Adresse eines Plausible-Skripts, das die Besuche zählt")
    serve = command("serve", "Vorschau der Website, baut bei Änderungen neu")
    output(serve)
    serve.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def load_token(environ: Mapping[str, str], dotenv: Path) -> str:
    """GITHUB_TOKEN from the environment, otherwise from a line GITHUB_TOKEN=… in .env"""
    if environ.get("GITHUB_TOKEN"):
        return environ["GITHUB_TOKEN"].strip()
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
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
    try:
        return COMMANDS[args.command](args)
    except AlreadyPublished as error:
        _fail(f"Für den {error} gibt es schon eine Ausgabe.")
    except NothingToPublish as error:
        _fail(f"Für den {error} gibt es keine Momentaufnahmen.")
    except IncompleteCollection as error:
        _fail(
            f"{error}\n  Mit 'collect' holt ein erneuter Lauf nach, was fehlt. "
            "Mit --allow-incomplete entsteht die Ausgabe trotzdem."
        )
    except (MissingToken, SourceUnavailable, UnknownRepo, ValueError) as error:
        _fail(str(error))
    return 1


def _fail(message: str) -> None:
    print(f"Fehler: {message}", file=sys.stderr)


def _token() -> str:
    return load_token(os.environ, Path(".env"))


def run_collect(args) -> int:
    report = collect(args.data_dir, _token(), args.limit)
    return 1 if report.failed else 0


def run_publish(args) -> int:
    publish(args, args.day or SystemClock().now().date())
    return 0


def run_daily(args) -> int:
    report = collect(args.data_dir, _token(), args.limit)
    # a run across midnight belongs to the day it began
    publish(args, report.day)  # refuses an incomplete collection unless allowed
    return 1 if report.failed else 0


def run_collect_hn(args) -> int:
    return collect_community(args, HN, lambda client: HackerNewsSearch(client(base_url=HN_API_URL)))


def run_collect_forums(args) -> int:
    def stories(client) -> ForumStories:
        return ForumStories(
            [
                LobstersNewest(client(base_url=LOBSTERS_URL), sleep=time.sleep),
                LemmyCommunities(client(base_url=LEMMY_URL), LEMMY_COMMUNITIES),
                MastodonTags(client(base_url=MASTODON_URL), MASTODON_TAGS),
            ]
        )

    return collect_community(args, FORUMS, stories)


def run_explain(args) -> int:
    use_case = ExplainAssessment(JsonSnapshotStore(args.data_dir / "snapshots"), Assessor().assess)
    day = args.day or SystemClock().now().date()
    print(use_case.run(day, RepoId.parse(args.repo)))
    return 0


def run_site(args) -> int:
    from github_anti_ai.publication.site import build_site  # only these commands need Pelican

    build_site(args.data_dir, args.output, args.site_url, args.plausible)
    print(f"Website gebaut: {args.output}/index.html")
    return 0


def run_serve(args) -> int:
    from github_anti_ai.publication.dev_server import serve
    from github_anti_ai.publication.site import THEME, build_site

    logging.getLogger().setLevel(logging.WARNING)  # Pelican is chatty on every rebuild
    watched = ["editions", "hn-editions", "lobsters-editions", "forums-editions"]
    serve(
        build=lambda: build_site(args.data_dir, args.output),
        watch=[args.data_dir / name for name in watched] + [THEME],
        output_dir=args.output,
        port=args.port,
    )
    return 0


COMMANDS = {
    "collect": run_collect,
    "publish": run_publish,
    "daily": run_daily,
    "collect-hn": run_collect_hn,
    "collect-forums": run_collect_forums,
    "explain": run_explain,
    "site": run_site,
    "serve": run_serve,
}


def collect(data_dir: Path, token: str, limit: int | None) -> CollectionReport:
    clock = SystemClock()
    snapshots = data_dir / "snapshots"
    with make_github_client(token) as client:
        report = CollectSnapshots(
            candidate_sources=[GitHubSearchCandidates(client, sleep=time.sleep, clock=clock)],
            repo_source=GitHubRepoSource(client, sleep=time.sleep, clock=clock),
            snapshot_store=JsonSnapshotStore(snapshots),
            status_store=JsonCollectionStatusStore(snapshots),
            clock=clock,
            assess=Assessor().assess,
            limit=limit,
        ).run()
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


def publish(args, day: date) -> None:
    data_dir = args.data_dir
    edition = PublishEdition(
        snapshot_store=JsonSnapshotStore(data_dir / "snapshots"),
        status_store=JsonCollectionStatusStore(data_dir / "snapshots"),
        edition_store=JsonEditionStore(data_dir / "editions"),
        record_store=JsonDailyRecordStore(data_dir / "history"),
        assess=Assessor().assess,
        reviewer=CopilotReviewer() if args.review else None,
        ignore_cooldown=args.ignore_cooldown,
        allow_incomplete=args.allow_incomplete,
    ).run(day)
    stats = edition.stats
    print(
        f"Ausgabe {edition.day}: {len(edition.main)} in der Hauptliste, "
        f"{len(edition.ai)} in der AI-Sektion "
        f"({stats.assessed} geprüft, {stats.excluded} ausgeschlossen)"
    )
    if args.review:
        read, shown = reviewed_entries(edition)
        print(f"Gegengelesen: {read} von {shown} Einträgen")


def collect_community(args, platform: Platform, stories) -> int:
    """`stories` makes the story source from a function that opens HTTP clients."""
    with ExitStack() as stack:

        def client(**options) -> httpx.Client:
            return stack.enter_context(
                httpx.Client(
                    headers={"User-Agent": USER_AGENT}, timeout=10, trust_env=False, **options
                )
            )

        github_client = stack.enter_context(make_github_client(_token()))
        edition = CollectCommunityEdition(
            platform=platform,
            story_source=stories(client),
            resolver=ProjectResolver(client(), github_client=github_client),
            edition_store=JsonCommunityEditionStore(platform, args.data_dir),
            clock=SystemClock(),
            limit=args.limit,
        ).run()
    print(
        f"{platform.name}-Ausgabe {edition.day}: {len(edition.main)} Projekte, "
        f"{len(edition.ai)} AI-Projekte"
    )
    return 0


def _names(repos: Sequence, shown: int = 5) -> str:
    names = ", ".join(str(repo) for repo in repos[:shown])
    return names + (" …" if len(repos) > shown else "")


if __name__ == "__main__":
    sys.exit(main())
