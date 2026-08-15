from __future__ import annotations

from pathlib import Path

from .filters import is_safe_candidate


def collect_candidates(folder: Path) -> list[Path]:
    """Collect safe top-level files without performing expensive classification."""
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return [path for path in sorted(folder.iterdir()) if is_safe_candidate(path)]

