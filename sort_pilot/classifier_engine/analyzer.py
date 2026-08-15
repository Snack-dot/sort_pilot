from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from ..models import FileSuggestion
from .config import Config, data_dir
from .extract import extract, is_processable, supports_content_analysis
from .hierarchy import route_type
from .topics import AnalysisRecord, vector_terms
from .types import FeatureVector


class FileAnalyzer(Protocol):
    """Structural boundary used by background analysis jobs."""

    def analyze_record(self, file_path: Path) -> AnalysisRecord:
        """Return one extraction record for local LLM classification."""
        ...


class ClassifierEngine:
    """Extract local file evidence without running a second classifier or decision store."""

    def __init__(self, config: Config | None = None, root: Path | None = None) -> None:
        """Load only the bounded extraction settings needed by the active workflow."""
        self.root = root or data_dir()
        self.config = config or Config.load(self.root / "config.json")

    def analyze_record(self, file_path: Path) -> AnalysisRecord:
        """Extract content evidence and contain failures to this one file."""
        vector = self._safe_extract(file_path)
        terms = vector_terms(vector, self.config.source_weights)
        return AnalysisRecord(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=file_path.name,
            family=route_type(file_path),
            terms=terms,
            content_extraction_failed=(
                bool(vector.partial)
                or (supports_content_analysis(file_path) and not terms)
            ),
        )

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Return the stable compatibility suggestion before role-aware LLM classification."""
        return self._suggestion(self.analyze_record(file_path))

    def analyze_json(self, file_path: Path) -> dict[str, str]:
        """Return one extraction-backed result using the public JSON contract."""
        suggestion = self.analyze(file_path)
        return {"filepath": Path(suggestion.file_path).as_posix(), "folder": suggestion.folder}

    def analyze_many_json(self, file_paths: Iterable[Path]) -> dict[str, list[dict[str, str]]]:
        """Return ordered extraction-backed results using the public batch contract."""
        return {
            "results": [self.analyze_json(path) for path in file_paths],
        }

    def close(self) -> None:
        """Retain a no-op close method for callers of the former persisted engine API."""

    def _safe_extract(self, file_path: Path) -> FeatureVector:
        """Convert extraction errors into a partial vector without masking other stages."""
        if not is_processable(file_path, self.config.exclusions):
            raise ValueError(f"Excluded or incomplete file: {file_path}")
        try:
            return extract(file_path, self.config.max_content_mb)
        except Exception:
            return FeatureVector(partial=True)

    @staticmethod
    def _suggestion(record: AnalysisRecord) -> FileSuggestion:
        """Adapt one record to the stable pre-LLM compatibility model."""
        return FileSuggestion(
            file_path=record.file_path,
            file_name=record.file_name,
            suggested_name=record.suggested_name,
            folder=record.folder,
            reason="",
        )
