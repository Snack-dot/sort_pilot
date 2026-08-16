from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


CURRICULUM_VERSION = "SORT_PILOT_KR_SECONDARY_V1"


class SchoolLevel(str, Enum):
    """Supported school levels and their user-visible folder labels."""

    MIDDLE = "중학생"
    HIGH = "고등학생"


class Semester(str, Enum):
    """Semester values retained independently from subject classification."""

    FIRST = "1학기"
    SECOND = "2학기"
    COMMON = "공통"
    UNKNOWN = "미확인"


COMMON_SUBJECTS = ("국어", "수학", "영어", "사회", "과학", "체육", "음악", "미술", "정보")
MIDDLE_SUBJECTS = COMMON_SUBJECTS + ("도덕", "기술·가정", "진로")
HIGH_SUBJECTS = COMMON_SUBJECTS + (
    "한국사",
    "통합사회",
    "통합과학",
    "제2외국어",
    "한문",
    "진로",
)
SPECIAL_SUBJECTS = ("비교과", "공통", "과목미확인")


@dataclass(frozen=True, slots=True)
class CurriculumProfile:
    """One versioned onboarding context that bounds subject candidates."""

    school_level: SchoolLevel
    grade: int
    semester: Semester
    allowed_subjects: tuple[str, ...]
    curriculum_version: str = CURRICULUM_VERSION

    def __post_init__(self) -> None:
        """Normalize and validate the bounded onboarding selections."""
        if self.grade not in {1, 2, 3}:
            raise ValueError("학년은 1, 2, 3 중 하나여야 합니다.")
        normalized = tuple(dict.fromkeys(subject.strip() for subject in self.allowed_subjects))
        if not normalized or any(not subject for subject in normalized):
            raise ValueError("허용 과목 목록은 비어 있을 수 없습니다.")
        object.__setattr__(self, "allowed_subjects", normalized)

    @property
    def subject_candidates(self) -> tuple[str, ...]:
        """Return curriculum subjects plus explicit non-subject fallbacks."""
        return tuple(dict.fromkeys((*self.allowed_subjects, *SPECIAL_SUBJECTS)))

    @property
    def requires_migration(self) -> bool:
        """Report whether persisted candidate data uses an older curriculum version."""
        return self.curriculum_version != CURRICULUM_VERSION

    def to_dict(self) -> dict:
        """Serialize the profile using stable string enum values."""
        data = asdict(self)
        data["school_level"] = self.school_level.value
        data["semester"] = self.semester.value
        data["allowed_subjects"] = list(self.allowed_subjects)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CurriculumProfile":
        """Parse and validate one persisted curriculum profile document."""
        try:
            return cls(
                school_level=SchoolLevel(str(data["school_level"])),
                grade=int(data["grade"]),
                semester=Semester(str(data["semester"])),
                allowed_subjects=tuple(str(value) for value in data["allowed_subjects"]),
                curriculum_version=str(data["curriculum_version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("유효하지 않은 교육과정 프로필입니다.") from exc


class CurriculumProfileStore:
    """Atomic JSON persistence for the single active onboarding profile."""

    DOCUMENT_VERSION = 1

    def __init__(self, path: Path) -> None:
        """Bind the store to a private application-state path."""
        self.path = path

    def load(self) -> CurriculumProfile | None:
        """Load the active profile, returning None only before onboarding."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if int(data["version"]) != self.DOCUMENT_VERSION:
                raise ValueError("지원하지 않는 프로필 문서 버전입니다.")
            return CurriculumProfile.from_dict(data["profile"])
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"교육과정 프로필을 읽을 수 없습니다: {self.path}") from exc

    def save(self, profile: CurriculumProfile) -> None:
        """Atomically replace the active curriculum profile."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix="curriculum-profile-", suffix=".tmp"
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
    school_level: SchoolLevel,
    grade: int,
    semester: Semester,
) -> CurriculumProfile:
    """Create the initial editable subject space for one onboarding choice."""
    subjects = MIDDLE_SUBJECTS if school_level is SchoolLevel.MIDDLE else HIGH_SUBJECTS
    return CurriculumProfile(school_level, grade, semester, subjects)
