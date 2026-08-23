from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from sort_pilot.curriculum import SUBJECT_CATALOG_VERSION, StudentProfile, load_subject_catalog

from .e5 import E5_MODEL_ID, E5_VECTOR_SIZE
from .result import CandidateScore, Template


PERSONAL_EXAMPLE_DOCUMENT_VERSION = 1
PERSONAL_EXAMPLE_POLICY_VERSION = "phase-7-personal-example-v1"
DEFAULT_PERSONAL_EXAMPLE_POLICY_PATH = (
    Path(__file__).with_name("data") / "personal_example_policy.json"
)
MAX_LEXICAL_EVIDENCE_ITEMS = 80
MAX_LEXICAL_EVIDENCE_CHARACTERS = 80
_FINGERPRINT = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True, slots=True)
class PersonalExampleVersions:
    """Relevant catalog, model, profile, and policy versions for one correction."""

    catalog_version: str
    embedding_model_version: str
    subject_profile_version: str
    template_profile_version: str
    subject_policy_version: str
    template_policy_version: str

    def __post_init__(self) -> None:
        """Require the configured catalog/model and nonblank remaining versions."""
        if self.catalog_version != SUBJECT_CATALOG_VERSION:
            raise ValueError("개인 예시의 과목 카탈로그 버전이 올바르지 않습니다.")
        if self.embedding_model_version != E5_MODEL_ID:
            raise ValueError("개인 예시는 정확한 multilingual-e5-small 임베딩이어야 합니다.")
        for value in (
            self.subject_profile_version,
            self.template_profile_version,
            self.subject_policy_version,
            self.template_policy_version,
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("개인 예시의 관련 버전은 비어 있을 수 없습니다.")

    def to_dict(self) -> dict[str, str]:
        """Serialize only the six named relevant versions."""
        return {
            "catalog_version": self.catalog_version,
            "embedding_model_version": self.embedding_model_version,
            "subject_profile_version": self.subject_profile_version,
            "template_profile_version": self.template_profile_version,
            "subject_policy_version": self.subject_policy_version,
            "template_policy_version": self.template_policy_version,
        }

    @classmethod
    def from_dict(cls, value: object) -> "PersonalExampleVersions":
        """Strictly parse the relevant-version object."""
        fields = {
            "catalog_version",
            "embedding_model_version",
            "subject_profile_version",
            "template_profile_version",
            "subject_policy_version",
            "template_policy_version",
        }
        if not isinstance(value, dict) or set(value) != fields or not all(
            isinstance(value[field], str) for field in fields
        ):
            raise ValueError("개인 예시의 관련 버전 필드가 올바르지 않습니다.")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class OriginalPrediction:
    """Subject and template labels shown before the user's preview correction."""

    subject: str | None
    template: str | None

    def __post_init__(self) -> None:
        """Allow unresolved labels while rejecting values outside fixed constraints."""
        catalog = load_subject_catalog()
        allowed_subjects = set(catalog.middle_subjects) | set(catalog.high_subjects)
        if self.subject is not None and self.subject not in allowed_subjects:
            raise ValueError("개인 예시의 원래 과목 예측이 카탈로그를 벗어났습니다.")
        if self.template is not None and self.template not in {item.value for item in Template}:
            raise ValueError("개인 예시의 원래 템플릿 예측이 고정 템플릿을 벗어났습니다.")

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the two nullable original labels."""
        return {"subject": self.subject, "template": self.template}

    @classmethod
    def from_dict(cls, value: object) -> "OriginalPrediction":
        """Strictly parse the two nullable original labels."""
        if (
            not isinstance(value, dict)
            or set(value) != {"subject", "template"}
            or not all(value[field] is None or isinstance(value[field], str) for field in value)
        ):
            raise ValueError("개인 예시의 원래 예측 필드가 올바르지 않습니다.")
        return cls(value["subject"], value["template"])


def _normalized_embedding(values: object) -> tuple[float, ...]:
    """Return one finite normalized 384-dimensional embedding tuple."""
    vector = np.asarray(values, dtype=np.float32)
    if vector.shape != (E5_VECTOR_SIZE,) or not np.isfinite(vector).all():
        raise ValueError("개인 예시 임베딩은 유한한 384차원 벡터여야 합니다.")
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("개인 예시 임베딩은 영벡터일 수 없습니다.")
    return tuple(float(value) for value in vector / norm)


@dataclass(frozen=True, slots=True)
class PersonalExample:
    """One local preview correction retained separately from global profiles."""

    fingerprint: str
    embedding: tuple[float, ...]
    approved_subject: str
    approved_template: str
    original_prediction: OriginalPrediction
    lexical_evidence: tuple[str, ...]
    versions: PersonalExampleVersions

    def __post_init__(self) -> None:
        """Validate the fingerprint, labels, embedding, evidence, and versions."""
        if not isinstance(self.fingerprint, str) or not _FINGERPRINT.fullmatch(
            self.fingerprint
        ):
            raise ValueError("개인 예시 fingerprint는 40~64자리 소문자 16진수여야 합니다.")
        catalog = load_subject_catalog()
        allowed_subjects = set(catalog.middle_subjects) | set(catalog.high_subjects)
        if self.approved_subject not in allowed_subjects:
            raise ValueError("승인한 과목이 과목 카탈로그를 벗어났습니다.")
        if self.approved_template not in {item.value for item in Template}:
            raise ValueError("승인한 템플릿이 고정된 다섯 템플릿을 벗어났습니다.")
        if not isinstance(self.original_prediction, OriginalPrediction):
            raise ValueError("개인 예시에는 원래 예측이 필요합니다.")
        if not isinstance(self.versions, PersonalExampleVersions):
            raise ValueError("개인 예시에는 관련 버전이 필요합니다.")
        if not isinstance(self.lexical_evidence, tuple) or not all(
            isinstance(value, str) for value in self.lexical_evidence
        ):
            raise ValueError("개인 예시의 어휘 근거는 문자열 튜플이어야 합니다.")

        object.__setattr__(self, "embedding", _normalized_embedding(self.embedding))
        lexical = tuple(
            dict.fromkeys(
                value.strip()[:MAX_LEXICAL_EVIDENCE_CHARACTERS]
                for value in self.lexical_evidence[:MAX_LEXICAL_EVIDENCE_ITEMS]
                if value.strip()
            )
        )
        object.__setattr__(self, "lexical_evidence", lexical)

    def to_dict(self) -> dict:
        """Serialize the plan-required correction fields without paths or raw text."""
        return {
            "fingerprint": self.fingerprint,
            "embedding": list(self.embedding),
            "approved_subject": self.approved_subject,
            "approved_template": self.approved_template,
            "original_prediction": self.original_prediction.to_dict(),
            "lexical_evidence": list(self.lexical_evidence),
            "versions": self.versions.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "PersonalExample":
        """Strictly parse one locally stored personal example."""
        fields = {
            "fingerprint",
            "embedding",
            "approved_subject",
            "approved_template",
            "original_prediction",
            "lexical_evidence",
            "versions",
        }
        if (
            not isinstance(value, dict)
            or set(value) != fields
            or not isinstance(value["fingerprint"], str)
            or not isinstance(value["embedding"], list)
            or not isinstance(value["approved_subject"], str)
            or not isinstance(value["approved_template"], str)
            or not isinstance(value["lexical_evidence"], list)
            or not all(isinstance(item, str) for item in value["lexical_evidence"])
        ):
            raise ValueError("개인 예시 필드가 올바르지 않습니다.")
        return cls(
            fingerprint=value["fingerprint"],
            embedding=tuple(value["embedding"]),
            approved_subject=value["approved_subject"],
            approved_template=value["approved_template"],
            original_prediction=OriginalPrediction.from_dict(value["original_prediction"]),
            lexical_evidence=tuple(value["lexical_evidence"]),
            versions=PersonalExampleVersions.from_dict(value["versions"]),
        )


@dataclass(frozen=True, slots=True)
class AxisPersonalExamplePolicy:
    """Calibrated weight and minimum nearest-example similarity for one axis."""

    weight: float
    minimum_similarity: float

    def __post_init__(self) -> None:
        """Require a finite nonnegative weight and cosine-similarity boundary."""
        if (
            isinstance(self.weight, bool)
            or not isinstance(self.weight, (int, float))
            or not math.isfinite(self.weight)
            or self.weight < 0
        ):
            raise ValueError("개인 예시 가중치는 0 이상의 유한한 숫자여야 합니다.")
        if (
            isinstance(self.minimum_similarity, bool)
            or not isinstance(self.minimum_similarity, (int, float))
            or not math.isfinite(self.minimum_similarity)
            or not -1.0 <= self.minimum_similarity <= 1.0
        ):
            raise ValueError("개인 예시 최소 유사도는 -1과 1 사이여야 합니다.")
        object.__setattr__(self, "weight", float(self.weight))
        object.__setattr__(self, "minimum_similarity", float(self.minimum_similarity))

    def to_dict(self) -> dict[str, float]:
        """Serialize the calibrated per-axis values."""
        return {
            "weight": self.weight,
            "minimum_similarity": self.minimum_similarity,
        }


@dataclass(frozen=True, slots=True)
class PersonalExamplePolicy:
    """Central calibrated nearest-example policy for subject and template."""

    subject: AxisPersonalExamplePolicy
    template: AxisPersonalExamplePolicy
    version: str = PERSONAL_EXAMPLE_POLICY_VERSION

    def __post_init__(self) -> None:
        """Require both per-axis policies and the exact packaged version."""
        if not isinstance(self.subject, AxisPersonalExamplePolicy) or not isinstance(
            self.template, AxisPersonalExamplePolicy
        ):
            raise ValueError("개인 예시 정책에는 subject와 template 값이 모두 필요합니다.")
        if self.version != PERSONAL_EXAMPLE_POLICY_VERSION:
            raise ValueError("지원하지 않는 개인 예시 정책 버전입니다.")

    def to_dict(self) -> dict:
        """Serialize the exact central policy fields."""
        return {
            "version": self.version,
            "subject": self.subject.to_dict(),
            "template": self.template.to_dict(),
        }


@lru_cache(maxsize=None)
def load_personal_example_policy(
    path: Path = DEFAULT_PERSONAL_EXAMPLE_POLICY_PATH,
) -> PersonalExamplePolicy:
    """Strictly load calibrated subject/template personal-example influence."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        fields = {"version", "subject", "template"}
        axis_fields = {"weight", "minimum_similarity"}
        if (
            not isinstance(value, dict)
            or set(value) != fields
            or value["version"] != PERSONAL_EXAMPLE_POLICY_VERSION
            or not isinstance(value["subject"], dict)
            or set(value["subject"]) != axis_fields
            or not isinstance(value["template"], dict)
            or set(value["template"]) != axis_fields
        ):
            raise ValueError("개인 예시 정책 필드가 올바르지 않습니다.")
        return PersonalExamplePolicy(
            subject=AxisPersonalExamplePolicy(**value["subject"]),
            template=AxisPersonalExamplePolicy(**value["template"]),
            version=value["version"],
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"개인 예시 정책을 읽을 수 없습니다: {path}") from exc


@dataclass(frozen=True, slots=True)
class PersonalExampleScores:
    """Nearest eligible personal-example similarity scores for both axes."""

    subject: tuple[CandidateScore, ...]
    template: tuple[CandidateScore, ...]


class PersonalExampleStore:
    """Strict atomic local persistence and nearest-example lookup."""

    def __init__(self, path: Path) -> None:
        """Bind the private application-state file without reading it."""
        self.path = path

    def load(self) -> tuple[PersonalExample, ...]:
        """Load the complete strict personal-example document."""
        if not self.path.exists():
            return ()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or set(value) != {"version", "examples"}
                or value["version"] != PERSONAL_EXAMPLE_DOCUMENT_VERSION
                or not isinstance(value["examples"], list)
            ):
                raise ValueError("개인 예시 문서 필드가 올바르지 않습니다.")
            examples = tuple(PersonalExample.from_dict(item) for item in value["examples"])
            fingerprints = tuple(item.fingerprint for item in examples)
            if len(fingerprints) != len(set(fingerprints)):
                raise ValueError("개인 예시 fingerprint는 중복될 수 없습니다.")
            return examples
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError(f"개인 예시를 읽을 수 없습니다: {self.path}") from exc

    def save(self, examples: tuple[PersonalExample, ...]) -> None:
        """Atomically replace the local document after complete validation."""
        if not isinstance(examples, tuple) or not all(
            isinstance(item, PersonalExample) for item in examples
        ):
            raise ValueError("개인 예시는 튜플이어야 합니다.")
        fingerprints = tuple(item.fingerprint for item in examples)
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("개인 예시 fingerprint는 중복될 수 없습니다.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix="personal-examples-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    {
                        "version": PERSONAL_EXAMPLE_DOCUMENT_VERSION,
                        "examples": [item.to_dict() for item in examples],
                    },
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

    def add(self, examples: tuple[PersonalExample, ...]) -> None:
        """Add or replace corrections by fingerprint while retaining separate records."""
        if not examples:
            return
        current = {item.fingerprint: item for item in self.load()}
        for item in examples:
            if not isinstance(item, PersonalExample):
                raise ValueError("개인 예시 타입이 올바르지 않습니다.")
            current[item.fingerprint] = item
        self.save(tuple(current.values()))

    def nearest_scores(
        self,
        embedding: tuple[float, ...],
        student: StudentProfile,
        policy: PersonalExamplePolicy,
    ) -> PersonalExampleScores:
        """Return maximum eligible cosine similarity per approved axis label."""
        if not isinstance(student, StudentProfile) or not isinstance(
            policy, PersonalExamplePolicy
        ):
            raise ValueError("개인 예시 검색에는 학생 프로필과 보정 정책이 필요합니다.")
        query = np.asarray(_normalized_embedding(embedding), dtype=np.float32)
        subject: dict[str, float] = {}
        template: dict[str, float] = {}
        for example in self.load():
            if (
                example.versions.catalog_version != student.catalog_version
                or example.versions.embedding_model_version != E5_MODEL_ID
            ):
                continue
            similarity = float(query @ np.asarray(example.embedding, dtype=np.float32))
            if (
                example.approved_subject in student.allowed_subjects
                and similarity >= policy.subject.minimum_similarity
            ):
                subject[example.approved_subject] = max(
                    subject.get(example.approved_subject, -1.0),
                    similarity,
                )
            if similarity >= policy.template.minimum_similarity:
                template[example.approved_template] = max(
                    template.get(example.approved_template, -1.0),
                    similarity,
                )
        return PersonalExampleScores(
            subject=tuple(
                CandidateScore(label, score)
                for label, score in sorted(subject.items(), key=lambda item: (-item[1], item[0]))
            ),
            template=tuple(
                CandidateScore(label, score)
                for label, score in sorted(template.items(), key=lambda item: (-item[1], item[0]))
            ),
        )
