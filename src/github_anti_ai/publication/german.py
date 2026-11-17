"""Numbers and dates the German way, as the pages show them."""

import json
import re
from datetime import date
from pathlib import Path

MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip
EDITION_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
FORMAT_VERSION = 1


def number(value: int) -> str:
    """91943 becomes 91.943"""
    return f"{value:,}".replace(",", ".")


def decimal(value: float) -> str:
    """One decimal with a comma; a real minus sign: −3,0"""
    text = f"{abs(value):.1f}".replace(".", ",")
    return f"−{text}" if value < 0 else text


def weight(value: float) -> str:
    """With its sign: +40,0, −3,0, and 0 for nothing."""
    if value == 0:
        return "0"
    return f"+{decimal(value)}" if value > 0 else decimal(value)


def long_date(day: date) -> str:
    return f"{day.day}. {MONTHS[day.month - 1]} {day.year}"


def age(created: date, day: date) -> str:
    days = (day - created).days
    if days <= 0:
        return "heute erstellt"
    return "1 Tag alt" if days == 1 else f"{days} Tage alt"


def shown_license(license_id: str | None) -> str | None:
    """A forge's placeholder for an unidentified license file is no license name."""
    return None if license_id == "NOASSERTION" else license_id


def web_url(value) -> str | None:
    """Text from strangers becomes a link only if it is a real web address."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def load_edition_files(directory: Path, what: str) -> list[dict]:
    """The stored editions of a directory, oldest first. An unknown format stops the build:
    a half understood edition must never be published."""
    directory = Path(directory)
    if not directory.exists():
        return []
    editions = []
    for path in sorted(directory.iterdir()):
        if not EDITION_FILE.fullmatch(path.name):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format_version") != FORMAT_VERSION:
            raise ValueError(
                f"{what} {path.name}: unbekannte format_version {data.get('format_version')!r}, "
                f"erwartet wird {FORMAT_VERSION}"
            )
        editions.append(data)
    return editions
