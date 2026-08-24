from __future__ import annotations

import os

from .classification import (
    AxisDecision,
    CandidateScore,
    DecisionSource,
    E5_VECTOR_SIZE,
    EducationalClassificationInput,
    EducationalClassificationOutput,
    EducationalClassificationResult,
    EvidenceContribution,
    Template,
)
from .curriculum import StudentProfile


SIMPLE_CLASSIFIER_ENV = "SORT_PILOT_SIMPLE_CLASSIFIER"
SIMPLE_CLASSIFIER_VERSION = "ui-test-simple-v1"

DOCUMENT_EXTENSIONS = frozenset(
    {".pdf", ".txt", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".hwp"}
)
IMAGE_EXTENSIONS = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"})
ARCHIVE_EXTENSIONS = frozenset({".7z", ".egg", ".gz", ".rar", ".tar", ".zip"})


def simple_classifier_enabled() -> bool:
    """Return whether the explicit UI-only classifier switch is enabled."""
    return os.getenv(SIMPLE_CLASSIFIER_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _simple_axis_decision(
    labels: tuple[str, ...],
    selected: str | None,
    axis_name: str,
    suffix: str,
) -> AxisDecision:
    """Build one deterministic fixed-choice decision without model inference."""
    ordered = (
        labels
        if selected is None
        else (selected, *(label for label in labels if label != selected))
    )
    candidates = tuple(
        CandidateScore(label, 1.0 - index * 0.01)
        for index, label in enumerate(ordered)
    )
    needs_review = selected is None
    margin = (
        candidates[0].raw_score - candidates[1].raw_score
        if len(candidates) > 1
        else 1.0
    )
    return AxisDecision(
        label=selected,
        raw_score=candidates[0].raw_score,
        calibrated_confidence=None,
        margin=margin,
        candidates=candidates,
        evidence=(
            EvidenceContribution(
                "ui_test_rule",
                1.0 if selected is not None else 0.0,
                f"{axis_name} extension rule: {suffix or '(none)'}",
            ),
        ),
        source=DecisionSource.REVIEW if needs_review else DecisionSource.LOCAL,
        model_version=SIMPLE_CLASSIFIER_VERSION,
        profile_version=SIMPLE_CLASSIFIER_VERSION,
        policy_version=SIMPLE_CLASSIFIER_VERSION,
        needs_review=needs_review,
    )


def classify_for_ui_test(
    inputs: tuple[EducationalClassificationInput, ...],
    student: StudentProfile,
) -> tuple[EducationalClassificationOutput, ...]:
    """Return fast extension-based results for UI testing without moving files."""
    subjects = student.allowed_subjects
    templates = tuple(template.value for template in Template)
    outputs: list[EducationalClassificationOutput] = []
    for item in inputs:
        suffix = item.source.suffix.casefold()
        if suffix in DOCUMENT_EXTENSIONS:
            subject = subjects[0]
            template = Template.LEARNING_MATERIAL.value
        elif suffix in IMAGE_EXTENSIONS:
            subject = subjects[min(1, len(subjects) - 1)]
            template = Template.IN_SCHOOL.value
        elif suffix in ARCHIVE_EXTENSIONS:
            subject = subjects[min(2, len(subjects) - 1)]
            template = Template.ASSIGNMENT.value
        else:
            subject = None
            template = None
        classification = EducationalClassificationResult(
            student=student,
            subject=_simple_axis_decision(subjects, subject, "subject", suffix),
            template=_simple_axis_decision(templates, template, "template", suffix),
        )
        outputs.append(
            EducationalClassificationOutput(
                source=item.source,
                fingerprint=item.fingerprint,
                classification=classification,
                embedding=(1.0, *(0.0 for _ in range(E5_VECTOR_SIZE - 1))),
                lexical_evidence=item.lexical_evidence,
            )
        )
    return tuple(outputs)
