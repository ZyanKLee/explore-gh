"""The withdrawn repos as the pages need them: address -> note.

Reads data/withdrawn.json, the same file the collection uses. See docs/ausgabe.md,
"Zurückziehen".
"""

import json
from datetime import date
from pathlib import Path

FORMAT_VERSION = 1


def load_withdrawn(path: Path | str | None) -> dict[str, str]:
    """The note of each withdrawn repo by its address. No file: nothing withdrawn."""
    if path is None or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"{Path(path).name}: unbekannte format_version")
    return {
        url_key(item["repository_url"]): (
            f"Zurückgezogen am {date.fromisoformat(item['day']):%d.%m.%Y}: {item['reason']}"
        )
        for item in data["withdrawals"]
    }


def url_key(url: str) -> str:
    return url.rstrip("/").casefold()
