from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .extract import SEMANTIC_FEATURE_SOURCES
from .hierarchy import UNSORTED_TOPIC, hierarchical_folder
from .types import FeatureVector

WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
GENERIC_PREFIXES = ("n_person:", "n_objects:", "subject:")


def normalize_tag(tag: str) -> str:
    """Normalize one extracted term for stable case-insensitive comparison."""
    return " ".join(tag.casefold().strip().split())


def validate_topic_name(name: str) -> str:
    """Validate and return one safe folder-path component."""
    candidate = name.strip().rstrip(". ")
    if not candidate:
        raise ValueError("정리 폴더 이름을 입력하세요.")
    if candidate.casefold() == UNSORTED_TOPIC.casefold():
        raise ValueError(f"'{UNSORTED_TOPIC}'는 예약된 이름입니다.")
    if candidate in {".", ".."} or WINDOWS_INVALID.search(candidate):
        raise ValueError("폴더 이름에 사용할 수 없는 문자가 있습니다.")
    return candidate


@dataclass(slots=True)
class AnalysisRecord:
    """One locally extracted file awaiting role-aware LLM classification."""

    file_path: str
    file_name: str
    suggested_name: str
    family: str
    terms: dict[str, float]
    content_extraction_failed: bool = False

    @property
    def source(self) -> Path:
        """Return the analyzed source path."""
        return Path(self.file_path)

    @property
    def folder(self) -> str:
        """Return the compatibility fallback used before LLM classification."""
        return hierarchical_folder(self.family)


def humanize_term(term: str) -> str | None:
    """Convert an extracted feature token into bounded human-readable evidence."""
    if term.startswith(("bi:", "tri:")):
        return term.split(":", 1)[1]
    if term.startswith("obj:"):
        return term[len("obj:"):].replace("_", " ")
    if term.startswith(("pair:", "co:")):
        return None
    return term


def vector_terms(vector: FeatureVector, source_weights: dict[str, float]) -> dict[str, float]:
    """Retain only body, OCR, and object evidence sent to the local LLM."""
    terms: Counter[str] = Counter()
    for feature in vector.features:
        token = normalize_tag(feature.t)
        if not token or token.startswith(GENERIC_PREFIXES):
            continue
        if feature.src not in SEMANTIC_FEATURE_SOURCES:
            continue
        terms[token] += float(feature.n) * float(source_weights.get(feature.src, 1.0))
    return dict(terms)
