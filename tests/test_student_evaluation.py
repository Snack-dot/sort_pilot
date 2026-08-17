from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.run_student_evaluation import main
from sort_pilot.classification import DecisionSource, Template
from sort_pilot.curriculum import Semester, StudentProfile, StudentType
from sort_pilot.evaluation import (
    CorpusCase,
    Prediction,
    evaluate_predictions,
    load_corpus,
    load_predictions,
)


ROOT = Path(__file__).parents[1]
SYNTHETIC_CORPUS = ROOT / "eval" / "synthetic_student_corpus.json"
SYNTHETIC_PREDICTIONS = ROOT / "eval" / "synthetic_student_predictions.json"


def _write_json(path: Path, value: object) -> None:
    """Write one temporary JSON evaluation document."""
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _case(subject: str, template: Template) -> CorpusCase:
    """Build one bounded synthetic corpus case for metric tests."""
    return CorpusCase(
        student=StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST),
        file_name="만든 예시.pdf",
        text="시험용으로 만든 내용",
        subject=subject,
        template=template,
    )


def _prediction(
    subject: str | None,
    template: str | None,
    *,
    subject_source: DecisionSource = DecisionSource.LOCAL,
    template_source: DecisionSource = DecisionSource.LOCAL,
    subject_corrected: bool = False,
    template_corrected: bool = False,
) -> Prediction:
    """Build one ordered prediction for metric tests."""
    return Prediction(
        subject=subject,
        template=template,
        subject_source=subject_source,
        template_source=template_source,
        subject_corrected=subject_corrected,
        template_corrected=template_corrected,
        latency_ms=10.0,
        memory_mb=80.0,
    )


def test_tracked_corpus_is_simple_synthetic_and_catalog_bounded():
    raw = json.loads(SYNTHETIC_CORPUS.read_text(encoding="utf-8"))
    assert set(raw) == {"cases"}
    assert len(raw["cases"]) == 10
    expected_fields = {
        "file_name",
        "text",
        "student_type",
        "grade",
        "semester",
        "subject",
        "template",
    }
    assert all(set(case) == expected_fields for case in raw["cases"])
    assert all("/" not in case["file_name"] and "\\" not in case["file_name"] for case in raw["cases"])

    cases = load_corpus(SYNTHETIC_CORPUS)
    assert {case.template for case in cases} == set(Template)
    assert all(case.subject in case.student.allowed_subjects for case in cases)


@pytest.mark.parametrize("change", ["extra", "missing", "invalid_subject"])
def test_corpus_loader_rejects_unexpected_missing_and_invalid_fields(
    tmp_path: Path, change: str
):
    case = json.loads(SYNTHETIC_CORPUS.read_text(encoding="utf-8"))["cases"][0]
    if change == "extra":
        case["local_path"] = "C:/private/example.pdf"
    elif change == "missing":
        del case["semester"]
    else:
        case["subject"] = "과목미확인"
    path = tmp_path / "corpus.json"
    _write_json(path, {"cases": [case]})

    with pytest.raises(RuntimeError):
        load_corpus(path)


@pytest.mark.parametrize("change", ["extra", "missing", "invalid_template"])
def test_prediction_loader_rejects_unexpected_missing_and_invalid_fields(
    tmp_path: Path, change: str
):
    prediction = json.loads(SYNTHETIC_PREDICTIONS.read_text(encoding="utf-8"))["predictions"][0]
    if change == "extra":
        prediction["unexpected"] = "not allowed"
    elif change == "missing":
        del prediction["memory_mb"]
    else:
        prediction["template"] = "미확인"
    path = tmp_path / "predictions.json"
    _write_json(path, {"predictions": [prediction]})

    with pytest.raises(RuntimeError):
        load_predictions(path)


def test_unresolved_axes_are_incorrect_for_all_accuracy_measures():
    corpus = (
        _case("수학", Template.ASSIGNMENT),
        _case("과학", Template.LEARNING_MATERIAL),
    )
    predictions = (
        _prediction(
            "수학",
            None,
            template_source=DecisionSource.REVIEW,
            template_corrected=True,
        ),
        _prediction(
            None,
            "학습자료",
            subject_source=DecisionSource.REVIEW,
            subject_corrected=True,
        ),
    )

    report = evaluate_predictions(corpus, predictions).to_dict()
    assert report["subject_accuracy"] == 0.5
    assert report["template_accuracy"] == 0.5
    assert report["combined_path_accuracy"] == 0.0
    assert report["coverage"] == 0.0
    assert report["review_rate"] == 1.0
    assert report["corrections"] == 2


def test_evaluation_rejects_count_mismatch_and_out_of_catalog_prediction():
    corpus = (_case("수학", Template.ASSIGNMENT),)
    with pytest.raises(ValueError, match="항목 수"):
        evaluate_predictions(corpus, ())
    with pytest.raises(ValueError, match="카탈로그"):
        evaluate_predictions(
            corpus,
            (_prediction("통합과학", "과제"),),
        )


def test_tracked_predictions_produce_all_required_phase_2_measures():
    report = evaluate_predictions(
        load_corpus(SYNTHETIC_CORPUS),
        load_predictions(SYNTHETIC_PREDICTIONS),
    ).to_dict()

    assert report == {
        "cases": 10,
        "subject_accuracy": 0.7,
        "template_accuracy": 0.6,
        "combined_path_accuracy": 0.5,
        "coverage": 0.8,
        "review_rate": 0.2,
        "fallback_rate": 0.3,
        "corrections": 5,
        "latency_ms": {"mean": 23.0, "p50": 19.5, "p95": 38.85},
        "memory_mb": {"mean": 97.6, "maximum": 104.0},
    }


def test_runner_prints_aggregate_measures_without_case_labels(capsys):
    assert main([str(SYNTHETIC_CORPUS), str(SYNTHETIC_PREDICTIONS)]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["combined_path_accuracy"] == 0.5
    assert "일차함수 연습 과제.pdf" not in output
    assert "수학" not in output


def test_real_label_evaluation_directory_is_git_ignored():
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/eval/local/" in ignore_rules
