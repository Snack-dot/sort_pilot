from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePath

from sort_pilot.curriculum import OCCUPATION, StudentProfile


class DecisionSource(str, Enum):
    """Authority that produced one classification-axis decision."""

    LOCAL = "local_classifier"
    GEMMA = "gemma_fallback"
    USER = "user"
    CACHE = "cache"
    PERSONAL_EXAMPLE = "personal_example"
    REVIEW = "needs_review"


class Template(str, Enum):
    """The five and only five destination templates for the student MVP."""

    LEARNING_MATERIAL = "학습자료"
    ASSIGNMENT = "과제"
    IN_SCHOOL = "교내활동"
    OUT_OF_SCHOOL = "교외활동"
    EVIDENCE = "증빙서류"


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """One ranked candidate with an inspectable raw score."""

    label: str
    raw_score: float

    def __post_init__(self) -> None:
        """Reject blank labels and non-finite raw scores."""
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("후보 라벨은 비어 있지 않은 문자열이어야 합니다.")
        if not math.isfinite(self.raw_score):
            raise ValueError("후보 원점수는 유한해야 합니다.")
        object.__setattr__(self, "label", self.label.strip())


@dataclass(frozen=True, slots=True)
class EvidenceContribution:
    """One named structured contribution retained for an axis decision."""

    name: str
    value: float
    detail: str = ""

    def __post_init__(self) -> None:
        """Validate the evidence name, numeric contribution, and detail text."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("근거 기여 이름은 비어 있을 수 없습니다.")
        if not math.isfinite(self.value):
            raise ValueError("근거 기여 값은 유한해야 합니다.")
        if not isinstance(self.detail, str):
            raise ValueError("근거 설명은 문자열이어야 합니다.")
        object.__setattr__(self, "name", self.name.strip())


@dataclass(frozen=True, slots=True)
class AxisDecision:
    """Complete representation for one subject or template decision."""

    label: str | None
    raw_score: float
    calibrated_confidence: float | None
    margin: float
    candidates: tuple[CandidateScore, ...]
    evidence: tuple[EvidenceContribution, ...]
    source: DecisionSource
    model_version: str
    profile_version: str
    policy_version: str
    needs_review: bool = False

    def __post_init__(self) -> None:
        """Validate scores, ranking, versions, and nullable review state."""
        if self.label is not None:
            if not isinstance(self.label, str) or not self.label.strip():
                raise ValueError("분류 축의 라벨은 빈 문자열일 수 없습니다.")
            object.__setattr__(self, "label", self.label.strip())
        if not math.isfinite(self.raw_score):
            raise ValueError("분류 축의 원점수는 유한해야 합니다.")
        if self.calibrated_confidence is not None and (
            not math.isfinite(self.calibrated_confidence)
            or not 0.0 <= self.calibrated_confidence <= 1.0
        ):
            raise ValueError("보정 신뢰도는 0과 1 사이의 유한한 값이어야 합니다.")
        if not math.isfinite(self.margin) or self.margin < 0:
            raise ValueError("상위 후보 간격은 0 이상의 유한한 값이어야 합니다.")
        labels = [candidate.label for candidate in self.candidates]
        if len(labels) != len(set(labels)):
            raise ValueError("순위 후보 라벨은 중복될 수 없습니다.")
        if any(
            left.raw_score < right.raw_score
            for left, right in zip(self.candidates, self.candidates[1:])
        ):
            raise ValueError("순위 후보는 원점수 내림차순이어야 합니다.")
        if not isinstance(self.source, DecisionSource):
            raise ValueError("지원하지 않는 결정 출처입니다.")
        for value, name in (
            (self.model_version, "model_version"),
            (self.profile_version, "profile_version"),
            (self.policy_version, "policy_version"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name}은 비어 있을 수 없습니다.")
        if self.needs_review != (self.label is None):
            raise ValueError("미해결 축만 needs_review로 표시해야 합니다.")
        if (self.source is DecisionSource.REVIEW) != self.needs_review:
            raise ValueError("검토 출처와 needs_review 상태가 일치해야 합니다.")

    def to_dict(self) -> dict:
        """Serialize every required per-axis representation field."""
        return {
            "label": self.label,
            "raw_score": self.raw_score,
            "calibrated_confidence": self.calibrated_confidence,
            "margin": self.margin,
            "candidates": [
                {"label": candidate.label, "raw_score": candidate.raw_score}
                for candidate in self.candidates
            ],
            "evidence": [
                {"name": contribution.name, "value": contribution.value, "detail": contribution.detail}
                for contribution in self.evidence
            ],
            "source": self.source.value,
            "model_version": self.model_version,
            "profile_version": self.profile_version,
            "policy_version": self.policy_version,
            "needs_review": self.needs_review,
        }


@dataclass(frozen=True, slots=True)
class EducationalClassificationResult:
    """Exactly two independent classification axes plus student context."""

    student: StudentProfile
    subject: AxisDecision
    template: AxisDecision

    def __post_init__(self) -> None:
        """Bound subject and template decisions, candidates, and labels."""
        allowed_subjects = set(self.student.allowed_subjects)
        if self.subject.label is not None and self.subject.label not in allowed_subjects:
            raise ValueError("과목 결정이 2026 과목 카탈로그 범위를 벗어났습니다.")
        if any(candidate.label not in allowed_subjects for candidate in self.subject.candidates):
            raise ValueError("과목 후보가 2026 과목 카탈로그 범위를 벗어났습니다.")
        allowed_templates = {template.value for template in Template}
        if self.template.label is not None and self.template.label not in allowed_templates:
            raise ValueError("지원하지 않는 템플릿 분류입니다.")
        if any(candidate.label not in allowed_templates for candidate in self.template.candidates):
            raise ValueError("템플릿 후보가 고정된 다섯 템플릿을 벗어났습니다.")

    @property
    def needs_review(self) -> bool:
        """Return whether either classification axis is unresolved."""
        return self.subject.needs_review or self.template.needs_review

    @property
    def folder(self) -> str:
        """Render the hierarchy only after both bounded axes are resolved."""
        if self.needs_review or self.subject.label is None or self.template.label is None:
            raise ValueError("과목과 템플릿이 모두 확정되어야 목적지 폴더를 만들 수 있습니다.")
        parts = (
            OCCUPATION,
            self.student.student_type.value,
            f"{self.student.grade}학년",
            self.student.semester.value,
            self.subject.label,
            self.template.label,
        )
        if any(not part or part in {".", ".."} or len(PurePath(part).parts) != 1 for part in parts):
            raise ValueError("안전하지 않은 교육 분류 경로입니다.")
        return "/".join(parts)

    def to_dict(self) -> dict:
        """Serialize student context and exactly the subject/template axes."""
        return {
            "student": self.student.to_dict(),
            "subject": self.subject.to_dict(),
            "template": self.template.to_dict(),
            "folder": None if self.needs_review else self.folder,
            "needs_review": self.needs_review,
        }


@dataclass(frozen=True, slots=True)
class OrganizationPlan:
    """Exact source and destination paths derived from a resolved classification."""

    source: Path
    destination: Path
    classification: EducationalClassificationResult

    def __post_init__(self) -> None:
        """Reject unresolved classifications and destinations outside the frozen hierarchy."""
        folder = self.classification.folder
        if not self.source.name or not self._valid_destination_name(
            self.source.name,
            self.destination.name,
        ):
            raise ValueError("조직 계획은 원본 파일 이름 또는 기존 충돌 접미사를 보존해야 합니다.")
        expected_parent = tuple(folder.split("/"))
        if self.destination.parent.parts[-len(expected_parent):] != expected_parent:
            raise ValueError("조직 계획의 목적지가 확정된 분류 경로와 일치하지 않습니다.")

    @staticmethod
    def _valid_destination_name(source_name: str, destination_name: str) -> bool:
        """Allow the original name or the existing underscore-number collision form."""
        source = Path(source_name)
        destination = Path(destination_name)
        if destination_name == source_name:
            return True
        if destination.suffix.casefold() != source.suffix.casefold():
            return False
        prefix = f"{source.stem}_"
        suffix = destination.stem[len(prefix):] if destination.stem.startswith(prefix) else ""
        return suffix.isdigit() and int(suffix) >= 1

    @classmethod
    def from_classification(
        cls,
        source: Path,
        destination_root: Path,
        classification: EducationalClassificationResult,
    ) -> "OrganizationPlan":
        """Build a move plan only from a fully resolved bounded classification."""
        folder = classification.folder
        destination = destination_root.joinpath(*folder.split("/"), source.name)
        return cls(source=source, destination=destination, classification=classification)
