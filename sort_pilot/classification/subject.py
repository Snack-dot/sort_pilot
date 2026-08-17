from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sort_pilot.curriculum import StudentProfile

from .result import AxisDecision


@dataclass(frozen=True, slots=True)
class SubjectProfile:
    """Versioned global evidence describing one curriculum subject."""

    label: str
    prototype_texts: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    version: str = "v1"

    def __post_init__(self) -> None:
        """Normalize profile text and require evidence beyond a bare label."""
        label = self.label.strip()
        prototypes = tuple(value.strip() for value in self.prototype_texts if value.strip())
        keywords = tuple(dict.fromkeys(value.strip() for value in self.keywords if value.strip()))
        if not label or not prototypes:
            raise ValueError("과목 프로필에는 라벨과 하나 이상의 설명문이 필요합니다.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "prototype_texts", prototypes)
        object.__setattr__(self, "keywords", keywords)


@dataclass(frozen=True, slots=True)
class SubjectEvidence:
    """Bounded natural text and structured lexical evidence for one file."""

    file_name: str
    natural_text: str
    lexical_terms: tuple[str, ...] = ()


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
    profiles_by_label = {profile.label: profile for profile in profiles}
    return tuple(
        profiles_by_label[label]
        for label in student.allowed_subjects
        if label in profiles_by_label
    )
