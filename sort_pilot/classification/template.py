from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from .e5 import E5_MODEL_ID, E5_VECTOR_SIZE, _embedding_matrix
from .result import (
    AxisDecision,
    CandidateScore,
    DecisionSource,
    EvidenceContribution,
    Template,
)


TEMPLATE_PROFILE_VERSION = "1"
TEMPLATE_RANKING_POLICY_VERSION = "phase-4-ranking"
DEFAULT_TEMPLATE_PROFILES_PATH = Path(__file__).with_name("data") / "template_profiles_ko.json"
_WEIGHT_FIELDS = (
    "semantic_intent",
    "file_name",
    "lexical",
    "pmi_collocation",
    "ocr_layout",
    "visual",
    "personal_example",
)
_PROFILE_FIELDS = {
    "prototype_texts",
    "file_name_indicators",
    "lexical_indicators",
    "pmi_collocations",
    "ocr_layout_indicators",
    "visual_indicators",
    "evidence_weights",
}


@dataclass(frozen=True, slots=True)
class TemplateEvidenceWeights:
    """Separate structured-evidence weights for one template profile."""

    semantic_intent: float
    file_name: float
    lexical: float
    pmi_collocation: float
    ocr_layout: float
    visual: float
    personal_example: float

    def __post_init__(self) -> None:
        """Require finite nonnegative weights with at least one active source."""
        values: list[float] = []
        for field in _WEIGHT_FIELDS:
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("템플릿 근거 가중치는 숫자여야 합니다.")
            normalized = float(value)
            if not math.isfinite(normalized) or normalized < 0:
                raise ValueError("템플릿 근거 가중치는 0 이상의 유한한 값이어야 합니다.")
            object.__setattr__(self, field, normalized)
            values.append(normalized)
        if not any(values):
            raise ValueError("템플릿 프로필에는 하나 이상의 양수 가중치가 필요합니다.")

    @property
    def total(self) -> float:
        """Return the denominator used for the inspectable weighted raw score."""
        return sum(getattr(self, field) for field in _WEIGHT_FIELDS)

    def to_dict(self) -> dict[str, float]:
        """Serialize the seven named evidence weights without renaming them."""
        return {field: getattr(self, field) for field in _WEIGHT_FIELDS}


@dataclass(frozen=True, slots=True)
class TemplateProfile:
    """Natural and structured indicators for one fixed template."""

    template: Template
    prototype_texts: tuple[str, ...]
    file_name_indicators: tuple[str, ...]
    lexical_indicators: tuple[str, ...]
    pmi_collocations: tuple[str, ...]
    ocr_layout_indicators: tuple[str, ...]
    visual_indicators: tuple[str, ...]
    evidence_weights: TemplateEvidenceWeights
    version: str = TEMPLATE_PROFILE_VERSION

    def __post_init__(self) -> None:
        """Normalize one complete profile while preserving the fixed template label."""
        if not isinstance(self.template, Template):
            raise ValueError("템플릿 프로필은 고정된 다섯 템플릿 중 하나여야 합니다.")
        for field in (
            "prototype_texts",
            "file_name_indicators",
            "lexical_indicators",
            "pmi_collocations",
            "ocr_layout_indicators",
            "visual_indicators",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(isinstance(value, str) for value in values):
                raise ValueError("템플릿 프로필의 자연어와 구조화 근거는 문자열 튜플이어야 합니다.")
            normalized = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
            if not normalized:
                raise ValueError("템플릿 프로필의 각 근거 목록에는 하나 이상의 값이 필요합니다.")
            object.__setattr__(self, field, normalized)
        if not isinstance(self.evidence_weights, TemplateEvidenceWeights):
            raise ValueError("템플릿 프로필에는 별도의 근거 가중치가 필요합니다.")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("템플릿 프로필 버전은 비어 있지 않은 문자열이어야 합니다.")
        object.__setattr__(self, "version", self.version.strip())


@dataclass(frozen=True, slots=True)
class TemplateEvidence:
    """Natural text and separate structured evidence for template ranking."""

    file_name: str
    natural_text: str
    lexical_terms: tuple[str, ...] = ()
    pmi_collocations: tuple[str, ...] = ()
    ocr_layout_terms: tuple[str, ...] = ()
    visual_terms: tuple[str, ...] = ()
    personal_example_scores: tuple[CandidateScore, ...] = ()

    def __post_init__(self) -> None:
        """Validate the filename and each independent evidence source."""
        if (
            not isinstance(self.file_name, str)
            or not self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
        ):
            raise ValueError("템플릿 근거에는 경로가 아닌 파일 이름이 필요합니다.")
        if not isinstance(self.natural_text, str):
            raise ValueError("템플릿 자연어 본문은 문자열이어야 합니다.")
        object.__setattr__(self, "file_name", self.file_name.strip())
        for field in (
            "lexical_terms",
            "pmi_collocations",
            "ocr_layout_terms",
            "visual_terms",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(isinstance(value, str) for value in values):
                raise ValueError("템플릿 구조화 근거는 문자열 튜플이어야 합니다.")
            object.__setattr__(
                self,
                field,
                tuple(dict.fromkeys(value.strip() for value in values if value.strip())),
            )
        if not isinstance(self.personal_example_scores, tuple) or not all(
            isinstance(value, CandidateScore) for value in self.personal_example_scores
        ):
            raise ValueError("개인 예시 근거는 템플릿 후보 점수 튜플이어야 합니다.")
        labels = tuple(score.label for score in self.personal_example_scores)
        if len(labels) != len(set(labels)):
            raise ValueError("개인 예시 템플릿 점수는 중복될 수 없습니다.")
        allowed = {template.value for template in Template}
        if any(score.label not in allowed or not -1.0 <= score.raw_score <= 1.0 for score in self.personal_example_scores):
            raise ValueError("개인 예시 근거는 고정 템플릿과 -1부터 1 사이 점수만 사용합니다.")

    @property
    def embedding_text(self) -> str:
        """Return only natural filename and body text for E5 embedding."""
        stem = Path(self.file_name).stem.replace("_", " ").replace("-", " ").strip()
        body = self.natural_text.strip()
        return "\n".join(value for value in (stem, body) if value)


class TemplateTextEncoder(Protocol):
    """Minimal multilingual E5 boundary used by template ranking."""

    model_id: str
    vector_size: int

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one 384-dimensional row per natural-language text."""
        ...


def _indicator_score(values: Sequence[str], indicators: Sequence[str]) -> float:
    """Measure the share of supplied structured values matching a profile indicator."""
    normalized_values = tuple(value.casefold().strip() for value in values if value.strip())
    normalized_indicators = tuple(value.casefold().strip() for value in indicators if value.strip())
    if not normalized_values or not normalized_indicators:
        return 0.0
    matched = sum(
        any(indicator in value for indicator in normalized_indicators)
        for value in normalized_values
    )
    return matched / len(normalized_values)


def ordered_template_profiles(
    profiles: tuple[TemplateProfile, ...],
) -> tuple[TemplateProfile, ...]:
    """Require exactly one profile for each fixed template in fixed order."""
    if not isinstance(profiles, tuple) or not all(
        isinstance(profile, TemplateProfile) for profile in profiles
    ):
        raise ValueError("템플릿 프로필은 튜플이어야 합니다.")
    labels = tuple(profile.template for profile in profiles)
    if len(labels) != len(set(labels)) or set(labels) != set(Template):
        raise ValueError("템플릿 프로필은 고정된 다섯 템플릿과 정확히 일치해야 합니다.")
    by_template = {profile.template: profile for profile in profiles}
    return tuple(by_template[template] for template in Template)


@lru_cache(maxsize=None)
def load_template_profiles(
    path: Path = DEFAULT_TEMPLATE_PROFILES_PATH,
) -> tuple[TemplateProfile, ...]:
    """Load strict separate profiles and evidence weights for all five templates."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"version", "templates"}:
            raise ValueError("템플릿 프로필의 최상위 필드가 올바르지 않습니다.")
        if data["version"] != TEMPLATE_PROFILE_VERSION:
            raise ValueError("지원하지 않는 템플릿 프로필 버전입니다.")
        if not isinstance(data["templates"], dict):
            raise ValueError("templates는 JSON 객체여야 합니다.")
        if set(data["templates"]) != {template.value for template in Template}:
            raise ValueError("템플릿 프로필은 고정된 다섯 템플릿과 정확히 일치해야 합니다.")

        profiles: list[TemplateProfile] = []
        for template in Template:
            raw = data["templates"][template.value]
            if not isinstance(raw, dict) or set(raw) != _PROFILE_FIELDS:
                raise ValueError("템플릿별 프로필 필드가 올바르지 않습니다.")
            weights = raw["evidence_weights"]
            if not isinstance(weights, dict) or set(weights) != set(_WEIGHT_FIELDS):
                raise ValueError("템플릿별 근거 가중치 필드가 올바르지 않습니다.")
            list_fields = _PROFILE_FIELDS - {"evidence_weights"}
            if any(
                not isinstance(raw[field], list)
                or not raw[field]
                or not all(isinstance(value, str) for value in raw[field])
                for field in list_fields
            ):
                raise ValueError("템플릿별 자연어와 구조화 근거는 비어 있지 않은 문자열 목록이어야 합니다.")
            profiles.append(
                TemplateProfile(
                    template=template,
                    prototype_texts=tuple(raw["prototype_texts"]),
                    file_name_indicators=tuple(raw["file_name_indicators"]),
                    lexical_indicators=tuple(raw["lexical_indicators"]),
                    pmi_collocations=tuple(raw["pmi_collocations"]),
                    ocr_layout_indicators=tuple(raw["ocr_layout_indicators"]),
                    visual_indicators=tuple(raw["visual_indicators"]),
                    evidence_weights=TemplateEvidenceWeights(**weights),
                    version=data["version"],
                )
            )
        return ordered_template_profiles(tuple(profiles))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"템플릿 프로필을 읽을 수 없습니다: {path}") from exc


class TemplateClassifier:
    """Rank exactly five templates with natural and separately weighted evidence."""

    model_id = E5_MODEL_ID

    def __init__(self, encoder: TemplateTextEncoder) -> None:
        """Bind the exact 384-dimensional multilingual E5-small encoder."""
        if encoder.model_id != self.model_id or encoder.vector_size != E5_VECTOR_SIZE:
            raise ValueError("템플릿 분류기는 정확한 384차원 multilingual-e5-small이 필요합니다.")
        self.encoder = encoder
        self._profile_cache: dict[tuple[TemplateProfile, ...], np.ndarray] = {}

    def _profile_embeddings(self, profiles: tuple[TemplateProfile, ...]) -> np.ndarray:
        """Generate and cache one normalized average vector per template profile."""
        cached = self._profile_cache.get(profiles)
        if cached is not None:
            return cached
        texts: list[str] = []
        owners: list[int] = []
        for index, profile in enumerate(profiles):
            for text in profile.prototype_texts:
                texts.append(f"passage: {text}")
                owners.append(index)
        prototype_matrix = _embedding_matrix(self.encoder.encode(texts), len(texts))
        rows: list[np.ndarray] = []
        owner_array = np.asarray(owners)
        for index in range(len(profiles)):
            average = prototype_matrix[owner_array == index].mean(axis=0)
            rows.append(_embedding_matrix((average,), 1)[0])
        matrix = np.asarray(rows, dtype=np.float32)
        self._profile_cache[profiles] = matrix
        return matrix

    @staticmethod
    def _channel_scores(
        profile: TemplateProfile,
        evidence: TemplateEvidence,
        semantic_intent: float,
        personal_example_weight: float,
    ) -> dict[str, float]:
        """Calculate each named raw evidence value without converting it to text."""
        personal = {
            score.label: score.raw_score for score in evidence.personal_example_scores
        }
        return {
            "semantic_intent": semantic_intent,
            "file_name": _indicator_score(
                (Path(evidence.file_name).stem,),
                profile.file_name_indicators,
            ),
            "lexical": _indicator_score(evidence.lexical_terms, profile.lexical_indicators),
            "pmi_collocation": _indicator_score(
                evidence.pmi_collocations,
                profile.pmi_collocations,
            ),
            "ocr_layout": _indicator_score(
                evidence.ocr_layout_terms,
                profile.ocr_layout_indicators,
            ),
            "visual": _indicator_score(evidence.visual_terms, profile.visual_indicators),
            "personal_example": (
                personal_example_weight * personal.get(profile.template.value, 0.0)
            ),
        }

    def classify(
        self,
        evidence: TemplateEvidence,
        profiles: tuple[TemplateProfile, ...],
        *,
        query_embedding: Sequence[float] | None = None,
        personal_example_weight: float = 1.0,
    ) -> AxisDecision:
        """Rank all five fixed templates and retain weighted evidence and margin."""
        if (
            isinstance(personal_example_weight, bool)
            or not isinstance(personal_example_weight, (int, float))
            or not math.isfinite(personal_example_weight)
            or personal_example_weight < 0
        ):
            raise ValueError("템플릿 개인 예시 가중치는 0 이상의 유한한 숫자여야 합니다.")
        ordered = ordered_template_profiles(profiles)
        versions = {profile.version for profile in ordered}
        if len(versions) != 1:
            raise ValueError("한 번의 템플릿 분류에는 하나의 프로필 버전만 사용할 수 있습니다.")

        profile_matrix = self._profile_embeddings(ordered)
        query_matrix = _embedding_matrix(
            (query_embedding,)
            if query_embedding is not None
            else self.encoder.encode((f"query: {evidence.embedding_text}",)),
            1,
        )
        similarities = np.clip(profile_matrix @ query_matrix[0], -1.0, 1.0)
        scored: list[tuple[TemplateProfile, float, dict[str, float]]] = []
        for profile, similarity in zip(ordered, similarities, strict=True):
            channels = self._channel_scores(
                profile,
                evidence,
                float(similarity),
                float(personal_example_weight),
            )
            raw_score = sum(
                getattr(profile.evidence_weights, field) * channels[field]
                for field in _WEIGHT_FIELDS
            ) / profile.evidence_weights.total
            scored.append((profile, raw_score, channels))
        baseline = [
            (
                profile,
                sum(
                    getattr(profile.evidence_weights, field)
                    * (0.0 if field == "personal_example" else channels[field])
                    for field in _WEIGHT_FIELDS
                )
                / profile.evidence_weights.total,
            )
            for profile, _raw_score, channels in scored
        ]
        baseline_label = max(baseline, key=lambda item: item[1])[0].template.value
        ranked = sorted(scored, key=lambda item: -item[1])
        candidates = tuple(
            CandidateScore(profile.template.value, raw_score)
            for profile, raw_score, _ in ranked
        )
        top_profile, top_score, top_channels = ranked[0]
        margin = top_score - candidates[1].raw_score
        contributions = tuple(
            EvidenceContribution(
                name=field,
                value=(
                    getattr(top_profile.evidence_weights, field)
                    * top_channels[field]
                    / top_profile.evidence_weights.total
                ),
                detail=(
                    f"raw={top_channels[field]:.6f}; "
                    f"weight={getattr(top_profile.evidence_weights, field):.6f}"
                ),
            )
            for field in _WEIGHT_FIELDS
        )
        return AxisDecision(
            label=top_profile.template.value,
            raw_score=top_score,
            calibrated_confidence=None,
            margin=max(0.0, margin),
            candidates=candidates,
            evidence=contributions,
            source=(
                DecisionSource.PERSONAL_EXAMPLE
                if top_profile.template.value != baseline_label
                and top_channels["personal_example"] != 0.0
                else DecisionSource.LOCAL
            ),
            model_version=self.encoder.model_id,
            profile_version=next(iter(versions)),
            policy_version=TEMPLATE_RANKING_POLICY_VERSION,
            needs_review=False,
        )
