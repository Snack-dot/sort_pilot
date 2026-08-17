from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from sort_pilot.classification import DecisionSource, Template
from sort_pilot.curriculum import Semester, StudentProfile, StudentType


_CORPUS_FIELDS = {
    "file_name",
    "text",
    "student_type",
    "grade",
    "semester",
    "subject",
    "template",
}
_PREDICTION_FIELDS = {
    "subject",
    "template",
    "subject_source",
    "template_source",
    "subject_corrected",
    "template_corrected",
    "latency_ms",
    "memory_mb",
}


def _require_fields(data: dict, expected: set[str], record_name: str) -> None:
    """Reject missing or additional fields in one evaluation record."""
    actual = set(data)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"{record_name} 필드가 올바르지 않습니다: missing={missing}, extra={extra}"
        )


def _required_text(value: object, field_name: str) -> str:
    """Validate required nonblank text without coercing another type."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}은 비어 있지 않은 문자열이어야 합니다.")
    return value.strip()


def _optional_label(value: object, field_name: str) -> str | None:
    """Validate a subject or template prediction that may be unresolved."""
    if value is None:
        return None
    return _required_text(value, field_name)


def _read_document(path: Path, root_field: str, record_name: str) -> list[dict]:
    """Read one strict JSON document containing an ordered record list."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{record_name} 파일을 읽을 수 없습니다: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{record_name} 파일의 최상위 값은 JSON 객체여야 합니다: {path}")
    try:
        _require_fields(data, {root_field}, record_name)
    except ValueError as exc:
        raise RuntimeError(f"{record_name} 파일이 올바르지 않습니다: {path}") from exc
    records = data[root_field]
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"{record_name} 항목은 비어 있지 않은 목록이어야 합니다: {path}")
    if not all(isinstance(record, dict) for record in records):
        raise RuntimeError(f"{record_name}의 각 항목은 JSON 객체여야 합니다: {path}")
    return records


@dataclass(frozen=True, slots=True)
class CorpusCase:
    """One made-up labeled example in the synthetic student corpus."""

    student: StudentProfile
    file_name: str
    text: str
    subject: str
    template: Template

    def __post_init__(self) -> None:
        """Validate a path-free example and its catalog-bounded labels."""
        if (
            not isinstance(self.file_name, str)
            or not self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
            or len(self.file_name) > 255
        ):
            raise ValueError("코퍼스에는 로컬 경로가 아닌 파일 이름만 저장할 수 있습니다.")
        if not isinstance(self.text, str) or len(self.text) > 8_000:
            raise ValueError("코퍼스 텍스트는 8,000자 이하의 문자열이어야 합니다.")
        if self.subject not in self.student.allowed_subjects:
            raise ValueError("과목이 선택한 학생 유형의 카탈로그에 없습니다.")
        if not isinstance(self.template, Template):
            raise ValueError("템플릿이 고정된 다섯 템플릿에 없습니다.")

    @classmethod
    def from_dict(cls, data: dict) -> "CorpusCase":
        """Parse one strict synthetic corpus case."""
        try:
            _require_fields(data, _CORPUS_FIELDS, "코퍼스")
            if type(data["grade"]) is not int or not isinstance(data["text"], str):
                raise ValueError("학년과 텍스트의 타입이 올바르지 않습니다.")
            student = StudentProfile(
                student_type=StudentType(_required_text(data["student_type"], "student_type")),
                grade=data["grade"],
                semester=Semester(_required_text(data["semester"], "semester")),
            )
            return cls(
                student=student,
                file_name=_required_text(data["file_name"], "file_name"),
                text=data["text"],
                subject=_required_text(data["subject"], "subject"),
                template=Template(_required_text(data["template"], "template")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("유효하지 않은 교육 평가 코퍼스 항목입니다.") from exc

    def to_dict(self) -> dict:
        """Serialize the simple synthetic corpus case."""
        return {
            "file_name": self.file_name,
            "text": self.text,
            "student_type": self.student.student_type.value,
            "grade": self.student.grade,
            "semester": self.student.semester.value,
            "subject": self.subject,
            "template": self.template.value,
        }


@dataclass(frozen=True, slots=True)
class Prediction:
    """One ordered subject/template prediction and its measurements."""

    subject: str | None
    template: str | None
    subject_source: DecisionSource
    template_source: DecisionSource
    subject_corrected: bool
    template_corrected: bool
    latency_ms: float
    memory_mb: float

    def __post_init__(self) -> None:
        """Validate unresolved state, fixed templates, flags, and measurements."""
        if not isinstance(self.subject_source, DecisionSource) or not isinstance(
            self.template_source, DecisionSource
        ):
            raise ValueError("과목과 템플릿 결정 출처가 올바르지 않습니다.")
        if self.subject is not None:
            _required_text(self.subject, "subject")
        if self.template is not None:
            Template(_required_text(self.template, "template"))
        for label, source, axis in (
            (self.subject, self.subject_source, "과목"),
            (self.template, self.template_source, "템플릿"),
        ):
            if (label is None) != (source is DecisionSource.REVIEW):
                raise ValueError(f"{axis}의 미해결 상태와 Needs Review 출처가 일치해야 합니다.")
        if type(self.subject_corrected) is not bool or type(self.template_corrected) is not bool:
            raise ValueError("교정 표시는 불리언이어야 합니다.")
        if (
            not isinstance(self.latency_ms, (int, float))
            or isinstance(self.latency_ms, bool)
            or not isinstance(self.memory_mb, (int, float))
            or isinstance(self.memory_mb, bool)
            or not math.isfinite(self.latency_ms)
            or self.latency_ms < 0
            or not math.isfinite(self.memory_mb)
            or self.memory_mb < 0
        ):
            raise ValueError("지연시간과 메모리는 0 이상의 유한한 값이어야 합니다.")

    @classmethod
    def from_dict(cls, data: dict) -> "Prediction":
        """Parse one strict ordered prediction."""
        try:
            _require_fields(data, _PREDICTION_FIELDS, "예측")
            if (
                type(data["subject_corrected"]) is not bool
                or type(data["template_corrected"]) is not bool
                or not isinstance(data["latency_ms"], (int, float))
                or isinstance(data["latency_ms"], bool)
                or not isinstance(data["memory_mb"], (int, float))
                or isinstance(data["memory_mb"], bool)
            ):
                raise ValueError("예측 측정값의 타입이 올바르지 않습니다.")
            return cls(
                subject=_optional_label(data["subject"], "subject"),
                template=_optional_label(data["template"], "template"),
                subject_source=DecisionSource(
                    _required_text(data["subject_source"], "subject_source")
                ),
                template_source=DecisionSource(
                    _required_text(data["template_source"], "template_source")
                ),
                subject_corrected=data["subject_corrected"],
                template_corrected=data["template_corrected"],
                latency_ms=float(data["latency_ms"]),
                memory_mb=float(data["memory_mb"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("유효하지 않은 교육 평가 예측 항목입니다.") from exc

    def to_dict(self) -> dict:
        """Serialize the ordered prediction."""
        return {
            "subject": self.subject,
            "template": self.template,
            "subject_source": self.subject_source.value,
            "template_source": self.template_source.value,
            "subject_corrected": self.subject_corrected,
            "template_corrected": self.template_corrected,
            "latency_ms": self.latency_ms,
            "memory_mb": self.memory_mb,
        }


def load_corpus(path: Path) -> tuple[CorpusCase, ...]:
    """Load a nonempty labeled synthetic corpus from JSON."""
    records = _read_document(path, "cases", "코퍼스")
    try:
        return tuple(CorpusCase.from_dict(record) for record in records)
    except ValueError as exc:
        raise RuntimeError(f"코퍼스 항목이 올바르지 않습니다: {path}") from exc


def load_predictions(path: Path) -> tuple[Prediction, ...]:
    """Load nonempty ordered predictions from JSON."""
    records = _read_document(path, "predictions", "예측")
    try:
        return tuple(Prediction.from_dict(record) for record in records)
    except ValueError as exc:
        raise RuntimeError(f"예측 항목이 올바르지 않습니다: {path}") from exc
