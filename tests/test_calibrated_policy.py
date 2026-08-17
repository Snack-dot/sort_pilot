from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import run_policy_calibration
from sort_pilot.classification import (
    CALIBRATED_POLICY_VERSION,
    DEFAULT_CALIBRATED_POLICY_PATH,
    GEMMA_ACCURACY_TARGET,
    LOCAL_PRECISION_TARGET,
    CalibratedPolicy,
    CalibrationTargets,
    HeldOutAxisResult,
    RoutingThresholds,
    calibrate_axis,
    calibrate_policy,
    load_calibrated_policy,
)
from sort_pilot.evaluation import load_corpus


ROOT = Path(__file__).parents[1]
HELD_OUT_CORPUS = ROOT / "eval" / "synthetic_student_held_out_corpus.json"
PHASE_2_CORPUS = ROOT / "eval" / "synthetic_student_corpus.json"


def _results(offset: float = 0.0) -> tuple[HeldOutAxisResult, ...]:
    """Build made-up held-out scores with clear local, escalation, and review regions."""
    return tuple(
        HeldOutAxisResult(score + offset, margin, correct)
        for score, margin, correct in (
            (0.95, 0.20, True),
            (0.93, 0.15, True),
            (0.91, 0.12, True),
            (0.89, 0.10, True),
            (0.87, 0.08, False),
            (0.75, 0.05, True),
            (0.65, 0.04, False),
            (0.55, 0.02, True),
            (0.40, 0.01, False),
            (0.20, 0.00, False),
        )
    )


def test_user_approved_phase_5_targets_are_exact():
    targets = CalibrationTargets()

    assert LOCAL_PRECISION_TARGET == 0.90
    assert GEMMA_ACCURACY_TARGET == 0.50
    assert targets.to_dict() == {
        "local_precision": 0.90,
        "gemma_accuracy": 0.50,
    }


def test_tracked_held_out_corpus_is_new_made_up_data_covering_both_axes():
    held_out_raw = json.loads(HELD_OUT_CORPUS.read_text(encoding="utf-8"))
    phase_2_raw = json.loads(PHASE_2_CORPUS.read_text(encoding="utf-8"))
    expected_fields = {
        "file_name",
        "text",
        "student_type",
        "grade",
        "semester",
        "subject",
        "template",
    }

    assert set(held_out_raw) == {"cases"}
    assert len(held_out_raw["cases"]) == 50
    assert all(set(case) == expected_fields for case in held_out_raw["cases"])
    assert not {
        (case["file_name"], case["text"]) for case in held_out_raw["cases"]
    } & {
        (case["file_name"], case["text"]) for case in phase_2_raw["cases"]
    }
    corpus = load_corpus(HELD_OUT_CORPUS)
    assert len({case.subject for case in corpus}) == 18
    assert len({case.template for case in corpus}) == 5


def test_axis_calibration_meets_both_targets_and_retains_review_region():
    report = calibrate_axis(_results(), CalibrationTargets())

    assert report.accepted == 4
    assert report.local_precision == 1.0
    assert report.escalated == 4
    assert report.gemma_accuracy == 0.5
    assert report.reviewed == 2
    assert report.thresholds.gemma_score == pytest.approx(0.55)
    assert report.to_dict()["held_out_cases"] == 10


def test_explicit_abstention_is_always_counted_as_review():
    results = (*_results(), HeldOutAxisResult(1.0, 1.0, False, abstained=True))

    report = calibrate_axis(results, CalibrationTargets())

    assert report.held_out_cases == 11
    assert report.reviewed == 3


def test_subject_and_template_thresholds_are_calibrated_independently():
    report = calibrate_policy(_results(), _results(-0.30))

    assert report.policy.subject != report.policy.template
    assert report.policy.subject == report.subject.thresholds
    assert report.policy.template == report.template.thresholds
    assert report.policy.thresholds_for("subject") == report.subject.thresholds
    assert report.policy.thresholds_for("template") == report.template.thresholds
    with pytest.raises(ValueError, match="subject 또는 template"):
        report.policy.thresholds_for("document")


def test_calibration_rejects_invalid_targets_results_and_unreachable_goals():
    with pytest.raises(ValueError, match="0보다 크고"):
        CalibrationTargets(0.0, 0.5)
    with pytest.raises(ValueError, match="원점수"):
        HeldOutAxisResult(float("nan"), 0.1, True)
    with pytest.raises(ValueError, match="기권"):
        HeldOutAxisResult(0.9, 0.1, True, abstained=True)
    with pytest.raises(ValueError, match="비어 있지 않은"):
        calibrate_axis((), CalibrationTargets())
    with pytest.raises(ValueError, match="임계값을 찾지 못했습니다"):
        calibrate_axis(
            (
                HeldOutAxisResult(0.9, 0.1, True),
                HeldOutAxisResult(0.8, 0.1, False),
            ),
            CalibrationTargets(1.0, 1.0),
        )


def test_calibrated_policy_loader_rejects_additional_fields_and_changed_targets(
    tmp_path: Path,
):
    policy = {
        "version": CALIBRATED_POLICY_VERSION,
        "targets": {"local_precision": 0.90, "gemma_accuracy": 0.50},
        "subject": {"high_score": 0.9, "high_margin": 0.1, "gemma_score": 0.5},
        "template": {"high_score": 0.2, "high_margin": 0.01, "gemma_score": 0.1},
    }
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(policy), encoding="utf-8")
    load_calibrated_policy.cache_clear()
    try:
        loaded = load_calibrated_policy(valid)
        assert isinstance(loaded, CalibratedPolicy)
        assert loaded.to_dict() == policy

        policy["unexpected"] = True
        invalid = tmp_path / "invalid.json"
        invalid.write_text(json.dumps(policy), encoding="utf-8")
        with pytest.raises(RuntimeError, match="보정 정책"):
            load_calibrated_policy(invalid)

        del policy["unexpected"]
        policy["targets"]["local_precision"] = 0.97
        changed = tmp_path / "changed.json"
        changed.write_text(json.dumps(policy), encoding="utf-8")
        with pytest.raises(RuntimeError, match="보정 정책"):
            load_calibrated_policy(changed)
    finally:
        load_calibrated_policy.cache_clear()


def test_packaged_calibrated_policy_uses_exact_targets_and_separate_axes():
    policy = load_calibrated_policy(DEFAULT_CALIBRATED_POLICY_PATH)

    assert policy.targets == CalibrationTargets()
    assert policy.version == CALIBRATED_POLICY_VERSION
    assert policy.subject != policy.template
    assert policy.subject.gemma_score <= policy.subject.high_score
    assert policy.template.gemma_score <= policy.template.high_score


def test_policy_serialization_contains_thresholds_not_held_out_contents():
    report = calibrate_policy(_results(), _results(-0.30))
    serialized = report.policy.to_dict()

    assert set(serialized) == {"version", "targets", "subject", "template"}
    assert set(serialized["subject"]) == {
        "high_score",
        "high_margin",
        "gemma_score",
    }
    assert "held_out_cases" not in serialized


def test_calibration_runner_prints_aggregate_policy_and_writes_nothing(
    monkeypatch,
    capsys,
    tmp_path: Path,
):
    report = calibrate_policy(_results(), _results(-0.30))
    before = set(tmp_path.iterdir())
    monkeypatch.setattr(run_policy_calibration, "load_corpus", lambda path: (object(),))
    monkeypatch.setattr(
        run_policy_calibration,
        "derive_policy",
        lambda corpus, model_cache: report,
    )

    assert run_policy_calibration.main([str(tmp_path / "made-up.json")]) == 0

    output = json.loads(capsys.readouterr().out)
    assert set(output) == {"policy", "subject_calibration", "template_calibration"}
    assert set(tmp_path.iterdir()) == before
