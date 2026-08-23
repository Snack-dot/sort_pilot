from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from sort_pilot.classification import DecisionSource

from .corpus import CorpusCase, Prediction


def _rate(numerator: int, denominator: int) -> float:
    """Return a zero-safe rate for evaluation output."""
    return numerator / denominator if denominator else 0.0


def _percentile(values: list[float], quantile: float) -> float:
    """Calculate a linearly interpolated percentile over measurements."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _measurement(value: float) -> float:
    """Round a resource measurement for stable readable JSON output."""
    return round(value, 6)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Required Phase 2 accuracy, routing, correction, and resource results."""

    total: int
    subject_correct: int
    template_correct: int
    combined_path_correct: int
    covered: int
    reviewed: int
    fallback_cases: int
    corrections: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_memory_mb: float
    max_memory_mb: float

    def to_dict(self) -> dict:
        """Serialize exactly the Phase 2 measures and total case count."""
        return {
            "cases": self.total,
            "subject_accuracy": _rate(self.subject_correct, self.total),
            "template_accuracy": _rate(self.template_correct, self.total),
            "combined_path_accuracy": _rate(self.combined_path_correct, self.total),
            "coverage": _rate(self.covered, self.total),
            "review_rate": _rate(self.reviewed, self.total),
            "fallback_rate": _rate(self.fallback_cases, self.total),
            "corrections": self.corrections,
            "latency_ms": {
                "mean": _measurement(self.mean_latency_ms),
                "p50": _measurement(self.p50_latency_ms),
                "p95": _measurement(self.p95_latency_ms),
            },
            "memory_mb": {
                "mean": _measurement(self.mean_memory_mb),
                "maximum": _measurement(self.max_memory_mb),
            },
        }


def evaluate_predictions(
    corpus: tuple[CorpusCase, ...],
    predictions: tuple[Prediction, ...],
) -> EvaluationReport:
    """Evaluate ordered predictions, counting unresolved axes as incorrect."""
    if not corpus:
        raise ValueError("평가 코퍼스는 비어 있을 수 없습니다.")
    if len(corpus) != len(predictions):
        raise ValueError("코퍼스 항목 수와 예측 항목 수가 일치해야 합니다.")

    subject_correct = template_correct = combined_path_correct = 0
    covered = reviewed = fallback_cases = corrections = 0
    latencies: list[float] = []
    memory: list[float] = []

    for expected, predicted in zip(corpus, predictions):
        if predicted.subject is not None and predicted.subject not in expected.student.allowed_subjects:
            raise ValueError("예측 과목이 선택한 학생 유형의 카탈로그 범위를 벗어났습니다.")

        subject_is_correct = (
            predicted.subject is not None and predicted.subject == expected.subject
        )
        template_is_correct = (
            predicted.template is not None and predicted.template == expected.template.value
        )
        is_covered = predicted.subject is not None and predicted.template is not None

        subject_correct += subject_is_correct
        template_correct += template_is_correct
        combined_path_correct += subject_is_correct and template_is_correct
        covered += is_covered
        reviewed += not is_covered
        fallback_cases += (
            predicted.subject_source is DecisionSource.GEMMA
            or predicted.template_source is DecisionSource.GEMMA
        )
        corrections += predicted.subject_corrected or predicted.template_corrected
        latencies.append(predicted.latency_ms)
        memory.append(predicted.memory_mb)

    return EvaluationReport(
        total=len(corpus),
        subject_correct=subject_correct,
        template_correct=template_correct,
        combined_path_correct=combined_path_correct,
        covered=covered,
        reviewed=reviewed,
        fallback_cases=fallback_cases,
        corrections=corrections,
        mean_latency_ms=fmean(latencies),
        p50_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
        mean_memory_mb=fmean(memory),
        max_memory_mb=max(memory),
    )
