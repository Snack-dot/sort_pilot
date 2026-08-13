from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Protocol

from .models import FileSuggestion
from .classifier_engine.config import data_dir
from .classifier_engine.hierarchy import hierarchical_folder, route_type
from .classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfileStore,
    filename_terms,
    vector_terms,
)


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

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Classify from filename and extension without reading file content."""
        normalized = file_path.stem.casefold()
        topic = next(
            (category for category, words in self.CATEGORIES if any(word in normalized for word in words)),
            None,
        )
        family = route_type(file_path)
        folder = hierarchical_folder(family, topic)
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
        self.topic_classifier = TopicClassifier()
        self.profile_store = TopicProfileStore(data_dir() / "topic_profiles.json")
        try:
            from .classifier_engine.pipeline import Pipeline

            self.pipeline = Pipeline()
        except (ImportError, OSError, ValueError, sqlite3.Error):
            self.pipeline = None

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Adapt an engine decision to the desktop application's stable model."""
        record = self.analyze_record(file_path)
        self.topic_classifier.assign_existing([record], self.profile_store.load())
        return self._suggestion(record)

    def analyze_record(self, file_path: Path) -> AnalysisRecord:
        """Extract a reusable type-and-term record without assigning a batch topic."""
        terms = filename_terms(file_path)
        reason = "파일명 기반 계층 분류"
        if self.pipeline is not None:
            try:
                vector = self.pipeline.extract_vector(file_path)
                terms = vector_terms(vector, self.pipeline.config.source_weights) or terms
                reason = "로컬 특징 추출 완료"
            except (OSError, ValueError, ImportError, AttributeError):
                pass
        return AnalysisRecord(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=self.fallback._clean_name(file_path),
            family=route_type(file_path),
            terms=terms,
            reason=reason,
        )

    @staticmethod
    def _suggestion(record: AnalysisRecord) -> FileSuggestion:
        """Convert a hierarchical analysis record into the stable app model."""
        return FileSuggestion(
            file_path=record.file_path,
            file_name=record.file_name,
            suggested_name=record.suggested_name,
            folder=record.folder,
            reason=record.reason or f"{record.family} 유형의 미분류 파일",
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
        records = [self.analyze_record(file_path) for file_path in file_paths]
        self.topic_classifier.assign_existing(records, self.profile_store.load())
        return {
            "results": [
                {"filepath": Path(record.file_path).as_posix(), "folder": record.folder}
                for record in records
            ],
        }

    def close(self) -> None:
        """Release the worker-local engine store when the analyzer is retired."""
        if self.pipeline is not None:
            self.pipeline.close()

