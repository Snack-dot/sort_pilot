from __future__ import annotations

from pathlib import Path

from sort_pilot.classification import EducationalClassificationInput, Template
from sort_pilot.curriculum import Semester, StudentType, default_profile
from sort_pilot.simple_classifier import classify_for_ui_test


def _input(path: Path, fingerprint: str) -> EducationalClassificationInput:
    return EducationalClassificationInput(
        source=path,
        fingerprint=fingerprint,
        file_name=path.name,
        natural_text="",
    )


def test_simple_classifier_groups_common_extensions_without_model_inference(
    tmp_path: Path,
) -> None:
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)
    inputs = (
        _input(tmp_path / "교재.pdf", "a" * 40),
        _input(tmp_path / "사진.png", "b" * 40),
        _input(tmp_path / "자료.zip", "c" * 40),
    )

    outputs = classify_for_ui_test(inputs, student)

    assert [output.classification.subject.label for output in outputs] == list(
        student.allowed_subjects[:3]
    )
    assert [output.classification.template.label for output in outputs] == [
        Template.LEARNING_MATERIAL.value,
        Template.IN_SCHOOL.value,
        Template.ASSIGNMENT.value,
    ]
    assert all(not output.classification.needs_review for output in outputs)


def test_simple_classifier_sends_unknown_extensions_to_review(tmp_path: Path) -> None:
    student = default_profile(StudentType.HIGH, 2, Semester.SECOND)

    output = classify_for_ui_test(
        (_input(tmp_path / "unknown.bin", "d" * 40),),
        student,
    )[0]

    assert output.classification.needs_review
    assert output.classification.subject.label is None
    assert output.classification.template.label is None
