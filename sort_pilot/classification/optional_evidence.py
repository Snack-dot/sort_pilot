from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PHASE8_OPTIONAL_EVIDENCE_VERSION = "phase-8-optional-evidence-v1"
DEFAULT_PHASE8_OPTIONAL_EVIDENCE_PATH = (
    Path(__file__).with_name("data") / "phase8_optional_evidence.json"
)
_FIELDS = {
    "version",
    "ocr_layout",
    "subject_kiwi_lexical_weight",
    "pmi",
    "yolo_lvis_visual",
    "model_session_scheduling",
}


@dataclass(frozen=True, slots=True)
class Phase8OptionalEvidence:
    """The measured Phase 8 evidence and low-end optimization decision."""

    ocr_layout: bool
    subject_kiwi_lexical_weight: float
    pmi: bool
    yolo_lvis_visual: bool
    model_session_scheduling: bool
    version: str = PHASE8_OPTIONAL_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        """Require the exact version, booleans, and a finite nonnegative weight."""
        if self.version != PHASE8_OPTIONAL_EVIDENCE_VERSION:
            raise ValueError("지원하지 않는 Phase 8 선택 버전입니다.")
        if not all(
            type(value) is bool
            for value in (
                self.ocr_layout,
                self.pmi,
                self.yolo_lvis_visual,
                self.model_session_scheduling,
            )
        ):
            raise ValueError("Phase 8 선택 값은 bool이어야 합니다.")
        weight = self.subject_kiwi_lexical_weight
        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(weight)
            or weight < 0
        ):
            raise ValueError("Phase 8 Kiwi 어휘 가중치는 유한한 음이 아닌 값이어야 합니다.")


@lru_cache(maxsize=None)
def load_phase8_optional_evidence(
    path: Path = DEFAULT_PHASE8_OPTIONAL_EVIDENCE_PATH,
) -> Phase8OptionalEvidence:
    """Load the strict measured Phase 8 selection from inspectable JSON."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise ValueError("Phase 8 선택 필드가 올바르지 않습니다.")
        return Phase8OptionalEvidence(
            ocr_layout=value["ocr_layout"],
            subject_kiwi_lexical_weight=value["subject_kiwi_lexical_weight"],
            pmi=value["pmi"],
            yolo_lvis_visual=value["yolo_lvis_visual"],
            model_session_scheduling=value["model_session_scheduling"],
            version=value["version"],
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(f"Phase 8 선택을 읽을 수 없습니다: {path}") from exc
