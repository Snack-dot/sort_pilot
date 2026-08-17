from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from sort_pilot.curriculum import StudentProfile, load_subject_catalog

from .result import AxisDecision, CandidateScore


SUBJECT_PROFILE_VERSION = "1"
DEFAULT_SUBJECT_PROFILES_PATH = Path(__file__).with_name("data") / "subject_profiles_ko.json"


@dataclass(frozen=True, slots=True)
class SubjectProfile:
    """Versioned global evidence describing one curriculum subject."""

    label: str
    prototype_texts: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    version: str = "v1"

    def __post_init__(self) -> None:
        """Normalize profile text and require evidence beyond a bare label."""
        if (
            not isinstance(self.label, str)
            or not isinstance(self.prototype_texts, tuple)
            or not all(isinstance(value, str) for value in self.prototype_texts)
            or not isinstance(self.keywords, tuple)
            or not all(isinstance(value, str) for value in self.keywords)
            or not isinstance(self.version, str)
        ):
            raise ValueError("과목 프로필 필드의 타입이 올바르지 않습니다.")
        label = self.label.strip()
        prototypes = tuple(dict.fromkeys(value.strip() for value in self.prototype_texts if value.strip()))
        keywords = tuple(dict.fromkeys(value.strip() for value in self.keywords if value.strip()))
        version = self.version.strip()
        if not label or not prototypes or not version:
            raise ValueError("과목 프로필에는 라벨과 하나 이상의 설명문이 필요합니다.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "prototype_texts", prototypes)
        object.__setattr__(self, "keywords", keywords)
        object.__setattr__(self, "version", version)


@dataclass(frozen=True, slots=True)
class SubjectEvidence:
    """Bounded natural text and structured lexical evidence for one file."""

    file_name: str
    natural_text: str
    lexical_terms: tuple[str, ...] = ()
    personal_example_scores: tuple[CandidateScore, ...] = ()

    def __post_init__(self) -> None:
        """Validate file-name, natural-text, and separate lexical evidence types."""
        if (
            not isinstance(self.file_name, str)
            or not self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
        ):
            raise ValueError("과목 근거에는 경로가 아닌 파일 이름이 필요합니다.")
        if not isinstance(self.natural_text, str):
            raise ValueError("과목 자연어 본문은 문자열이어야 합니다.")
        if not isinstance(self.lexical_terms, tuple) or not all(
            isinstance(value, str) for value in self.lexical_terms
        ):
            raise ValueError("과목 어휘 근거는 문자열 튜플이어야 합니다.")
        if not isinstance(self.personal_example_scores, tuple) or not all(
            isinstance(value, CandidateScore) for value in self.personal_example_scores
        ):
            raise ValueError("개인 예시 과목 근거는 후보 점수 튜플이어야 합니다.")
        labels = tuple(item.label for item in self.personal_example_scores)
        if len(labels) != len(set(labels)) or any(
            not -1.0 <= item.raw_score <= 1.0 for item in self.personal_example_scores
        ):
            raise ValueError("개인 예시 과목 근거는 중복 없는 -1부터 1 사이 점수여야 합니다.")

    @property
    def embedding_text(self) -> str:
        """Return natural filename/body text without serializing structured evidence."""
        stem = Path(self.file_name).stem.replace("_", " ").replace("-", " ").strip()
        body = self.natural_text.strip()
        return "\n".join(value for value in (stem, body) if value)


class SubjectClassifier(Protocol):
    """Interface implemented by local subject classifiers such as E5 scoring."""

    model_id: str

    def classify(
        self,
        evidence: SubjectEvidence,
        student: StudentProfile,
        profiles: tuple[SubjectProfile, ...],
    ) -> AxisDecision:
        """Return one observable decision bounded by the student subject catalog."""
        ...


def eligible_subject_profiles(
    student: StudentProfile,
    profiles: tuple[SubjectProfile, ...],
) -> tuple[SubjectProfile, ...]:
    """Select profiles allowed by the student catalog in candidate-list order."""
    labels = tuple(profile.label for profile in profiles)
    if len(labels) != len(set(labels)):
        raise ValueError("과목 프로필 라벨은 중복될 수 없습니다.")
    profiles_by_label = {profile.label: profile for profile in profiles}
    return tuple(
        profiles_by_label[label]
        for label in student.allowed_subjects
        if label in profiles_by_label
    )


@lru_cache(maxsize=None)
def load_subject_profiles(
    path: Path = DEFAULT_SUBJECT_PROFILES_PATH,
) -> tuple[SubjectProfile, ...]:
    """Load strict natural-language profiles for every configured catalog subject."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"version", "subjects"}:
            raise ValueError("과목 프로필 최상위 필드가 올바르지 않습니다.")
        if not isinstance(data["version"], str) or data["version"] != SUBJECT_PROFILE_VERSION:
            raise ValueError("지원하지 않는 과목 프로필 버전입니다.")
        if not isinstance(data["subjects"], dict):
            raise ValueError("과목 프로필 subjects는 JSON 객체여야 합니다.")

        catalog = load_subject_catalog()
        catalog_subjects = tuple(
            dict.fromkeys((*catalog.middle_subjects, *catalog.high_subjects))
        )
        if set(data["subjects"]) != set(catalog_subjects):
            raise ValueError("과목 프로필 라벨이 과목 카탈로그와 일치하지 않습니다.")
        if any(
            not isinstance(data["subjects"][label], list)
            or not data["subjects"][label]
            or not all(isinstance(value, str) for value in data["subjects"][label])
            for label in catalog_subjects
        ):
            raise ValueError("각 과목 프로필에는 하나 이상의 자연어 설명문이 필요합니다.")
        return tuple(
            SubjectProfile(
                label=label,
                prototype_texts=tuple(data["subjects"][label]),
                version=data["version"],
            )
            for label in catalog_subjects
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"과목 프로필을 읽을 수 없습니다: {path}") from exc
