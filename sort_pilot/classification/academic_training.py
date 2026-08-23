from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from sort_pilot.curriculum import Semester, StudentProfile, StudentType

from .e5 import E5SubjectClassifier, SubjectTextEncoder, _embedding_matrix
from .optional_evidence import Phase8OptionalEvidence, load_phase8_optional_evidence
from .subject import SubjectEvidence, SubjectProfile, eligible_subject_profiles
from .template import _indicator_score
from .tfidf import HashedWordCharacterTfidf


ACADEMIC_TOP_CATEGORY = "학업"
ACADEMIC_TYPES = ("교재", "문제지", "정답지")
ACADEMIC_TYPE_PROFILE_VERSION = "1"
DEFAULT_ACADEMIC_TYPE_PROFILES_PATH = (
    Path(__file__).with_name("data") / "academic_type_profiles_ko.json"
)
_TYPE_PROFILE_FIELDS = {
    "prototype_texts",
    "file_name_indicators",
    "lexical_indicators",
    "pmi_collocations",
    "ocr_layout_indicators",
}
PDF_NUMERIC_FEATURE_NAMES = (
    "pdf_page_count",
    "pdf_sampled_page_count",
    "pdf_scan_ratio",
    "pdf_image_ratio",
    "pdf_text_characters_per_page",
)


@dataclass(frozen=True, slots=True)
class AcademicTypeProfile:
    """Inspectable evidence profile for one user-approved academic document type."""

    label: str
    prototype_texts: tuple[str, ...]
    file_name_indicators: tuple[str, ...]
    lexical_indicators: tuple[str, ...]
    pmi_collocations: tuple[str, ...]
    ocr_layout_indicators: tuple[str, ...]
    version: str = ACADEMIC_TYPE_PROFILE_VERSION

    def __post_init__(self) -> None:
        if self.label not in ACADEMIC_TYPES:
            raise ValueError("Unsupported academic document type.")
        for field in _TYPE_PROFILE_FIELDS:
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) for value in values
            ):
                raise ValueError("Academic type evidence must be string tuples.")
            normalized = tuple(
                dict.fromkeys(value.strip() for value in values if value.strip())
            )
            if not normalized:
                raise ValueError("Academic type evidence cannot be empty.")
            object.__setattr__(self, field, normalized)
        if self.version != ACADEMIC_TYPE_PROFILE_VERSION:
            raise ValueError("Unsupported academic type profile version.")


@dataclass(frozen=True, slots=True)
class AcademicTrainingEvidence:
    """Transient path-free evidence extracted from one sandbox file."""

    file_name: str
    natural_text: str
    template_natural_text: str
    lexical_terms: tuple[str, ...] = ()
    pmi_collocations: tuple[str, ...] = ()
    ocr_layout_terms: tuple[str, ...] = ()
    numeric_features: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.file_name, str)
            or not self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
        ):
            raise ValueError("Academic evidence requires one filename, not a path.")
        for field in ("natural_text", "template_natural_text"):
            if not isinstance(getattr(self, field), str):
                raise ValueError("Academic natural evidence must be text.")
        for field in ("lexical_terms", "pmi_collocations", "ocr_layout_terms"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) for value in values
            ):
                raise ValueError("Academic structured evidence must be string tuples.")
        if self.numeric_features is None:
            object.__setattr__(self, "numeric_features", {})
        elif not isinstance(self.numeric_features, dict) or any(
            key not in PDF_NUMERIC_FEATURE_NAMES
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for key, value in self.numeric_features.items()
        ):
            raise ValueError("Academic numeric evidence must use finite PDF features.")
        else:
            object.__setattr__(
                self,
                "numeric_features",
                {key: float(value) for key, value in self.numeric_features.items()},
            )


@dataclass(frozen=True, slots=True)
class AcademicBaseFeatures:
    """Reusable non-personal feature matrices and transparent baseline predictions."""

    subject_matrix: np.ndarray
    academic_type_matrix: np.ndarray
    subject_embeddings: np.ndarray
    academic_type_embeddings: np.ndarray
    subject_feature_names: tuple[str, ...]
    academic_type_feature_names: tuple[str, ...]
    subject_labels: tuple[str, ...]
    academic_type_labels: tuple[str, ...]
    subject_baseline: tuple[str, ...]
    academic_type_baseline: tuple[str, ...]
    subject_texts: tuple[str, ...]
    academic_type_texts: tuple[str, ...]
    subject_tfidf: HashedWordCharacterTfidf
    academic_type_tfidf: HashedWordCharacterTfidf


class AcademicFeatureBuilder:
    """Build E5, margin, lexical, PMI, OCR, and weighted-policy features."""

    def __init__(
        self,
        encoder: SubjectTextEncoder,
        subject_profiles: tuple[SubjectProfile, ...],
        academic_type_profiles: tuple[AcademicTypeProfile, ...],
        optional_evidence: Phase8OptionalEvidence | None = None,
    ) -> None:
        self.encoder = encoder
        self.student = StudentProfile(StudentType.HIGH, 1, Semester.FIRST)
        self.subject_profiles = eligible_subject_profiles(self.student, subject_profiles)
        if tuple(profile.label for profile in academic_type_profiles) != ACADEMIC_TYPES:
            raise ValueError("Academic type profiles must use the fixed configured order.")
        self.academic_type_profiles = academic_type_profiles
        self.optional_evidence = optional_evidence or load_phase8_optional_evidence()
        self.subject_classifier = E5SubjectClassifier(encoder)

    def build(self, evidence: Sequence[AcademicTrainingEvidence]) -> AcademicBaseFeatures:
        """Encode a batch once and retain all interpretable non-personal channels."""
        items = tuple(evidence)
        if not items:
            raise ValueError("Academic training evidence cannot be empty.")
        subject_texts = tuple(
            f"query: {SubjectEvidence(item.file_name, item.natural_text).embedding_text}"
            for item in items
        )
        type_texts = tuple(
            f"query: {SubjectEvidence(item.file_name, item.template_natural_text).embedding_text}"
            for item in items
        )
        unique_texts = tuple(dict.fromkeys((*subject_texts, *type_texts)))
        unique_embeddings = _embedding_matrix(
            self.encoder.encode(unique_texts), len(unique_texts)
        )
        index = {value: position for position, value in enumerate(unique_texts)}
        subject_embeddings = np.asarray(
            [unique_embeddings[index[value]] for value in subject_texts], dtype=np.float64
        )
        type_embeddings = np.asarray(
            [unique_embeddings[index[value]] for value in type_texts], dtype=np.float64
        )
        subject_matrix, subject_names, subject_baseline = self._subject_features(
            items, subject_embeddings
        )
        type_matrix, type_names, type_baseline = self._type_features(
            items, type_embeddings
        )
        subject_natural_texts = tuple(item.natural_text for item in items)
        type_natural_texts = tuple(item.template_natural_text for item in items)
        subject_tfidf = HashedWordCharacterTfidf.fit(subject_natural_texts)
        type_tfidf = HashedWordCharacterTfidf.fit(type_natural_texts)
        numeric = np.asarray(
            [
                [float((item.numeric_features or {}).get(name, 0.0)) for name in PDF_NUMERIC_FEATURE_NAMES]
                for item in items
            ],
            dtype=np.float64,
        )
        numeric_names = tuple(f"numeric:{name}" for name in PDF_NUMERIC_FEATURE_NAMES)
        subject_matrix = np.column_stack((subject_matrix, numeric))
        type_matrix = np.column_stack((type_matrix, numeric))
        subject_names = (*subject_names, *numeric_names)
        type_names = (*type_names, *numeric_names)
        return AcademicBaseFeatures(
            subject_matrix=subject_matrix,
            academic_type_matrix=type_matrix,
            subject_embeddings=subject_embeddings,
            academic_type_embeddings=type_embeddings,
            subject_feature_names=subject_names,
            academic_type_feature_names=type_names,
            subject_labels=tuple(profile.label for profile in self.subject_profiles),
            academic_type_labels=ACADEMIC_TYPES,
            subject_baseline=subject_baseline,
            academic_type_baseline=type_baseline,
            subject_texts=subject_natural_texts,
            academic_type_texts=type_natural_texts,
            subject_tfidf=subject_tfidf,
            academic_type_tfidf=type_tfidf,
        )

    def _subject_features(
        self,
        items: tuple[AcademicTrainingEvidence, ...],
        embeddings: np.ndarray,
    ) -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...]]:
        labels = tuple(profile.label for profile in self.subject_profiles)
        profile_matrix = self.subject_classifier._profile_embeddings(self.subject_profiles)
        similarities = np.clip(embeddings @ profile_matrix.T, -1.0, 1.0)
        rows: list[list[float]] = []
        baselines: list[str] = []
        channels = ("e5", "lexical", "filename", "pmi", "language", "weighted")
        names = tuple(f"{channel}:{label}" for channel in channels for label in labels) + (
            "weighted:top_score",
            "weighted:margin",
        )
        for item, similarity in zip(items, similarities, strict=True):
            value = SubjectEvidence(
                file_name=item.file_name,
                natural_text=item.natural_text,
                lexical_terms=item.lexical_terms,
                pmi_collocations=(
                    item.pmi_collocations if self.optional_evidence.pmi else ()
                ),
            )
            lexical = self.subject_classifier._lexical_scores(value, self.subject_profiles)
            filename = self.subject_classifier._filename_scores(value, self.subject_profiles)
            pmi = self.subject_classifier._pmi_scores(value, self.subject_profiles)
            language = self.subject_classifier._language_scores(value, self.subject_profiles)
            lexical_values = np.asarray([lexical[label] for label in labels])
            filename_values = np.asarray([filename[label] for label in labels])
            pmi_values = np.asarray([pmi[label] for label in labels])
            language_values = np.asarray([language[label] for label in labels])
            weighted = (
                similarity
                + self.optional_evidence.subject_kiwi_lexical_weight * lexical_values
                + self.optional_evidence.subject_filename_weight * filename_values
                + self.optional_evidence.subject_pmi_weight * pmi_values
                + self.optional_evidence.subject_language_weight * language_values
            )
            order = np.argsort(-weighted)
            baselines.append(labels[int(order[0])])
            rows.append(
                [
                    *similarity,
                    *lexical_values,
                    *filename_values,
                    *pmi_values,
                    *language_values,
                    *weighted,
                    float(weighted[order[0]]),
                    float(weighted[order[0]] - weighted[order[1]]),
                ]
            )
        return np.asarray(rows, dtype=np.float64), names, tuple(baselines)

    def _type_features(
        self,
        items: tuple[AcademicTrainingEvidence, ...],
        embeddings: np.ndarray,
    ) -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...]]:
        profiles = self.academic_type_profiles
        labels = tuple(profile.label for profile in profiles)
        prototype_texts: list[str] = []
        owners: list[int] = []
        for position, profile in enumerate(profiles):
            for text in profile.prototype_texts:
                prototype_texts.append(f"passage: {text}")
                owners.append(position)
        prototype_embeddings = _embedding_matrix(
            self.encoder.encode(tuple(prototype_texts)), len(prototype_texts)
        )
        owner_array = np.asarray(owners)
        profile_matrix = np.asarray(
            [
                _embedding_matrix((prototype_embeddings[owner_array == position].mean(axis=0),), 1)[
                    0
                ]
                for position in range(len(profiles))
            ],
            dtype=np.float64,
        )
        similarities = np.clip(embeddings @ profile_matrix.T, -1.0, 1.0)
        channels = ("e5", "filename", "lexical", "pmi", "ocr_layout", "weighted")
        names = tuple(f"{channel}:{label}" for channel in channels for label in labels) + (
            "weighted:top_score",
            "weighted:margin",
        )
        rows: list[list[float]] = []
        baselines: list[str] = []
        for item, similarity in zip(items, similarities, strict=True):
            filename = np.asarray(
                [
                    _indicator_score((Path(item.file_name).stem,), profile.file_name_indicators)
                    for profile in profiles
                ]
            )
            lexical = np.asarray(
                [
                    _indicator_score(item.lexical_terms, profile.lexical_indicators)
                    for profile in profiles
                ]
            )
            pmi = np.asarray(
                [
                    _indicator_score(item.pmi_collocations, profile.pmi_collocations)
                    for profile in profiles
                ]
            )
            layout = np.asarray(
                [
                    _indicator_score(item.ocr_layout_terms, profile.ocr_layout_indicators)
                    for profile in profiles
                ]
            )
            weighted = (similarity + filename + lexical + pmi + layout) / 5.0
            order = np.argsort(-weighted)
            baselines.append(labels[int(order[0])])
            rows.append(
                [
                    *similarity,
                    *filename,
                    *lexical,
                    *pmi,
                    *layout,
                    *weighted,
                    float(weighted[order[0]]),
                    float(weighted[order[0]] - weighted[order[1]]),
                ]
            )
        return np.asarray(rows, dtype=np.float64), names, tuple(baselines)


def personal_similarity_features(
    query_embeddings: np.ndarray,
    reference_embeddings: np.ndarray,
    reference_targets: Sequence[str],
    labels: Sequence[str],
    *,
    query_reference_indices: Sequence[int | None] | None = None,
) -> np.ndarray:
    """Return per-label nearest approved-example cosine scores without self leakage."""
    query = np.asarray(query_embeddings, dtype=np.float64)
    reference = np.asarray(reference_embeddings, dtype=np.float64)
    if query.ndim != 2 or reference.ndim != 2 or query.shape[1:] != reference.shape[1:]:
        raise ValueError("Personal similarity embedding shapes do not match.")
    if not np.isfinite(query).all() or not np.isfinite(reference).all():
        raise ValueError("Personal similarity embeddings must be finite.")
    targets = tuple(reference_targets)
    configured = tuple(labels)
    if len(targets) != len(reference) or any(value not in configured for value in targets):
        raise ValueError("Personal reference targets do not match configured labels.")
    excluded = tuple(query_reference_indices or (None,) * len(query))
    if len(excluded) != len(query):
        raise ValueError("Personal exclusion indices must match query rows.")
    similarities = np.clip(query @ reference.T, -1.0, 1.0)
    result = np.full((len(query), len(configured)), -1.0, dtype=np.float64)
    target_array = np.asarray(targets)
    for row, excluded_index in enumerate(excluded):
        for column, label in enumerate(configured):
            candidates = np.flatnonzero(target_array == label)
            if excluded_index is not None:
                candidates = candidates[candidates != excluded_index]
            if len(candidates):
                result[row, column] = float(similarities[row, candidates].max())
    return result


@lru_cache(maxsize=None)
def load_academic_type_profiles(
    path: Path = DEFAULT_ACADEMIC_TYPE_PROFILES_PATH,
) -> tuple[AcademicTypeProfile, ...]:
    """Load the strict user-approved 학업/{교재|문제지|정답지} profile set."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"version", "top_category", "types"}:
            raise ValueError
        if (
            data["version"] != ACADEMIC_TYPE_PROFILE_VERSION
            or data["top_category"] != ACADEMIC_TOP_CATEGORY
            or not isinstance(data["types"], dict)
            or tuple(data["types"]) != ACADEMIC_TYPES
        ):
            raise ValueError
        profiles: list[AcademicTypeProfile] = []
        for label in ACADEMIC_TYPES:
            value = data["types"][label]
            if not isinstance(value, dict) or set(value) != _TYPE_PROFILE_FIELDS:
                raise ValueError
            if any(
                not isinstance(value[field], list)
                or not value[field]
                or not all(isinstance(item, str) for item in value[field])
                for field in _TYPE_PROFILE_FIELDS
            ):
                raise ValueError
            profiles.append(
                AcademicTypeProfile(
                    label=label,
                    prototype_texts=tuple(value["prototype_texts"]),
                    file_name_indicators=tuple(value["file_name_indicators"]),
                    lexical_indicators=tuple(value["lexical_indicators"]),
                    pmi_collocations=tuple(value["pmi_collocations"]),
                    ocr_layout_indicators=tuple(value["ocr_layout_indicators"]),
                    version=data["version"],
                )
            )
        return tuple(profiles)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise RuntimeError(f"Academic type profiles cannot be loaded: {path}") from exc
