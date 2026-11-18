"""Helpers for the stores that keep one file per day."""

import json
from datetime import date
from pathlib import Path


def day_files(directory: Path, suffix: str) -> dict[date, Path]:
    """The files named YYYY-MM-DD<suffix>, by day. Other files are ignored."""
    directory = Path(directory)
    if not directory.exists():
        return {}
    found = {}
    for path in directory.glob(f"*{suffix}"):
        try:
            found[date.fromisoformat(path.name.removesuffix(suffix))] = path
        except ValueError:
            continue
    return dict(sorted(found.items()))


def write_new_json(path: Path, data: dict) -> bool:
    """Writes readable JSON to a file that must not exist yet. False if it does."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(text)
    except FileExistsError:
        return False
    return True


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
