from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .policy import RoutingThresholds


LOCAL_PRECISION_TARGET = 0.90
GEMMA_ACCURACY_TARGET = 0.50
CALIBRATED_POLICY_VERSION = "phase-5-held-out-v1"
DEFAULT_CALIBRATED_POLICY_PATH = (
    Path(__file__).with_name("data") / "calibrated_policy.json"
)


def _rate(correct: int, total: int) -> float:
    """Return a zero-safe empirical rate for calibration reports."""
    return correct / total if total else 0.0


@dataclass(frozen=True, slots=True)
class CalibrationTargets:
    """User-approved held-out operating targets for both classifier axes."""

    local_precision: float = LOCAL_PRECISION_TARGET
    gemma_accuracy: float = GEMMA_ACCURACY_TARGET

    def __post_init__(self) -> None:
        """Require finite rates strictly above zero and at most one."""
        for value in (self.local_precision, self.gemma_accuracy):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 < value <= 1.0
            ):
                raise ValueError("보정 목표는 0보다 크고 1 이하인 유한한 비율이어야 합니다.")
        object.__setattr__(self, "local_precision", float(self.local_precision))
        object.__setattr__(self, "gemma_accuracy", float(self.gemma_accuracy))

    def to_dict(self) -> dict[str, float]:
        """Serialize the two user-approved operating targets."""
        return {
            "local_precision": self.local_precision,
            "gemma_accuracy": self.gemma_accuracy,
        }


@dataclass(frozen=True, slots=True)
class HeldOutAxisResult:
    """One held-out local-axis result used only for threshold calibration."""

    raw_score: float
    margin: float
    correct: bool
    abstained: bool = False

    def __post_init__(self) -> None:
        """Validate finite raw evidence, nonnegative margin, and boolean labels."""
        if (
            isinstance(self.raw_score, bool)
            or not isinstance(self.raw_score, (int, float))
            or not math.isfinite(self.raw_score)
        ):
            raise ValueError("보정용 원점수는 유한한 숫자여야 합니다.")
        if (
            isinstance(self.margin, bool)
            or not isinstance(self.margin, (int, float))
            or not math.isfinite(self.margin)
            or self.margin < 0
        ):
            raise ValueError("보정용 상위 후보 간격은 0 이상의 유한한 숫자여야 합니다.")
        if type(self.correct) is not bool or type(self.abstained) is not bool:
            raise ValueError("보정용 정답과 명시적 기권 표시는 불리언이어야 합니다.")
        if self.abstained and self.correct:
            raise ValueError("명시적으로 기권한 결과는 정답으로 표시할 수 없습니다.")
        object.__setattr__(self, "raw_score", float(self.raw_score))
        object.__setattr__(self, "margin", float(self.margin))


@dataclass(frozen=True, slots=True)
class AxisCalibrationReport:
    """Calibrated thresholds and held-out routing measurements for one axis."""

    thresholds: RoutingThresholds
    held_out_cases: int
    accepted: int
    accepted_correct: int
    escalated: int
    escalated_correct: int
    reviewed: int
    targets: CalibrationTargets

    @property
    def local_precision(self) -> float:
        """Return held-out precision among authoritative local decisions."""
        return _rate(self.accepted_correct, self.accepted)

    @property
    def gemma_accuracy(self) -> float:
        """Return held-out top-label accuracy among Gemma-escalated decisions."""
        return _rate(self.escalated_correct, self.escalated)

    def to_dict(self) -> dict:
        """Serialize thresholds, counts, and achieved held-out rates."""
        return {
            "thresholds": {
                "high_score": self.thresholds.high_score,
                "high_margin": self.thresholds.high_margin,
                "gemma_score": self.thresholds.gemma_score,
            },
            "held_out_cases": self.held_out_cases,
            "accepted": self.accepted,
            "accepted_correct": self.accepted_correct,
            "local_precision": self.local_precision,
            "escalated": self.escalated,
            "escalated_correct": self.escalated_correct,
            "gemma_accuracy": self.gemma_accuracy,
            "reviewed": self.reviewed,
        }


@dataclass(frozen=True, slots=True)
class CalibratedPolicy:
    """Centralized per-axis thresholds produced from held-out labeled data."""

    subject: RoutingThresholds
    template: RoutingThresholds
    targets: CalibrationTargets
    version: str = CALIBRATED_POLICY_VERSION

    def __post_init__(self) -> None:
        """Validate both threshold sets, targets, and the nonblank policy version."""
        if not isinstance(self.subject, RoutingThresholds) or not isinstance(
            self.template, RoutingThresholds
        ):
            raise ValueError("과목과 템플릿에는 각각 보정된 임계값이 필요합니다.")
        if not isinstance(self.targets, CalibrationTargets):
            raise ValueError("보정 정책에는 사용자 승인 목표가 필요합니다.")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("보정 정책 버전은 비어 있지 않은 문자열이어야 합니다.")
        object.__setattr__(self, "version", self.version.strip())

    def thresholds_for(self, axis: str) -> RoutingThresholds:
        """Return the independently calibrated subject or template thresholds."""
        if axis == "subject":
            return self.subject
        if axis == "template":
            return self.template
        raise ValueError("보정 정책 축은 subject 또는 template이어야 합니다.")

    def to_dict(self) -> dict:
        """Serialize the centralized policy without held-out case contents."""
        def threshold_dict(value: RoutingThresholds) -> dict[str, float]:
            return {
                "high_score": value.high_score,
                "high_margin": value.high_margin,
                "gemma_score": value.gemma_score,
            }

        return {
            "version": self.version,
            "targets": self.targets.to_dict(),
            "subject": threshold_dict(self.subject),
            "template": threshold_dict(self.template),
        }


@dataclass(frozen=True, slots=True)
class PolicyCalibrationReport:
    """Complete subject/template held-out calibration result."""

    policy: CalibratedPolicy
    subject: AxisCalibrationReport
    template: AxisCalibrationReport

    def to_dict(self) -> dict:
        """Serialize the central policy and per-axis achieved measurements."""
        return {
            "policy": self.policy.to_dict(),
            "subject_calibration": self.subject.to_dict(),
            "template_calibration": self.template.to_dict(),
        }


def _measure_thresholds(
    results: tuple[HeldOutAxisResult, ...],
    thresholds: RoutingThresholds,
    targets: CalibrationTargets,
) -> AxisCalibrationReport:
    """Measure one threshold set against held-out axis results."""
    accepted: list[HeldOutAxisResult] = []
    escalated: list[HeldOutAxisResult] = []
    reviewed: list[HeldOutAxisResult] = []
    for result in results:
        if result.abstained:
            reviewed.append(result)
        elif (
            result.raw_score >= thresholds.high_score
            and result.margin >= thresholds.high_margin
        ):
            accepted.append(result)
        elif result.raw_score >= thresholds.gemma_score:
            escalated.append(result)
        else:
            reviewed.append(result)
    return AxisCalibrationReport(
        thresholds=thresholds,
        held_out_cases=len(results),
        accepted=len(accepted),
        accepted_correct=sum(result.correct for result in accepted),
        escalated=len(escalated),
        escalated_correct=sum(result.correct for result in escalated),
        reviewed=len(reviewed),
        targets=targets,
    )


def calibrate_axis(
    results: tuple[HeldOutAxisResult, ...],
    targets: CalibrationTargets,
) -> AxisCalibrationReport:
    """Select the broadest held-out routes that satisfy both approved targets."""
    if not isinstance(results, tuple) or not results or not all(
        isinstance(result, HeldOutAxisResult) for result in results
    ):
        raise ValueError("축 보정에는 비어 있지 않은 held-out 결과 튜플이 필요합니다.")
    if not isinstance(targets, CalibrationTargets):
        raise ValueError("축 보정에는 사용자 승인 목표가 필요합니다.")
    usable = tuple(result for result in results if not result.abstained)
    if not usable:
        raise ValueError("명시적 기권이 아닌 held-out 결과가 필요합니다.")

    scores = sorted({result.raw_score for result in usable})
    margins = sorted({result.margin for result in usable})
    best: tuple[tuple, AxisCalibrationReport] | None = None
    for high_score in scores:
        for high_margin in margins:
            for gemma_score in (score for score in scores if score <= high_score):
                thresholds = RoutingThresholds(
                    high_score=high_score,
                    high_margin=high_margin,
                    gemma_score=gemma_score,
                )
                report = _measure_thresholds(results, thresholds, targets)
                if (
                    not report.accepted
                    or report.local_precision < targets.local_precision
                    or not report.escalated
                    or report.gemma_accuracy < targets.gemma_accuracy
                ):
                    continue
                objective = (
                    report.accepted,
                    report.escalated,
                    report.local_precision,
                    report.gemma_accuracy,
                    -report.reviewed,
                    -high_score,
                    -high_margin,
                    -gemma_score,
                )
                if best is None or objective > best[0]:
                    best = (objective, report)
    if best is None:
        raise ValueError("held-out 결과에서 승인된 보정 목표를 만족하는 임계값을 찾지 못했습니다.")
    return best[1]


def calibrate_policy(
    subject_results: tuple[HeldOutAxisResult, ...],
    template_results: tuple[HeldOutAxisResult, ...],
    targets: CalibrationTargets = CalibrationTargets(),
    version: str = CALIBRATED_POLICY_VERSION,
) -> PolicyCalibrationReport:
    """Calibrate independent subject and template routes from held-out data."""
    subject = calibrate_axis(subject_results, targets)
    template = calibrate_axis(template_results, targets)
    policy = CalibratedPolicy(
        subject=subject.thresholds,
        template=template.thresholds,
        targets=targets,
        version=version,
    )
    return PolicyCalibrationReport(policy=policy, subject=subject, template=template)


@lru_cache(maxsize=None)
def load_calibrated_policy(
    path: Path = DEFAULT_CALIBRATED_POLICY_PATH,
) -> CalibratedPolicy:
    """Load the strict centralized Phase 5 policy produced from held-out data."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {
            "version",
            "targets",
            "subject",
            "template",
        }:
            raise ValueError("보정 정책의 최상위 필드가 올바르지 않습니다.")
        if data["version"] != CALIBRATED_POLICY_VERSION:
            raise ValueError("지원하지 않는 보정 정책 버전입니다.")
        targets = data["targets"]
        if not isinstance(targets, dict) or set(targets) != {
            "local_precision",
            "gemma_accuracy",
        }:
            raise ValueError("보정 목표 필드가 올바르지 않습니다.")
        parsed_targets = CalibrationTargets(**targets)
        if parsed_targets != CalibrationTargets():
            raise ValueError("보정 목표가 사용자 승인 값과 일치하지 않습니다.")

        threshold_fields = {"high_score", "high_margin", "gemma_score"}
        parsed: dict[str, RoutingThresholds] = {}
        for axis in ("subject", "template"):
            value = data[axis]
            if not isinstance(value, dict) or set(value) != threshold_fields:
                raise ValueError("축별 보정 임계값 필드가 올바르지 않습니다.")
            parsed[axis] = RoutingThresholds(**value)
        return CalibratedPolicy(
            subject=parsed["subject"],
            template=parsed["template"],
            targets=parsed_targets,
            version=data["version"],
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"보정 정책을 읽을 수 없습니다: {path}") from exc
