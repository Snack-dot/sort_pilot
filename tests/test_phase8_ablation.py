from __future__ import annotations

import json
from pathlib import Path

import pytest

from sort_pilot.classification import Template
from sort_pilot.classification import (
    DEFAULT_PHASE8_OPTIONAL_EVIDENCE_PATH,
    load_phase8_optional_evidence,
)
from sort_pilot.evaluation import (
    Phase8GateReport,
    ResourceMeasurement,
    load_phase8_corpus,
    paired_accuracy,
)


ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "eval" / "synthetic_phase8_ablation_corpus.json"
HELD_OUT_CORPUS = ROOT / "eval" / "synthetic_phase8_held_out_corpus.json"


def test_phase8_corpus_is_direct_labeled_made_up_evidence():
    cases = load_phase8_corpus(CORPUS)

    assert len(cases) == 30
    assert {case.template for case in cases} == set(Template)
    assert all(case.subject in case.student.allowed_subjects for case in cases)
    assert all(case.file_name.endswith(".png") for case in cases)
    assert not any(hasattr(case, "case_id") for case in cases)


def test_phase8_held_out_corpus_is_separate_and_covers_fixed_templates():
    development = load_phase8_corpus(CORPUS)
    held_out = load_phase8_corpus(HELD_OUT_CORPUS)

    assert len(held_out) == 30
    assert {case.template for case in held_out} == set(Template)
    assert {case.file_name for case in development}.isdisjoint(
        case.file_name for case in held_out
    )


def test_phase8_selected_evidence_is_strict_and_matches_final_ablation(
    tmp_path: Path,
):
    selected = load_phase8_optional_evidence()

    assert selected.ocr_layout is True
    assert selected.subject_kiwi_lexical_weight == 0.05
    assert selected.pmi is True
    assert selected.yolo_lvis_visual is False
    assert selected.model_session_scheduling is False

    document = json.loads(
        DEFAULT_PHASE8_OPTIONAL_EVIDENCE_PATH.read_text(encoding="utf-8")
    )
    document["unexpected"] = True
    path = tmp_path / "phase8-selection.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    load_phase8_optional_evidence.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Phase 8 선택"):
            load_phase8_optional_evidence(path)
    finally:
        load_phase8_optional_evidence.cache_clear()


@pytest.mark.parametrize("change", ["extra_top", "extra_case", "bad_subject", "bad_evidence"])
def test_phase8_corpus_loader_rejects_unexpected_or_invalid_fields(
    tmp_path: Path,
    change: str,
):
    document = json.loads(CORPUS.read_text(encoding="utf-8"))
    if change == "extra_top":
        document["unexpected"] = True
    elif change == "extra_case":
        document["cases"][0]["unexpected"] = True
    elif change == "bad_subject":
        document["cases"][0]["subject"] = "미확인"
    else:
        document["cases"][0]["pmi_collocations"] = "개념 정리"
    path = tmp_path / "phase8.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Phase 8 corpus"):
        load_phase8_corpus(path)


def test_paired_accuracy_requires_gain_and_exact_statistical_significance():
    baseline = (False,) * 10 + (True,) * 20
    candidate = (True,) * 30

    result = paired_accuracy(baseline, candidate)

    assert result.baseline_accuracy == pytest.approx(2 / 3)
    assert result.candidate_accuracy == 1.0
    assert result.gain == pytest.approx(1 / 3)
    assert result.improved == 10
    assert result.regressed == 0
    assert result.p_value == pytest.approx(0.001953125)
    assert result.passes is True


def test_paired_accuracy_rejects_small_or_non_significant_change():
    too_small = paired_accuracy((False,) + (True,) * 99, (True,) * 100)
    not_significant = paired_accuracy((False,) * 5 + (True,) * 25, (True,) * 30)

    assert too_small.gain == pytest.approx(0.01)
    assert too_small.passes is False
    assert not_significant.gain == pytest.approx(1 / 6)
    assert not_significant.p_value == pytest.approx(0.0625)
    assert not_significant.passes is False


def test_complete_gate_requires_all_accuracy_latency_and_memory_limits():
    passing_accuracy = paired_accuracy((False,) * 10 + (True,) * 20, (True,) * 30)
    report = Phase8GateReport(
        subject=passing_accuracy,
        template=passing_accuracy,
        combined_path=passing_accuracy,
        baseline_resources=ResourceMeasurement(100.0, 1800.0),
        candidate_resources=ResourceMeasurement(109.0, 2048.0),
    )

    assert report.latency_ratio == pytest.approx(1.09)
    assert report.passes is True
    assert report.to_dict()["gate"] == {
        "minimum_accuracy_gain": 0.05,
        "significance_alpha": 0.05,
        "maximum_p95_latency_ratio": 1.1,
        "maximum_peak_memory_mb": 2048.0,
    }

    assert Phase8GateReport(
        subject=passing_accuracy,
        template=passing_accuracy,
        combined_path=passing_accuracy,
        baseline_resources=ResourceMeasurement(100.0, 1800.0),
        candidate_resources=ResourceMeasurement(111.0, 1800.0),
    ).passes is False
    assert Phase8GateReport(
        subject=passing_accuracy,
        template=passing_accuracy,
        combined_path=passing_accuracy,
        baseline_resources=ResourceMeasurement(100.0, 1800.0),
        candidate_resources=ResourceMeasurement(100.0, 2048.1),
    ).passes is False
