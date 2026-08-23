from __future__ import annotations

import math
from dataclasses import dataclass

from .calibrated_policy import CalibrationTargets
from .personal_examples import (
    AxisPersonalExamplePolicy,
    PersonalExamplePolicy,
)
from .policy import PolicyRoute, RoutingThresholds
from .result import CandidateScore


@dataclass(frozen=True, slots=True)
class PersonalCalibrationCase:
    """One made-up held-out ranking with nearest personal-example similarities."""

    candidates: tuple[CandidateScore, ...]
    similarities: tuple[CandidateScore, ...]
    correct_label: str
    contribution_scale: float = 1.0

    def __post_init__(self) -> None:
        """Validate ranked candidates, bounded similarities, label, and scale."""
        if not self.candidates or not all(
            isinstance(item, CandidateScore) for item in self.candidates
        ):
            raise ValueError("개인 예시 보정에는 비어 있지 않은 후보 순위가 필요합니다.")
        labels = tuple(item.label for item in self.candidates)
        if len(labels) != len(set(labels)) or self.correct_label not in labels:
            raise ValueError("개인 예시 보정 정답은 중복 없는 후보 중 하나여야 합니다.")
        if not isinstance(self.similarities, tuple) or not all(
            isinstance(item, CandidateScore) for item in self.similarities
        ):
            raise ValueError("개인 예시 보정 유사도는 후보 점수 튜플이어야 합니다.")
        similarity_labels = tuple(item.label for item in self.similarities)
        if len(similarity_labels) != len(set(similarity_labels)) or any(
            item.label not in labels or not -1.0 <= item.raw_score <= 1.0
            for item in self.similarities
        ):
            raise ValueError("개인 예시 보정 유사도는 공급된 후보와 -1부터 1 사이여야 합니다.")
        if (
            isinstance(self.contribution_scale, bool)
            or not isinstance(self.contribution_scale, (int, float))
            or not math.isfinite(self.contribution_scale)
            or self.contribution_scale <= 0
        ):
            raise ValueError("개인 예시 보정 기여 배율은 양의 유한한 숫자여야 합니다.")


@dataclass(frozen=True, slots=True)
class PersonalAxisCalibrationReport:
    """One axis's calibrated influence and held-out routing measurements."""

    policy: AxisPersonalExamplePolicy
    held_out_cases: int
    accepted: int
    accepted_correct: int
    escalated: int
    escalated_correct: int
    reviewed: int
    top_correct: int
    corrections: int
    regressions: int
    targets: CalibrationTargets

    @property
    def local_precision(self) -> float:
        """Return precision among authoritative local decisions."""
        return self.accepted_correct / self.accepted if self.accepted else 0.0

    @property
    def gemma_accuracy(self) -> float:
        """Return top-label accuracy among Gemma-routed decisions."""
        return self.escalated_correct / self.escalated if self.escalated else 0.0

    def to_dict(self) -> dict:
        """Serialize influence, counts, and target measurements."""
        return {
            "policy": self.policy.to_dict(),
            "held_out_cases": self.held_out_cases,
            "accepted": self.accepted,
            "accepted_correct": self.accepted_correct,
            "local_precision": self.local_precision,
            "escalated": self.escalated,
            "escalated_correct": self.escalated_correct,
            "gemma_accuracy": self.gemma_accuracy,
            "reviewed": self.reviewed,
            "top_correct": self.top_correct,
            "corrections": self.corrections,
            "regressions": self.regressions,
            "targets": self.targets.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PersonalExampleCalibrationReport:
    """Calibrated subject/template influence and their held-out reports."""

    policy: PersonalExamplePolicy
    subject: PersonalAxisCalibrationReport
    template: PersonalAxisCalibrationReport

    def to_dict(self) -> dict:
        """Serialize the central policy and aggregate per-axis evidence."""
        return {
            "policy": self.policy.to_dict(),
            "subject_calibration": self.subject.to_dict(),
            "template_calibration": self.template.to_dict(),
        }


def _measure_personal_policy(
    cases: tuple[PersonalCalibrationCase, ...],
    thresholds: RoutingThresholds,
    policy: AxisPersonalExamplePolicy,
    targets: CalibrationTargets,
) -> PersonalAxisCalibrationReport:
    """Measure one personal-example policy without changing routing thresholds."""
    accepted = accepted_correct = 0
    escalated = escalated_correct = 0
    reviewed = top_correct = corrections = regressions = 0
    for case in cases:
        similarities = {item.label: item.raw_score for item in case.similarities}
        adjusted = sorted(
            (
                CandidateScore(
                    item.label,
                    item.raw_score
                    + (
                        case.contribution_scale
                        * policy.weight
                        * similarities.get(item.label, 0.0)
                        if similarities.get(item.label, -1.0) >= policy.minimum_similarity
                        else 0.0
                    ),
                )
                for item in case.candidates
            ),
            key=lambda item: -item.raw_score,
        )
        top = adjusted[0]
        margin = top.raw_score - adjusted[1].raw_score if len(adjusted) > 1 else 0.0
        correct = top.label == case.correct_label
        baseline_correct = case.candidates[0].label == case.correct_label
        top_correct += int(correct)
        corrections += int(correct and not baseline_correct)
        regressions += int(not correct and baseline_correct)
        if top.raw_score >= thresholds.high_score and margin >= thresholds.high_margin:
            route = PolicyRoute.ACCEPT_LOCAL
        elif top.raw_score >= thresholds.gemma_score:
            route = PolicyRoute.GEMMA_FALLBACK
        else:
            route = PolicyRoute.NEEDS_REVIEW
        if route is PolicyRoute.ACCEPT_LOCAL:
            accepted += 1
            accepted_correct += int(correct)
        elif route is PolicyRoute.GEMMA_FALLBACK:
            escalated += 1
            escalated_correct += int(correct)
        else:
            reviewed += 1
    return PersonalAxisCalibrationReport(
        policy=policy,
        held_out_cases=len(cases),
        accepted=accepted,
        accepted_correct=accepted_correct,
        escalated=escalated,
        escalated_correct=escalated_correct,
        reviewed=reviewed,
        top_correct=top_correct,
        corrections=corrections,
        regressions=regressions,
        targets=targets,
    )


def calibrate_personal_axis(
    cases: tuple[PersonalCalibrationCase, ...],
    thresholds: RoutingThresholds,
    targets: CalibrationTargets = CalibrationTargets(),
) -> PersonalAxisCalibrationReport:
    """Select conservative influence maximizing held-out corrections under targets."""
    if not cases:
        raise ValueError("개인 예시 보정에는 비어 있지 않은 held-out 결과가 필요합니다.")
    minimum_candidates = sorted(
        {item.raw_score for case in cases for item in case.similarities},
        reverse=True,
    )
    if not minimum_candidates:
        raise ValueError("개인 예시 보정에는 nearest-example 유사도가 필요합니다.")
    weight_candidates = tuple(index / 100.0 for index in range(1, 201))
    selected: PersonalAxisCalibrationReport | None = None
    selected_key: tuple | None = None
    for minimum_similarity in minimum_candidates:
        for weight in weight_candidates:
            report = _measure_personal_policy(
                cases,
                thresholds,
                AxisPersonalExamplePolicy(weight, minimum_similarity),
                targets,
            )
            if (
                report.local_precision < targets.local_precision
                or report.gemma_accuracy < targets.gemma_accuracy
            ):
                continue
            key = (
                report.corrections - report.regressions,
                report.top_correct,
                report.accepted,
                report.escalated,
                -report.regressions,
                -weight,
                minimum_similarity,
            )
            if selected_key is None or key > selected_key:
                selected = report
                selected_key = key
    if selected is None:
        raise ValueError("승인된 정확도 목표를 만족하는 개인 예시 정책을 찾지 못했습니다.")
    return selected


def calibrate_personal_examples(
    subject_cases: tuple[PersonalCalibrationCase, ...],
    template_cases: tuple[PersonalCalibrationCase, ...],
    subject_thresholds: RoutingThresholds,
    template_thresholds: RoutingThresholds,
    targets: CalibrationTargets = CalibrationTargets(),
) -> PersonalExampleCalibrationReport:
    """Calibrate both axes independently while retaining Phase 5 route thresholds."""
    subject = calibrate_personal_axis(subject_cases, subject_thresholds, targets)
    template = calibrate_personal_axis(template_cases, template_thresholds, targets)
    policy = PersonalExamplePolicy(subject.policy, template.policy)
    return PersonalExampleCalibrationReport(policy, subject, template)
