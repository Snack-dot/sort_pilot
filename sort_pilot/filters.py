from __future__ import annotations

from pathlib import Path


BLOCKED_SUFFIXES = {
    ".lnk", ".url", ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".ps1"
}
TEMP_SUFFIXES = {".tmp", ".part", ".crdownload", ".download"}
UNSUPPORTED_CONTENT_SUFFIXES = {".hwp", ".hwpx"}


def is_safe_candidate(path: Path) -> bool:
    """Return whether a path is a safe, complete, non-executable file candidate."""
    if not path.is_file() or path.name.startswith("."):
        return False
    suffix = path.suffix.casefold()
    if suffix in BLOCKED_SUFFIXES or suffix in TEMP_SUFFIXES:
        return False
    if suffix in UNSUPPORTED_CONTENT_SUFFIXES:
        return False
    return not path.name.startswith(("~$", "~"))

