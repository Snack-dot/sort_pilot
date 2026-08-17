from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path, PurePath


SUBJECT_CATALOG_VERSION = "KR_STUDENT_2026_MVP_V1"
OCCUPATION = "학생"
DEFAULT_CATALOG_PATH = Path(__file__).with_name("data") / "subjects_2026.json"
_FORBIDDEN_FALLBACK_SUBJECTS = {
    "기타",
    "미확인",
    "분류미확인",
    "공통",
    "비교과",
    "과목미확인",
}


class StudentType(str, Enum):
    """Supported student types and their exact user-visible folder labels."""

    MIDDLE = "중학생"
    HIGH = "고등학생"


@dataclass(frozen=True, slots=True)
class SubjectCatalog:
    """One inspectable, versioned subject constraint loaded from JSON."""

    version: str
    occupation: str
    middle_subjects: tuple[str, ...]
    high_subjects: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject stale metadata, missing subjects, fallbacks, and unsafe labels."""
        if not isinstance(self.version, str) or self.version != SUBJECT_CATALOG_VERSION:
            raise ValueError("지원하지 않는 과목 카탈로그 버전입니다.")
        if not isinstance(self.occupation, str) or self.occupation != OCCUPATION:
            raise ValueError("과목 카탈로그의 직업은 학생이어야 합니다.")
        for subjects in (self.middle_subjects, self.high_subjects):
            if not subjects or len(subjects) != len(set(subjects)):
                raise ValueError("학생 유형별 과목은 비어 있거나 중복될 수 없습니다.")
            for subject in subjects:
                if (
                    not subject
                    or subject != subject.strip()
                    or subject in _FORBIDDEN_FALLBACK_SUBJECTS
                    or subject in {".", ".."}
                    or len(PurePath(subject).parts) != 1
                ):
                    raise ValueError(f"유효하지 않은 과목 라벨입니다: {subject!r}")

    def subjects_for(self, student_type: StudentType) -> tuple[str, ...]:
        """Return the exact ordered candidates configured for one student type."""
        if student_type is StudentType.MIDDLE:
            return self.middle_subjects
        if student_type is StudentType.HIGH:
            return self.high_subjects
        raise ValueError("지원하지 않는 학생 유형입니다.")


@lru_cache(maxsize=None)
def load_subject_catalog(path: Path = DEFAULT_CATALOG_PATH) -> SubjectCatalog:
    """Load and validate the static 2026 MVP subject catalog from JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "catalog_version",
            "occupation",
            "student_types",
        }:
            raise ValueError("과목 카탈로그 최상위 필드가 올바르지 않습니다.")
        if not isinstance(data.get("student_types"), dict):
            raise ValueError("과목 카탈로그는 JSON 객체여야 합니다.")
        if not isinstance(data["catalog_version"], str) or not isinstance(data["occupation"], str):
            raise ValueError("과목 카탈로그 메타데이터는 문자열이어야 합니다.")
        student_types = data["student_types"]
        expected_types = {student_type.value for student_type in StudentType}
        if set(student_types) != expected_types:
            raise ValueError("과목 카탈로그의 학생 유형 구성이 올바르지 않습니다.")
        if any(
            not isinstance(student_types[label], list)
            or not all(isinstance(subject, str) for subject in student_types[label])
            for label in expected_types
        ):
            raise ValueError("학생 유형별 과목은 문자열 목록이어야 합니다.")
        return SubjectCatalog(
            version=data["catalog_version"],
            occupation=data["occupation"],
            middle_subjects=tuple(student_types[StudentType.MIDDLE.value]),
            high_subjects=tuple(student_types[StudentType.HIGH.value]),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"과목 카탈로그를 읽을 수 없습니다: {path}") from exc
