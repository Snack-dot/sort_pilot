from __future__ import annotations

from pathlib import Path

from .classifier_engine.analyzer import FileAnalyzer
from .filters import is_safe_candidate
from .models import FileSuggestion


def collect_candidates(folder: Path) -> list[Path]:
    """Collect safe top-level files without performing expensive classification."""
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return [path for path in sorted(folder.iterdir()) if is_safe_candidate(path)]


def scan_folder(folder: Path, analyzer: FileAnalyzer) -> list[FileSuggestion]:
    """Synchronously classify a folder; retained for scripts and compatibility."""
    return [analyzer.analyze(path) for path in collect_candidates(folder)]

