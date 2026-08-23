from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from ..models import FileSuggestion
from .config import data_dir
from .hierarchy import UNSORTED_TOPIC, route_type
from .pipeline import Pipeline
from .topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfileStore,
    humanize_term,
    vector_terms,
)
from .types import Decision


class FileAnalyzer(Protocol):
    """Structural application boundary implemented by the classifier engine."""

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Return one application-facing hierarchical suggestion."""
        ...


class ClassifierEngine:
    """Single engine-owned adapter for extraction, decisions, topics, and JSON output."""

    def __init__(
        self,
        pipeline: Pipeline | None = None,
        profile_store: TopicProfileStore | None = None,
    ) -> None:
        """Own a real pipeline and the family-specific topic services."""
        self.pipeline = pipeline or Pipeline()
        self.profile_store = profile_store or TopicProfileStore(data_dir() / "topic_profiles.json")
        self.topic_classifier = TopicClassifier()

    def analyze_record(self, file_path: Path) -> AnalysisRecord:
        """Run the complete pipeline and retain its persisted decision in one record."""
        vector, decision, decision_id = self.pipeline.safe_classify(file_path)
        family = route_type(file_path)
        reason = self._decision_reason(decision)
        lexical_evidence = tuple(
            dict.fromkeys(
                feature.t
                for feature in vector.features
                if feature.src in {"body", "ocr"}
                and not feature.t.startswith(("bi:", "tri:"))
            )
        )
        pmi_collocations = tuple(
            dict.fromkeys(
                feature.t.split(":", 1)[1]
                for feature in vector.features
                if feature.src == "body" and feature.t.startswith(("bi:", "tri:"))
            )
        )
        visual_evidence = tuple(
            dict.fromkeys(
                value
                for feature in vector.features
                if feature.src in {"obj", "pair"}
                for value in (humanize_term(feature.t),)
                if value
            )
        )
        return AnalysisRecord(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            suggested_name=file_path.name,
            family=family,
            terms=vector_terms(vector, self.pipeline.config.source_weights),
            fingerprint=vector.file_id.split(":", 1)[-1],
            natural_text=vector.natural_text,
            template_natural_text=vector.template_natural_text,
            lexical_evidence=lexical_evidence,
            pmi_collocations=pmi_collocations,
            ocr_layout_evidence=vector.ocr_layout_evidence,
            visual_evidence=visual_evidence,
            topic=None,
            score=float(decision.margin),
            reason=reason,
            engine_category=decision.category,
            engine_action=decision.action,
            engine_tier=decision.tier,
            decision_id=decision_id,
        )

    def analyze(self, file_path: Path) -> FileSuggestion:
        """Run engine classification and saved-profile resolution for one file."""
        record = self.analyze_record(file_path)
        self.topic_classifier.assign_existing([record], self.profile_store.load())
        return self._suggestion(record)

    def analyze_json(self, file_path: Path) -> dict[str, str]:
        """Return one real-engine result using the public JSON-object contract."""
        suggestion = self.analyze(file_path)
        return {"filepath": Path(suggestion.file_path).as_posix(), "folder": suggestion.folder}

    def analyze_many_json(self, file_paths: Iterable[Path]) -> dict[str, list[dict[str, str]]]:
        """Return ordered real-engine results using the public batch JSON contract."""
        records = [self.analyze_record(path) for path in file_paths]
        self.topic_classifier.assign_existing(records, self.profile_store.load())
        return {
            "results": [
                {"filepath": Path(record.file_path).as_posix(), "folder": record.folder}
                for record in records
            ]
        }

    def close(self) -> None:
        """Release the engine-owned SQLite connection."""
        self.pipeline.close()

    @staticmethod
    def _suggestion(record: AnalysisRecord) -> FileSuggestion:
        """Convert one resolved engine record into the stable application model."""
        reason = record.reason or f"{record.family} 유형에서 일치하는 주제가 없어 '{UNSORTED_TOPIC}'로 제안"
        return FileSuggestion(
            file_path=record.file_path,
            file_name=record.file_name,
            suggested_name=record.suggested_name,
            folder=record.folder,
            reason=reason,
        )

    @staticmethod
    def _decision_reason(decision: Decision) -> str:
        """Explain the recorded engine evidence without selecting a user topic."""
        if decision.action == "exclude":
            return f"엔진 {decision.tier} 제외 결정"
        category = f", category={decision.category}" if decision.category else ""
        return (
            f"엔진 {decision.tier} 분석 증거 기록"
            f" (action={decision.action}{category}, margin={decision.margin:.3f}); 주제는 사용자 프로필/승인으로 결정"
        )
