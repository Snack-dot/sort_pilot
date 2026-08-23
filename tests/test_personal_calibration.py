from __future__ import annotations

import pytest

from sort_pilot.classification import (
    CalibrationTargets,
    CandidateScore,
    PersonalCalibrationCase,
    RoutingThresholds,
    calibrate_personal_axis,
    load_personal_example_policy,
)


def _case(
    first: str,
    correct: str,
    similarities: tuple[CandidateScore, ...],
) -> PersonalCalibrationCase:
    return PersonalCalibrationCase(
        candidates=(CandidateScore(first, 0.70), CandidateScore(correct, 0.69)),
        similarities=similarities,
        correct_label=correct,
    )


def test_packaged_personal_example_policy_has_independent_calibrated_axes() -> None:
    policy = load_personal_example_policy()

    assert policy.subject.weight == 0.01
    assert policy.subject.minimum_similarity == pytest.approx(0.8699697256088257)
    assert policy.template.weight == 1.15
    assert policy.template.minimum_similarity == pytest.approx(0.8862630128860474)


def test_calibration_selects_personal_influence_without_changing_route_thresholds() -> None:
    thresholds = RoutingThresholds(high_score=0.90, high_margin=0.05, gemma_score=0.60)
    cases = (
        _case(
            "수학",
            "과학",
            (CandidateScore("과학", 0.95), CandidateScore("수학", 0.10)),
        ),
        PersonalCalibrationCase(
            candidates=(CandidateScore("국어", 0.95), CandidateScore("과학", 0.40)),
            similarities=(CandidateScore("국어", 0.96),),
            correct_label="국어",
        ),
    )

    report = calibrate_personal_axis(
        cases,
        thresholds,
        CalibrationTargets(local_precision=0.90, gemma_accuracy=0.50),
    )

    assert report.corrections == 1
    assert report.regressions == 0
    assert report.local_precision >= 0.90
    assert report.gemma_accuracy >= 0.50
    assert thresholds == RoutingThresholds(0.90, 0.05, 0.60)


def test_calibration_rejects_cases_without_nearest_example_scores() -> None:
    case = PersonalCalibrationCase(
        candidates=(CandidateScore("수학", 0.70), CandidateScore("과학", 0.60)),
        similarities=(),
        correct_label="수학",
    )

    with pytest.raises(ValueError, match="nearest-example"):
        calibrate_personal_axis(
            (case,),
            RoutingThresholds(high_score=0.90, high_margin=0.05, gemma_score=0.60),
        )
