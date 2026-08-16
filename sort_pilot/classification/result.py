from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import PurePath

from sort_pilot.curriculum import CurriculumProfile


CLASSIFIER_POLICY_VERSION = "education-hybrid-v1"


class DecisionSource(str, Enum):
    """Authority that produced one classification-axis decision."""

    LOCAL = "local_classifier"
    GEMMA = "gemma_fallback"
    USER = "user"
    CACHE = "cache"
    PERSONAL_EXAMPLE = "personal_example"
    REVIEW = "needs_review"


class Activity(str, Enum):
    """Stable user-facing activity folders for the student MVP."""

    ACADEMIC = "학업"
    ASSIGNMENT = "과제"
    IN_SCHOOL = "교내활동"
    OUT_OF_SCHOOL = "교외활동"
    EVIDENCE = "증빙서류"
    NEEDS_REVIEW = "분류미확인"


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """One inspectable candidate score; it is not necessarily a probability."""

    label: str
    score: float


@dataclass(frozen=True, slots=True)
class AxisDecision:
    """One independently resolved subject or activity decision."""

    label: str
    score: float
    margin: float
    source: DecisionSource
    candidates: tuple[CandidateScore, ...] = ()
    evidence: tuple[str, ...] = ()
    needs_review: bool = False

    def __post_init__(self) -> None:
        """Reject empty labels, invalid margins, and inconsistent review state."""
        if not self.label.strip():
            raise ValueError("분류 축의 라벨은 비어 있을 수 없습니다.")
        if self.margin < 0:
            raise ValueError("상위 후보 간격은 음수일 수 없습니다.")
        if self.source is DecisionSource.REVIEW and not self.needs_review:
            raise ValueError("검토 출처의 결정은 needs_review로 표시해야 합니다.")


@dataclass(frozen=True, slots=True)
class EducationalClassificationResult:
    """Rich classification state kept separate from the rendered folder path."""

    curriculum: CurriculumProfile
    subject: AxisDecision
    activity: AxisDecision
    document_type: AxisDecision | None = None
    policy_version: str = CLASSIFIER_POLICY_VERSION
    evidence: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Enforce curriculum and activity bounds before folder rendering."""
        if self.subject.label not in self.curriculum.subject_candidates:
            raise ValueError("과목 결정이 교육과정 후보 범위를 벗어났습니다.")
        if self.activity.label not in {activity.value for activity in Activity}:
            raise ValueError("지원하지 않는 활동 분류입니다.")

    @property
    def needs_review(self) -> bool:
        """Return whether any folder-defining axis still requires user review."""
        return self.subject.needs_review or self.activity.needs_review

    @property
    def folder(self) -> str:
        """Render the stable student hierarchy without exposing internal features."""
        parts = (
            "학생",
            self.curriculum.school_level.value,
            f"{self.curriculum.grade}학년",
            self.curriculum.semester.value,
            self.subject.label,
            self.activity.label,
        )
        if any(not part or part in {".", ".."} or len(PurePath(part).parts) != 1 for part in parts):
            raise ValueError("안전하지 않은 교육 분류 경로입니다.")
        return "/".join(parts)

    def to_dict(self) -> dict:
        """Serialize the complete observable decision contract."""
        data = asdict(self)
        data["curriculum"] = self.curriculum.to_dict()
        data["subject"]["source"] = self.subject.source.value
        data["activity"]["source"] = self.activity.source.value
        if self.document_type is not None:
            data["document_type"]["source"] = self.document_type.source.value
        data["folder"] = self.folder
        data["needs_review"] = self.needs_review
        return data
