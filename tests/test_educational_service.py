from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sort_pilot.classification import (
    AxisPersonalExamplePolicy,
    CalibratedPolicy,
    CalibrationTargets,
    DecisionSource,
    E5_MODEL_ID,
    E5_VECTOR_SIZE,
    EducationalClassificationInput,
    EducationalClassificationService,
    GemmaFallbackCancelled,
    OriginalPrediction,
    PersonalExample,
    PersonalExamplePolicy,
    PersonalExampleStore,
    PersonalExampleVersions,
    RoutingThresholds,
    load_subject_profiles,
    load_template_profiles,
)
from sort_pilot.curriculum import (
    SUBJECT_CATALOG_VERSION,
    Semester,
    StudentType,
    default_profile,
)


class EqualEncoder:
    """Return one valid equal embedding for every made-up input."""

    model_id = E5_MODEL_ID
    vector_size = E5_VECTOR_SIZE

    def encode(self, texts) -> np.ndarray:
        """Return one shared unit direction per input text."""
        values = np.zeros((len(texts), E5_VECTOR_SIZE), dtype=np.float32)
        values[:, 0] = 1.0
        return values


class ForbiddenGemma:
    """Fail a test if an authoritative local or review route reaches Gemma."""

    def resolve_many(self, requests, **kwargs):
        """Reject every unexpected fallback invocation."""
        raise AssertionError(f"Gemma must not receive {len(requests)} requests")


def _policy(route: str) -> CalibratedPolicy:
    if route == "accept":
        thresholds = RoutingThresholds(high_score=-1.0, high_margin=0.0, gemma_score=-1.0)
    elif route == "review":
        thresholds = RoutingThresholds(high_score=2.0, high_margin=1.0, gemma_score=2.0)
    else:
        thresholds = RoutingThresholds(high_score=2.0, high_margin=1.0, gemma_score=-1.0)
    return CalibratedPolicy(
        thresholds,
        thresholds,
        CalibrationTargets(),
        version=f"made-up-{route}",
    )


def _personal_policy(weight: float = 0.0) -> PersonalExamplePolicy:
    axis = AxisPersonalExamplePolicy(weight, 0.5)
    return PersonalExamplePolicy(axis, axis)


def _input(tmp_path: Path) -> EducationalClassificationInput:
    return EducationalClassificationInput(
        source=tmp_path / "만든자료.txt",
        fingerprint="a" * 40,
        file_name="만든자료.txt",
        natural_text="만든 학습 내용",
        lexical_evidence=("학습", "내용"),
    )


def _service(
    tmp_path: Path,
    route: str,
    *,
    weight: float = 0.0,
) -> EducationalClassificationService:
    return EducationalClassificationService(
        encoder=EqualEncoder(),
        subject_profiles=load_subject_profiles(),
        template_profiles=load_template_profiles(),
        calibrated_policy=_policy(route),
        personal_policy=_personal_policy(weight),
        personal_examples=PersonalExampleStore(tmp_path / "personal_examples.json"),
        gemma=ForbiddenGemma(),
    )


def test_service_accepts_both_high_local_axes_without_gemma(tmp_path: Path):
    service = _service(tmp_path, "accept")
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)

    output = service.classify_many((_input(tmp_path),), student)[0]

    assert output.classification.subject.source is DecisionSource.LOCAL
    assert output.classification.template.source is DecisionSource.LOCAL
    assert not output.classification.needs_review
    assert output.classification.folder.startswith("학생/중학생/1학년/1학기/")


def test_service_turns_both_weak_axes_into_needs_review_without_gemma(tmp_path: Path):
    service = _service(tmp_path, "review")
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)

    output = service.classify_many((_input(tmp_path),), student)[0]

    assert output.classification.subject.source is DecisionSource.REVIEW
    assert output.classification.template.source is DecisionSource.REVIEW
    assert output.classification.needs_review
    with pytest.raises(ValueError, match="모두 확정"):
        _ = output.classification.folder


def test_nearest_personal_example_contributes_before_routing(tmp_path: Path):
    store = PersonalExampleStore(tmp_path / "personal_examples.json")
    store.save(
        (
            PersonalExample(
                fingerprint="b" * 40,
                embedding=(1.0, *(0.0 for _ in range(E5_VECTOR_SIZE - 1))),
                approved_subject="과학",
                approved_template="과제",
                original_prediction=OriginalPrediction("국어", "학습자료"),
                lexical_evidence=("만든",),
                versions=PersonalExampleVersions(
                    SUBJECT_CATALOG_VERSION,
                    E5_MODEL_ID,
                    "1",
                    "1",
                    "old-subject-policy",
                    "old-template-policy",
                ),
            ),
        )
    )
    service = EducationalClassificationService(
        EqualEncoder(),
        load_subject_profiles(),
        load_template_profiles(),
        _policy("accept"),
        _personal_policy(1.0),
        store,
        ForbiddenGemma(),
    )

    output = service.classify_many(
        (_input(tmp_path),),
        default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
    )[0]

    assert output.classification.subject.label == "과학"
    assert output.classification.template.label == "과제"
    assert output.classification.subject.source is DecisionSource.PERSONAL_EXAMPLE
    assert output.classification.template.source is DecisionSource.PERSONAL_EXAMPLE


def test_service_checks_cancellation_before_embedding(tmp_path: Path):
    service = _service(tmp_path, "accept")

    with pytest.raises(GemmaFallbackCancelled, match="취소"):
        service.classify_many(
            (_input(tmp_path),),
            default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
            cancelled=lambda: True,
        )
