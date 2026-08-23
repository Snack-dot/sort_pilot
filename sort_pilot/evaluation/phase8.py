from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from sort_pilot.classification import Template
from sort_pilot.curriculum import Semester, StudentProfile, StudentType


PHASE8_CORPUS_VERSION = "1"
MINIMUM_ACCURACY_GAIN = 0.05
SIGNIFICANCE_ALPHA = 0.05
MAXIMUM_P95_LATENCY_RATIO = 1.10
MAXIMUM_PEAK_MEMORY_MB = 2048.0

_CASE_FIELDS = {
    "file_name",
    "phase7_text",
    "layout_text",
    "student_type",
    "grade",
    "semester",
    "subject",
    "template",
    "pmi_collocations",
    "ocr_layout_evidence",
    "visual_evidence",
}


@dataclass(frozen=True, slots=True)
class Phase8Case:
    """One direct made-up case for paired optional-evidence measurement."""

    file_name: str
    phase7_text: str
    layout_text: str
    student: StudentProfile
    subject: str
    template: Template
    pmi_collocations: tuple[str, ...]
    ocr_layout_evidence: tuple[str, ...]
    visual_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require bounded natural text, exact labels, and separate evidence channels."""
        if (
            not isinstance(self.file_name, str)
            or not self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
        ):
            raise ValueError("Phase 8 사례에는 경로가 아닌 파일 이름이 필요합니다.")
        if not isinstance(self.phase7_text, str) or not isinstance(self.layout_text, str):
            raise ValueError("Phase 8 OCR 텍스트는 문자열이어야 합니다.")
        if not self.layout_text.strip():
            raise ValueError("Phase 8 레이아웃 OCR 텍스트는 비어 있을 수 없습니다.")
        if self.subject not in self.student.allowed_subjects:
            raise ValueError("Phase 8 과목 라벨은 선택한 학생 유형의 카탈로그에 있어야 합니다.")
        if not isinstance(self.template, Template):
            raise ValueError("Phase 8 템플릿 라벨은 고정된 다섯 템플릿 중 하나여야 합니다.")
        for field in ("pmi_collocations", "ocr_layout_evidence", "visual_evidence"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ValueError("Phase 8 구조화 근거는 비어 있지 않은 문자열 튜플이어야 합니다.")
            if len(values) != len(set(values)):
                raise ValueError("Phase 8 구조화 근거는 중복될 수 없습니다.")


def load_phase8_corpus(path: Path) -> tuple[Phase8Case, ...]:
    """Load strict ordered made-up Phase 8 cases without invented identifiers."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or set(document) != {"version", "cases"}:
            raise ValueError("Phase 8 corpus 최상위 필드가 올바르지 않습니다.")
        if document["version"] != PHASE8_CORPUS_VERSION:
            raise ValueError("지원하지 않는 Phase 8 corpus 버전입니다.")
        if not isinstance(document["cases"], list) or not document["cases"]:
            raise ValueError("Phase 8 corpus에는 하나 이상의 사례가 필요합니다.")
        cases: list[Phase8Case] = []
        for raw in document["cases"]:
            if not isinstance(raw, dict) or set(raw) != _CASE_FIELDS:
                raise ValueError("Phase 8 사례 필드가 올바르지 않습니다.")
            if (
                not isinstance(raw["student_type"], str)
                or type(raw["grade"]) is not int
                or not isinstance(raw["semester"], str)
                or not isinstance(raw["subject"], str)
                or not isinstance(raw["template"], str)
            ):
                raise ValueError("Phase 8 학생 정보와 라벨의 타입이 올바르지 않습니다.")
            evidence = (
                raw["pmi_collocations"],
                raw["ocr_layout_evidence"],
                raw["visual_evidence"],
            )
            if any(
                not isinstance(values, list)
                or not all(isinstance(value, str) for value in values)
                for values in evidence
            ):
                raise ValueError("Phase 8 구조화 근거는 문자열 목록이어야 합니다.")
            cases.append(
                Phase8Case(
                    file_name=raw["file_name"],
                    phase7_text=raw["phase7_text"],
                    layout_text=raw["layout_text"],
                    student=StudentProfile(
                        StudentType(raw["student_type"]),
                        raw["grade"],
                        Semester(raw["semester"]),
                    ),
                    subject=raw["subject"],
                    template=Template(raw["template"]),
                    pmi_collocations=tuple(raw["pmi_collocations"]),
                    ocr_layout_evidence=tuple(raw["ocr_layout_evidence"]),
                    visual_evidence=tuple(raw["visual_evidence"]),
                )
            )
        return tuple(cases)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(f"Phase 8 corpus를 읽을 수 없습니다: {path}") from exc


def _exact_mcnemar_p_value(improved: int, regressed: int) -> float:
    """Return the two-sided exact paired McNemar binomial probability."""
    discordant = improved + regressed
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, value)
        for value in range(min(improved, regressed) + 1)
    ) / (2**discordant)
    return min(1.0, 2.0 * tail)


@dataclass(frozen=True, slots=True)
class PairedAccuracy:
    """One paired baseline/candidate accuracy comparison."""

    cases: int
    baseline_correct: int
    candidate_correct: int
    improved: int
    regressed: int
    p_value: float

    @property
    def baseline_accuracy(self) -> float:
        """Return baseline accuracy as a zero-to-one rate."""
        return self.baseline_correct / self.cases

    @property
    def candidate_accuracy(self) -> float:
        """Return candidate accuracy as a zero-to-one rate."""
        return self.candidate_correct / self.cases

    @property
    def gain(self) -> float:
        """Return the candidate minus baseline accuracy difference."""
        return self.candidate_accuracy - self.baseline_accuracy

    @property
    def passes(self) -> bool:
        """Return whether this metric clears the agreed gain and significance gates."""
        return self.gain >= MINIMUM_ACCURACY_GAIN and self.p_value < SIGNIFICANCE_ALPHA

    def to_dict(self) -> dict:
        """Serialize counts, rates, gain, significance, and gate outcome."""
        return {
            "cases": self.cases,
            "baseline_correct": self.baseline_correct,
            "candidate_correct": self.candidate_correct,
            "baseline_accuracy": self.baseline_accuracy,
            "candidate_accuracy": self.candidate_accuracy,
            "gain": self.gain,
            "improved": self.improved,
            "regressed": self.regressed,
            "p_value": self.p_value,
            "passes": self.passes,
        }


def paired_accuracy(
    baseline: tuple[bool, ...],
    candidate: tuple[bool, ...],
) -> PairedAccuracy:
    """Calculate one strict paired accuracy result from ordered correctness values."""
    if not baseline or len(baseline) != len(candidate):
        raise ValueError("paired accuracy에는 길이가 같은 비어 있지 않은 결과가 필요합니다.")
    if not all(type(value) is bool for value in (*baseline, *candidate)):
        raise ValueError("paired accuracy 결과는 bool이어야 합니다.")
    improved = sum(not old and new for old, new in zip(baseline, candidate, strict=True))
    regressed = sum(old and not new for old, new in zip(baseline, candidate, strict=True))
    return PairedAccuracy(
        cases=len(baseline),
        baseline_correct=sum(baseline),
        candidate_correct=sum(candidate),
        improved=improved,
        regressed=regressed,
        p_value=_exact_mcnemar_p_value(improved, regressed),
    )


@dataclass(frozen=True, slots=True)
class ResourceMeasurement:
    """Measured per-file P95 latency and process peak memory."""

    p95_latency_ms: float
    peak_memory_mb: float

    def __post_init__(self) -> None:
        """Require finite nonnegative resource measurements."""
        for value in (self.p95_latency_ms, self.peak_memory_mb):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("Phase 8 resource measurement는 유한한 음이 아닌 값이어야 합니다.")

    def to_dict(self) -> dict[str, float]:
        """Serialize the two agreed resource measurements."""
        return {
            "p95_latency_ms": float(self.p95_latency_ms),
            "peak_memory_mb": float(self.peak_memory_mb),
        }


@dataclass(frozen=True, slots=True)
class Phase8GateReport:
    """Complete agreed Phase 8 accuracy, latency, and memory decision."""

    subject: PairedAccuracy
    template: PairedAccuracy
    combined_path: PairedAccuracy
    baseline_resources: ResourceMeasurement
    candidate_resources: ResourceMeasurement

    @property
    def latency_ratio(self) -> float:
        """Return candidate P95 latency divided by the Phase 7 baseline."""
        if self.baseline_resources.p95_latency_ms == 0:
            return 1.0 if self.candidate_resources.p95_latency_ms == 0 else math.inf
        return (
            self.candidate_resources.p95_latency_ms
            / self.baseline_resources.p95_latency_ms
        )

    @property
    def passes(self) -> bool:
        """Return true only when the complete selected configuration clears every gate."""
        return (
            self.subject.passes
            and self.template.passes
            and self.combined_path.passes
            and self.latency_ratio <= MAXIMUM_P95_LATENCY_RATIO
            and self.candidate_resources.peak_memory_mb <= MAXIMUM_PEAK_MEMORY_MB
        )

    def to_dict(self) -> dict:
        """Serialize every agreed gate and the final retain-or-reject result."""
        return {
            "gate": {
                "minimum_accuracy_gain": MINIMUM_ACCURACY_GAIN,
                "significance_alpha": SIGNIFICANCE_ALPHA,
                "maximum_p95_latency_ratio": MAXIMUM_P95_LATENCY_RATIO,
                "maximum_peak_memory_mb": MAXIMUM_PEAK_MEMORY_MB,
            },
            "subject": self.subject.to_dict(),
            "template": self.template.to_dict(),
            "combined_path": self.combined_path.to_dict(),
            "baseline_resources": self.baseline_resources.to_dict(),
            "candidate_resources": self.candidate_resources.to_dict(),
            "latency_ratio": self.latency_ratio,
            "passes": self.passes,
        }
