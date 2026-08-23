from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .catalog import OCCUPATION, SUBJECT_CATALOG_VERSION, StudentType, load_subject_catalog


class Semester(str, Enum):
    """The only semester values accepted by the student MVP."""

    FIRST = "1학기"
    SECOND = "2학기"


@dataclass(frozen=True, slots=True)
class StudentProfile:
    """Persisted onboarding context bounded by the single student catalog."""

    student_type: StudentType
    grade: int
    semester: Semester
    catalog_version: str = SUBJECT_CATALOG_VERSION
    occupation: str = OCCUPATION

    def __post_init__(self) -> None:
        """Validate the fixed occupation, catalog, student type, grade, and term."""
        if not isinstance(self.student_type, StudentType):
            raise ValueError("학생 유형은 중학생 또는 고등학생이어야 합니다.")
        if type(self.grade) is not int or self.grade not in {1, 2, 3}:
            raise ValueError("학년은 1, 2, 3 중 하나여야 합니다.")
        if not isinstance(self.semester, Semester):
            raise ValueError("학기는 1학기 또는 2학기여야 합니다.")
        if self.catalog_version != SUBJECT_CATALOG_VERSION:
            raise ValueError("지원하지 않는 과목 카탈로그 버전입니다.")
        if self.occupation != OCCUPATION:
            raise ValueError("지원하는 직업은 학생뿐입니다.")
        load_subject_catalog().subjects_for(self.student_type)

    @property
    def allowed_subjects(self) -> tuple[str, ...]:
        """Return only exact JSON catalog entries for the selected student type."""
        return load_subject_catalog().subjects_for(self.student_type)

    def to_dict(self) -> dict:
        """Serialize only the fixed occupation and onboarding selections."""
        return {
            "occupation": self.occupation,
            "student_type": self.student_type.value,
            "grade": self.grade,
            "semester": self.semester.value,
            "catalog_version": self.catalog_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentProfile":
        """Parse and validate one persisted student onboarding document."""
        try:
            if set(data) != {
                "occupation",
                "student_type",
                "grade",
                "semester",
                "catalog_version",
            }:
                raise ValueError("학생 프로필 필드가 올바르지 않습니다.")
            if (
                type(data["grade"]) is not int
                or not isinstance(data["student_type"], str)
                or not isinstance(data["semester"], str)
                or not isinstance(data["catalog_version"], str)
                or not isinstance(data["occupation"], str)
            ):
                raise ValueError("학년은 정수여야 합니다.")
            return cls(
                student_type=StudentType(data["student_type"]),
                grade=data["grade"],
                semester=Semester(data["semester"]),
                catalog_version=data["catalog_version"],
                occupation=data["occupation"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("유효하지 않은 학생 프로필입니다.") from exc


class StudentProfileStore:
    """Atomic JSON persistence for the single active onboarding profile."""

    DOCUMENT_VERSION = 1

    def __init__(self, path: Path) -> None:
        """Bind the store to a private application-state path."""
        self.path = path

    def load(self) -> StudentProfile | None:
        """Load the active profile, returning None only before onboarding."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or set(data) != {"version", "profile"}
                or type(data["version"]) is not int
                or data["version"] != self.DOCUMENT_VERSION
                or not isinstance(data["profile"], dict)
            ):
                raise ValueError("지원하지 않는 프로필 문서 버전입니다.")
            return StudentProfile.from_dict(data["profile"])
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"학생 프로필을 읽을 수 없습니다: {self.path}") from exc

    def save(self, profile: StudentProfile) -> None:
        """Atomically replace the active student profile."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix="student-profile-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    {"version": self.DOCUMENT_VERSION, "profile": profile.to_dict()},
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)


def default_profile(
    student_type: StudentType,
    grade: int,
    semester: Semester,
) -> StudentProfile:
    """Create a validated profile for one onboarding choice."""
    return StudentProfile(student_type, grade, semester)
