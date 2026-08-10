from __future__ import annotations

from pathlib import Path

from .classifier import FileAnalyzer
from .filters import is_safe_candidate
from .models import FileSuggestion


def scan_folder(folder: Path, analyzer: FileAnalyzer) -> list[FileSuggestion]:
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return [analyzer.analyze(path) for path in sorted(folder.iterdir()) if is_safe_candidate(path)]

