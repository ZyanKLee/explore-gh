"""What a change of the rules does: assesses the stored snapshots with two versions of the
code and lists every difference. Asks no API, writes nothing.

    uv run python checks/compare_rules.py                    # working tree against HEAD
    uv run python checks/compare_rules.py --against main     # against another git ref
    uv run python checks/compare_rules.py --day 2026-11-15 --show 30

Compared are section, exclusion, score with the signals behind it, and the places in the
edition the day would get (without cooldown and review). Both versions read the snapshots
with their own code. A version from before 2026-11-17 cannot read snapshots written later.
"""

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).parent.parent
SECTIONS = {"main": "Hauptliste", "ai": "AI-Sektion"}
MIN_SCORE_CHANGE = 0.05  # less is rounding

# Runs in a separate Python with the code of one version first on its path.
DUMP = r"""
import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from github_anti_ai.adapters.json_snapshot_store import JsonSnapshotStore
from github_anti_ai.domain.assessor import Assessor
from github_anti_ai.domain.copies import CopyCheck
from github_anti_ai.domain.edition import EditionCurator

store = JsonSnapshotStore(Path(sys.argv[2]))
assessor = Assessor()
result = {}
for text in sys.argv[3:]:
    day = date.fromisoformat(text)
    assessments = CopyCheck().apply([assessor.assess(s) for s in store.load(day)])
    edition = EditionCurator().curate(day, assessments, [])
    ranks = {}
    for entries in (edition.main, edition.ai):
        for place, entry in enumerate(entries, start=1):
            ranks[str(entry.repo)] = place
    result[text] = {
        str(a.repo): {
            "section": a.section.value,
            "score": a.score,
            "exclusion": a.exclusion.kind if a.exclusion else None,
            "reason": a.exclusion.reason if a.exclusion else None,
            "rank": ranks.get(str(a.repo)),
            "signals": [[s.kind, s.weight, s.reason] for s in a.signals],
        }
        for a in assessments
    }
json.dump(result, sys.stdout, ensure_ascii=False)
"""


def assess_with(src: Path, snapshots: Path, days: list[str]) -> dict:
    """Assessments by day and repo, made by the code in `src`."""
    result = subprocess.run(
        [sys.executable, "-P", "-c", DUMP, str(src), str(snapshots), *days],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Bewerten mit {src} gescheitert:\n{result.stderr.strip()}")
    return json.loads(result.stdout)


def source_of(ref: str, into: Path) -> Path:
    """The src directory of a git ref, unpacked into `into`."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref, "src"], cwd=ROOT, capture_output=True, check=False
    )
    if archive.returncode != 0:
        raise SystemExit(f"git kennt {ref!r} nicht: {archive.stderr.decode().strip()}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(into, filter="data")
    return into / "src"


def compare(before: dict, after: dict, show: int = 10) -> str:
    """The differences as a report for the terminal, day by day."""
    lines: list[str] = []
    changed_repos: set[tuple[str, str]] = set()
    changed_days = 0
    for day in sorted(set(before) & set(after)):
        old_day, new_day = before[day], after[day]
        repos = sorted(set(old_day) & set(new_day), key=str.lower)
        groups = _differences(repos, old_day, new_day)
        if not any(groups.values()):
            continue
        changed_days += 1
        lines += ["", f"{day} ({len(repos)} Repos)"]
        for title, items in groups.items():
            if not items:
                continue
            lines.append(f"  {title}")
            for repo, text in items[:show]:
                lines.append(f"    {text}")
                changed_repos.add((day, repo))
            for repo, _ in items[show:]:
                changed_repos.add((day, repo))
            if len(items) > show:
                lines.append(f"    … und {len(items) - show} weitere")
    if not changed_repos:
        return "\n".join([*lines, "Keine Unterschiede."]).strip()
    repos_word = "Repo" if len(changed_repos) == 1 else "Repos"
    days_word = "Tag" if changed_days == 1 else "Tagen"
    lines += [
        "",
        f"Insgesamt: {len(changed_repos)} {repos_word} mit Unterschieden an {changed_days} {days_word}.",
    ]
    return "\n".join(lines).strip()


def _differences(repos: list[str], old_day: dict, new_day: dict) -> dict[str, list]:
    """Each group holds (repo, line) pairs, in the order they are shown."""
    section, excluded, lifted, other_reason, scores = [], [], [], [], []
    added, dropped, moved = [], [], []
    for repo in repos:
        old, new = old_day[repo], new_day[repo]
        if old["section"] != new["section"]:
            section.append(
                (repo, f"{repo}  {SECTIONS[old['section']]} → {SECTIONS[new['section']]}")
            )
        if old["exclusion"] is None and new["exclusion"] is not None:
            excluded.append((repo, f"{repo}  {new['exclusion']}: {new['reason']}"))
        elif old["exclusion"] is not None and new["exclusion"] is None:
            lifted.append((repo, f"{repo}  war {old['exclusion']}: {old['reason']}"))
        elif old["exclusion"] != new["exclusion"]:
            other_reason.append((repo, f"{repo}  {old['exclusion']} → {new['exclusion']}"))
        change = new["score"] - old["score"]
        if abs(change) >= MIN_SCORE_CHANGE:
            text = f"{repo}  {_decimal(old['score'])} → {_decimal(new['score'])}"
            if signals := _signal_changes(old["signals"], new["signals"]):
                text += f"  ({signals})"
            scores.append((-abs(change), repo, text))
        old_place, new_place = _place(old), _place(new)
        if new_place and not old_place:
            added.append((repo, f"+ {repo}  {new_place}"))
        elif old_place and not new_place:
            dropped.append((repo, f"− {repo}  war {old_place}"))
        elif old_place != new_place:
            same_section = old["section"] == new["section"]
            moved.append(
                (repo, f"{repo}  {old_place} → {new['rank'] if same_section else new_place}")
            )
    # what changes on the page first, then why
    return {
        f"Neu in der Ausgabe: {len(added)}": added,
        f"Nicht mehr in der Ausgabe: {len(dropped)}": dropped,
        f"Anderer Platz in der Ausgabe: {len(moved)}": moved,
        f"Sektion gewechselt: {len(section)}": section,
        f"Neu ausgeschlossen: {len(excluded)}": excluded,
        f"Nicht mehr ausgeschlossen: {len(lifted)}": lifted,
        f"Anderer Ausschlussgrund: {len(other_reason)}": other_reason,
        f"Punktzahl geändert: {len(scores)}": [(r, t) for _, r, t in sorted(scores)],
    }


def _place(assessment: dict) -> str | None:
    if assessment["rank"] is None:
        return None
    return f"{SECTIONS[assessment['section']]} Platz {assessment['rank']}"


def _signal_changes(old: list, new: list) -> str:
    """`kind old → new` for each kind of signal whose weight changed; – for missing."""
    old_weights, new_weights = _weights(old), _weights(new)
    changes = []
    for kind in dict.fromkeys([*old_weights, *new_weights]):
        before, after = old_weights.get(kind), new_weights.get(kind)
        if before is None or after is None or abs(after - before) >= MIN_SCORE_CHANGE:
            changes.append(f"{kind} {_weight(before)} → {_weight(after)}")
    return ", ".join(changes)


def _weights(signals: list) -> dict[str, float]:
    weights: dict[str, float] = defaultdict(float)
    for kind, weight, _ in signals:
        weights[kind] += weight
    return dict(weights)


def _decimal(value: float) -> str:
    text = f"{abs(value):.1f}".replace(".", ",")
    return f"−{text}" if value < 0 else text


def _weight(value: float | None) -> str:
    if value is None:
        return "–"
    return f"+{_decimal(value)}" if value > 0 else _decimal(value) if value < 0 else "0"


def stored_days(snapshots: Path) -> list[str]:
    return sorted(p.name.removesuffix(".jsonl.gz") for p in snapshots.glob("????-??-??.jsonl.gz"))


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--against", default="HEAD", help="git-Stand zum Vergleich (Standard: HEAD)"
    )
    parser.add_argument(
        "--day", action="append", help="nur diesen Tag (JJJJ-MM-TT), mehrfach möglich"
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--show", type=int, default=10, help="höchstens so viele Zeilen je Gruppe")
    args = parser.parse_args(argv)

    snapshots = args.data_dir / "snapshots"
    days = args.day or stored_days(snapshots)
    if not days:
        raise SystemExit(f"Keine Momentaufnahmen in {snapshots}")
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor() as pool:
        # both versions at once: each runs in its own Python
        before = pool.submit(assess_with, source_of(args.against, Path(tmp)), snapshots, days)
        after = pool.submit(assess_with, ROOT / "src", snapshots, days)
        before, after = before.result(), after.result()
    assessed = sum(len(repos) for repos in after.values())
    days_word = "Tag" if len(days) == 1 else "Tage"
    print(f"Arbeitsstand gegen {args.against}: {len(days)} {days_word}, {assessed} Bewertungen")
    print(compare(before, after, args.show))


if __name__ == "__main__":
    main(sys.argv[1:])
