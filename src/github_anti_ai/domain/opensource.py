"""Which licenses the community project lists accept. See docs/datensammlung.md."""

OPEN_SOURCE_LICENSES = frozenset(
    {
        "0BSD", "AFL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "Apache-2.0",
        "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSL-1.0", "CC0-1.0",
        "CDDL-1.0", "CERN-OHL-P-2.0", "ECL-2.0", "EPL-1.0", "EPL-2.0",
        "EUPL-1.2", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only",
        "GPL-3.0-or-later", "ISC", "LGPL-2.1-only", "LGPL-2.1-or-later",
        "LGPL-3.0-only", "LGPL-3.0-or-later", "MIT", "MPL-2.0", "MS-PL",
        "OFL-1.1", "OSL-3.0", "PostgreSQL", "Python-2.0", "Unlicense", "WTFPL",
        "Zlib",
    }
)
# What GitHub reports for a license file it cannot identify, typically two license files
# (MIT and Apache) or a modified license text. The resolver maps GitLab's "other" to it.
UNRECOGNIZED_LICENSE = "NOASSERTION"


def is_open_source_license(license_id: str | None) -> bool:
    """An approved license, or a license file the forge cannot identify."""
    return license_id in OPEN_SOURCE_LICENSES or license_id == UNRECOGNIZED_LICENSE
