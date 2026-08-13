from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Protocol

from .models import FileSuggestion


class FileAnalyzer(Protocol):
    """Application-facing protocol implemented by all file analyzers."""

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Return one application-facing suggestion for a file."""
        ...


class RuleBasedAnalyzer:
    """Temporary lightweight analyzer; replaceable by a local-AI implementation."""

    CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("학교", ("과제", "강의", "수업", "학교", "시험", "운영체제")),
        ("금융", ("영수증", "세금", "invoice", "receipt", "결제", "쿠팡")),
        ("업무", ("회의", "보고서", "업무", "회사", "계약")),
        ("이미지", ("스크린샷", "사진", "image", "img", "screenshot")),
    )

    EXTENSION_FOLDERS = {
        ".jpg": "이미지",
        ".jpeg": "이미지",
        ".png": "이미지",
        ".gif": "이미지",
        ".webp": "이미지",
        ".pdf": "문서",
        ".txt": "문서",
        ".docx": "문서",
    }

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Classify from filename and extension without reading file content."""
        normalized = file_path.stem.casefold()
        folder = next(
            (category for category, words in self.CATEGORIES if any(word in normalized for word in words)),
            self.EXTENSION_FOLDERS.get(file_path.suffix.casefold(), "기타"),
        )
        suggested_name = self._clean_name(file_path)
        return FileSuggestion(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=suggested_name,
            folder=folder,
            reason=f"파일명과 확장자를 기준으로 '{folder}' 유형으로 분류했습니다.",
        )

    @staticmethod
    def _clean_name(file_path: Path) -> str:
        """Normalize whitespace and repeated final markers in a filename."""
        stem = re.sub(r"\s+", "_", file_path.stem.strip())
        stem = re.sub(r"(?i)\b(final[_ -]*){2,}", "final_", stem)
        return f"{stem}{file_path.suffix.casefold()}"


class LocalPipelineAnalyzer:
    """Adapt the architecture classifier to the desktop app's stable contract."""

    def __init__(self) -> None:
        """Initialize the local engine, retaining rules as a safe fallback."""
        self.fallback = RuleBasedAnalyzer()
        try:
            from .classifier_engine.pipeline import Pipeline

            self.pipeline = Pipeline()
        except (ImportError, OSError, ValueError, sqlite3.Error):
            self.pipeline = None

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Adapt an engine decision to the desktop application's stable model."""
        if self.pipeline is None:
            return self.fallback.analyze(file_path)

        _, decision, _ = self.pipeline.safe_classify(file_path)
        if not decision.category:
            return self.fallback.analyze(file_path)

        return FileSuggestion(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=self.fallback._clean_name(file_path),
            folder=decision.category,
            reason=(
                f"로컬 {decision.tier} 분류 결과입니다 "
                f"(action={decision.action}, margin={decision.margin:.3f})."
            ),
        )

    def analyze_json(self, file_path: Path) -> dict[str, str]:
        """Return one AI classification using the public JSON-object contract."""
        suggestion = self.analyze(file_path)
        return {
            "filepath": Path(suggestion.file_path).as_posix(),
            "folder": suggestion.folder,
        }

    def analyze_many_json(self, file_paths: Iterable[Path]) -> dict[str, list[dict[str, str]]]:
        """Return multiple AI classifications using the public JSON-object contract."""
        return {
            "results": [self.analyze_json(file_path) for file_path in file_paths],
        }

    def close(self) -> None:
        """Release the worker-local engine store when the analyzer is retired."""
        if self.pipeline is not None:
            self.pipeline.close()

