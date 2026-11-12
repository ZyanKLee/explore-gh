"""Turns the judged repos into a test fixture without names and e-mail addresses of people.

    uv run python checks/make_labelled_examples.py data-test/snapshots/2026-11-12.jsonl.gz \\
        data-test/urteile.csv

Writes tests/integration/fixtures/labelled/: the snapshots of the judged repos and the
verdicts (without the notes). Commit authors become "person-1", "person-2" …, co-authors
who are not AI tools become a placeholder, commit headlines and e-mail addresses in
READMEs are removed. AI tools and bots stay as they are, the rules need them.
"""

import csv
import dataclasses
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from github_anti_ai.adapters.json_snapshot_store import SUFFIX, JsonSnapshotStore
from github_anti_ai.domain.ai_assistance import is_ai_assisted, is_ai_tool
from github_anti_ai.domain.model import RepoId, Snapshot

TARGET = Path(__file__).parent.parent / "tests/integration/fixtures/labelled"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def anonymous(snapshot: Snapshot) -> Snapshot:
    people: dict[str, str] = {}

    def commit(c):
        author = c.author
        if not c.is_bot and not is_ai_assisted(dataclasses.replace(c, co_authors=())):
            author = people.setdefault(c.author, f"person-{len(people) + 1}")
        co_authors = tuple(
            a if is_ai_tool(a) else "Person <person@example.org>" for a in c.co_authors
        )
        return dataclasses.replace(c, author=author, co_authors=co_authors, headline="")

    return dataclasses.replace(
        snapshot,
        readme=EMAIL.sub("[email]", snapshot.readme),
        description=EMAIL.sub("[email]", snapshot.description),
        recent_commits=tuple(commit(c) for c in snapshot.recent_commits),
    )


def main(snapshot_file: Path, verdict_file: Path) -> None:
    day = date.fromisoformat(snapshot_file.name.removesuffix(SUFFIX))
    with verdict_file.open(newline="") as file:
        verdicts = list(csv.DictReader(file))
    judged = {RepoId.parse(row["repo"]) for row in verdicts}
    snapshots = [s for s in JsonSnapshotStore(snapshot_file.parent).load(day) if s.repo in judged]

    shutil.rmtree(TARGET, ignore_errors=True)
    JsonSnapshotStore(TARGET).append(day, [anonymous(s) for s in snapshots])
    with (TARGET / "urteile.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["repo", "ai_thema", "urteil"])
        writer.writerows([row["repo"], row["ai_thema"], row["urteil"]] for row in verdicts)
    print(f"{len(snapshots)} Momentaufnahmen und {len(verdicts)} Urteile nach {TARGET}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
