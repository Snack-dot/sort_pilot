from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Feature:
    """One weighted token and its extraction source."""

    t: str
    src: str
    n: float = 1.0


@dataclass
class FeatureVector:
    """Complete bounded local feature representation of one file."""

    features: list[Feature] = field(default_factory=list)
    partial: bool = False
