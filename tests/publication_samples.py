"""Edition files as the Publication context sees them: plain JSON, see docs/ausgabe.md."""

import json
from pathlib import Path


def entry_json(repo="alice/tiny-editor", rank=1, **overrides):
    entry = {
        "rank": rank,
        "repo": repo,
        "url": f"https://github.com/{repo}",
        "description": "A tiny terminal text editor",
        "homepage": None,
        "language": "Rust",
        "topics": ["editor", "terminal"],
        "stars": 91943,
        "stars_gained": 120,
        "star_history": [0] * 28 + [10, 20, 30, 15, 15, 20, 10],
        "created_at": "2026-10-20T12:00:00Z",
        "pushed_at": "2026-11-10T19:02:11Z",
        "license": "MIT",
        "forks": 31,
        "active_authors": 2,
        "score": 37.0,
        "signals": [
            {"kind": "momentum", "weight": 40.0, "reason": "+120 Sterne in 7 Tagen bei 91.943 insgesamt"},
            {"kind": "ai_files", "weight": -3.0, "reason": "Anweisungsdateien für AI-Agenten: AGENTS.md"},
            {"kind": "ai_focus", "weight": 0, "reason": "Beschreibung nennt „AI“"},
        ],
    }
    entry.update(overrides)
    return entry


def edition_json(day="2026-11-12", main=None, ai=None, **overrides):
    edition = {
        "format_version": 1,
        "day": day,
        "stats": {"assessed": 1834, "excluded": 420, "ai_focused": 212},
        "sections": {
            "main": [entry_json()] if main is None else main,
            "ai": [entry_json("bob/agent-kit", language="Python")] if ai is None else ai,
        },
    }
    edition.update(overrides)
    return edition


def write_edition(directory: Path, edition: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{edition['day']}.json"
    path.write_text(json.dumps(edition, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
