"""The withdrawn repos: data/withdrawn.json, written by hand and versioned.

{"format_version": 1, "withdrawals": [{"repository_url": "https://github.com/a/x",
 "day": "2026-11-21", "reason": "Verteilt fremde Spieldaten"}]}

See docs/ausgabe.md, "Zurückziehen".
"""

import json
from datetime import date
from pathlib import Path

from explore_gh.domain.withdrawal import Withdrawal

FORMAT_VERSION = 1


class JsonWithdrawalStore:
    def __init__(self, path: Path):
        self._path = Path(path)

    def load(self) -> list[Withdrawal]:
        """No file: nothing withdrawn. An unknown format stops the run."""
        if not self._path.exists():
            return []
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if data.get("format_version") != FORMAT_VERSION:
            raise ValueError(f"{self._path.name}: unbekannte format_version")
        return [
            Withdrawal(item["repository_url"], date.fromisoformat(item["day"]), item["reason"])
            for item in data["withdrawals"]
        ]
