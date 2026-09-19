"""Thin interface to the installed `smbcrawler` package (import, don't shell out
here -- the actual crawl runs as a subprocess in the worker).
"""

from __future__ import annotations

import functools
from typing import Any


@functools.lru_cache(maxsize=1)
def _profile_collection():
    from smbcrawler.profiles import collect_profiles

    return collect_profiles()


def default_profile() -> dict[str, Any]:
    """The effective built-in profile collection as plain data (for the scan form)."""
    return _profile_collection().as_dict()


def classify_secret(line: str) -> tuple[str, str]:
    """Which secret rule matched a line -> (rule_label, comment).

    Uses the same "last-defined rule wins" convention as smbcrawler. Only the
    built-in / XDG profile rules are considered (per-scan ``extra_profile_yaml``
    rules are not re-loaded here), so anything else falls back to ``(unmatched)``.
    """
    pc = _profile_collection()
    for label, rule in reversed(list(pc.secrets.items())):
        rule.match(line)
        if rule.secret is not None:
            return label, rule.comment or ""
    return "(unmatched)", ""


def parse_targets(target_strings: list[str]) -> list[str]:
    """Expand CIDRs / validate host specs the same way smbcrawler's CLI does."""
    from smbcrawler.io import get_targets

    return [str(t) for t in get_targets(list(target_strings), None)]


def dry_run(target_strings: list[str], extra_profile_yaml: str | None) -> dict[str, Any]:
    """Mimic `smbcrawler crawl --dry-run`: effective profiles + parsed targets."""
    import tempfile

    from smbcrawler.profiles import collect_profiles

    extra_files: list[str] = []
    tmp = None
    if extra_profile_yaml and extra_profile_yaml.strip():
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".yml", delete=False, prefix="smbui_profile_"
        )
        tmp.write(extra_profile_yaml)
        tmp.close()
        extra_files = [tmp.name]
    try:
        pc = collect_profiles(extra_files=extra_files)
        return {"profiles": pc.as_dict(), "targets": parse_targets(target_strings)}
    finally:
        if tmp is not None:
            import os

            os.unlink(tmp.name)
