"""Edition files as Publication sees them: plain JSON. See docs/ausgabe.md and docs/community.md."""

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
            {
                "kind": "momentum",
                "weight": 40.0,
                "reason": "+120 Sterne in 14 Tagen bei 91.943 insgesamt",
            },
            {
                "kind": "ai_files",
                "weight": -3.0,
                "reason": "Anweisungsdateien für AI-Agenten: AGENTS.md",
            },
            {"kind": "ai_focus", "weight": 0, "reason": "Beschreibung: AI-Begriffe „ai“"},
        ],
    }
    entry.update(overrides)
    return entry


def edition_json(day="2026-11-12", main=None, ai=None, **overrides):
    edition = {
        "format_version": 1,
        "day": day,
        "growth_window_days": 14,
        "stats": {"assessed": 1834, "excluded": 420, "ai_focused": 212},
        "sections": {
            "main": [entry_json()] if main is None else main,
            "ai": [entry_json("bob/agent-kit", language="Python")] if ai is None else ai,
        },
    }
    edition.update(overrides)
    return edition


def project_json(title="Tiny Editor 1.0", repo="https://github.com/alice/tiny-editor", **overrides):
    project = {
        "story": {
            "id": "4711",
            "title": title,
            "url": repo,
            "points": 321,
            "comments": 45,
            "created_at": "2026-11-12T03:00:00+00:00",
        },
        "repository_url": repo,
        "project_url": repo,
        "description": "A tiny terminal text editor",
        "language": "Rust",
        "license_id": "MIT",
        "is_fork": False,
        "is_archived": False,
        "has_code": True,
        "topics": ["editor"],
        "linked_directly": True,
        "reasons": ["Die Story verlinkt das Repo direkt."],
    }
    project.update(overrides)
    return project


def community_edition_json(day="2026-11-12", projects=None, ai_projects=None):
    return {
        "format_version": 1,
        "day": day,
        "projects": [project_json()] if projects is None else projects,
        "ai_projects": [] if ai_projects is None else ai_projects,
    }


def write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_edition(data_dir: Path, edition: dict) -> Path:
    return write_json(data_dir / "editions" / f"{edition['day']}.json", edition)


def write_community_edition(data_dir: Path, slug: str, edition: dict) -> Path:
    return write_json(data_dir / f"{slug}-editions" / f"{edition['day']}.json", edition)
