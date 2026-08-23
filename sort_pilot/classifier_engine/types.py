from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Feature:
    """One weighted token and its extraction source."""

    t: str
    src: str
    n: float = 1.0


@dataclass
class FeatureVector:
    """Complete bounded local feature representation of one file."""

    file_id: str
    path: str
    size: int
    features: list[Feature] = field(default_factory=list)
    partial: bool = False
    route: str = "metadata"
    extractor_ms: dict[str, float] = field(default_factory=dict)
    peak_rss_mb: float = 0.0
    natural_text: str = field(default="", repr=False)
    template_natural_text: str = field(default="", repr=False)
    ocr_layout_evidence: tuple[str, ...] = field(default=(), repr=False)
    numeric_features: dict[str, float] = field(default_factory=dict)
    extraction_quality: str = "ok"
    ocr_confidence: float | None = None

    def to_dict(self) -> dict:
        """Serialize classifier features without persisting raw extracted text."""
        value = asdict(self)
        value.pop("natural_text", None)
        value.pop("template_natural_text", None)
        value.pop("ocr_layout_evidence", None)
        return value


@dataclass
class Decision:
    """Classifier category, confidence evidence, action gate, and explanation."""

    category: str | None
    score: float
    margin: float
    n_eff: float
    action: str
    tier: str
    explanation: list[dict] = field(default_factory=list)


class Classifier(Protocol):
    """Protocol for optional higher-tier local classifiers."""

    def classify(self, vector: FeatureVector, candidates: list[str]) -> Decision | None:
        """Return a decision for a feature vector or decline classification."""
        ...


class Tier3Stub:
    """Disabled-by-default extension point for a future local classifier."""

    def classify(self, vector: FeatureVector, candidates: list[str]) -> Decision | None:
        """Decline classification until a Tier 3 implementation is configured."""
        return None


def path_id(path: Path) -> str:
    """Hash only resolved path, size, and mtime metadata; never read the file body."""
    import hashlib

    stat = path.stat()
    value = f"{path.resolve()}\0{stat.st_mtime_ns}\0{stat.st_size}".encode("utf-8")
    return "sha1:" + hashlib.sha1(value).hexdigest()
