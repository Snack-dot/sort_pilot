from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sort_pilot.classification import (
    DEFAULT_TEMPLATE_PROFILES_PATH,
    E5_MODEL_ID,
    E5_VECTOR_SIZE,
    CandidateScore,
    Template,
    TemplateClassifier,
    TemplateEvidence,
    TemplateEvidenceWeights,
    TemplateProfile,
    load_template_profiles,
    ordered_template_profiles,
)


class DeterministicTemplateEncoder:
    """Map made-up template intent to stable orthogonal E5-sized vectors."""

    model_id = E5_MODEL_ID
    vector_size = E5_VECTOR_SIZE

    def __init__(self) -> None:
        """Start without recorded embedding batches."""
        self.batches: list[tuple[str, ...]] = []

    def encode(self, texts) -> np.ndarray:
        """Return one unit vector for each recognizable template intent."""
        batch = tuple(texts)
        self.batches.append(batch)
        rows: list[np.ndarray] = []
        for text in batch:
            row = np.zeros(E5_VECTOR_SIZE, dtype=np.float32)
            if any(value in text for value in ("증명하는 서류", "기관이 발급", "수료증")):
                row[4] = 1.0
            elif any(value in text for value in ("학교 밖", "외부 기관", "교외")):
                row[3] = 1.0
            elif any(value in text for value in ("학교가 주관", "교내 행사", "교내")):
                row[2] = 1.0
            elif any(value in text for value in ("문제를 풀거나", "결과물을 제출", "수행평가")):
                row[1] = 1.0
            else:
                row[0] = 1.0
            rows.append(row)
        return np.asarray(rows, dtype=np.float32)


class EqualTemplateEncoder:
    """Return equal semantic intent so structured evidence decides the ranking."""

    model_id = E5_MODEL_ID
    vector_size = E5_VECTOR_SIZE

    def encode(self, texts) -> np.ndarray:
        """Return identical valid vectors for every natural-language input."""
        rows = np.zeros((len(texts), E5_VECTOR_SIZE), dtype=np.float32)
        rows[:, 0] = 1.0
        return rows


def test_template_profiles_cover_exactly_five_fixed_templates_with_separate_weights():
    profiles = load_template_profiles()

    assert tuple(profile.template for profile in profiles) == tuple(Template)
    assert all(profile.version == "1" for profile in profiles)
    assert all(profile.prototype_texts for profile in profiles)
    assert all(profile.evidence_weights.total == 7.0 for profile in profiles)
    assert len({id(profile.evidence_weights) for profile in profiles}) == 5


@pytest.mark.parametrize(
    "change",
    ["extra_top_level", "missing_template", "extra_profile_field", "invalid_weight"],
)
def test_template_profile_loader_rejects_unexpected_or_invalid_documents(
    tmp_path: Path,
    change: str,
):
    data = json.loads(DEFAULT_TEMPLATE_PROFILES_PATH.read_text(encoding="utf-8"))
    if change == "extra_top_level":
        data["unexpected"] = True
    elif change == "missing_template":
        del data["templates"][Template.EVIDENCE.value]
    elif change == "extra_profile_field":
        data["templates"][Template.ASSIGNMENT.value]["unexpected"] = True
    else:
        data["templates"][Template.ASSIGNMENT.value]["evidence_weights"]["lexical"] = -1
    path = tmp_path / "template-profiles.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    load_template_profiles.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="템플릿 프로필"):
            load_template_profiles(path)
    finally:
        load_template_profiles.cache_clear()


def test_template_evidence_embeds_natural_text_without_structured_evidence():
    evidence = TemplateEvidence(
        "수학_수행평가.pdf",
        "문제를 풀어 제출하세요.",
        lexical_terms=("structured:lexical",),
        pmi_collocations=("structured:pmi",),
        ocr_layout_terms=("structured:layout",),
        visual_terms=("structured:visual",),
        personal_example_scores=(CandidateScore(Template.ASSIGNMENT.value, 0.8),),
    )

    assert evidence.embedding_text == "수학 수행평가\n문제를 풀어 제출하세요."
    assert "structured" not in evidence.embedding_text


def test_template_classifier_ranks_exactly_five_and_retains_weighted_evidence():
    encoder = DeterministicTemplateEncoder()
    classifier = TemplateClassifier(encoder)

    decision = classifier.classify(
        TemplateEvidence(
            "수학_수행평가.pdf",
            "문제를 풀고 풀이를 작성하여 제출하세요.",
            lexical_terms=("제출",),
            pmi_collocations=("과제 제출",),
            ocr_layout_terms=("답안란",),
            visual_terms=("워크시트",),
            personal_example_scores=(CandidateScore(Template.ASSIGNMENT.value, 0.8),),
        ),
        load_template_profiles(),
    )

    assert decision.label == Template.ASSIGNMENT.value
    assert len(decision.candidates) == 5
    assert {candidate.label for candidate in decision.candidates} == {
        template.value for template in Template
    }
    assert decision.raw_score == pytest.approx(6.8 / 7.0)
    assert decision.margin > 0
    assert decision.calibrated_confidence is None
    assert decision.model_version == E5_MODEL_ID
    assert decision.profile_version == "1"
    assert decision.policy_version == "phase-4-ranking"
    assert tuple(value.name for value in decision.evidence) == (
        "semantic_intent",
        "file_name",
        "lexical",
        "pmi_collocation",
        "ocr_layout",
        "visual",
        "personal_example",
    )
    assert all(text.startswith("passage: ") for text in encoder.batches[0])
    assert encoder.batches[1][0].startswith("query: ")
    assert "structured" not in encoder.batches[1][0]


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (TemplateEvidence("과제.pdf", "일반 안내"), Template.ASSIGNMENT),
        (
            TemplateEvidence("안내.pdf", "일반 안내", lexical_terms=("봉사",)),
            Template.OUT_OF_SCHOOL,
        ),
        (
            TemplateEvidence("안내.pdf", "일반 안내", pmi_collocations=("교내 활동",)),
            Template.IN_SCHOOL,
        ),
        (
            TemplateEvidence("문서.pdf", "일반 안내", ocr_layout_terms=("직인",)),
            Template.EVIDENCE,
        ),
        (
            TemplateEvidence("문서.pdf", "일반 안내", visual_terms=("교과서",)),
            Template.LEARNING_MATERIAL,
        ),
        (
            TemplateEvidence(
                "문서.pdf",
                "일반 안내",
                personal_example_scores=(
                    CandidateScore(Template.OUT_OF_SCHOOL.value, 1.0),
                ),
            ),
            Template.OUT_OF_SCHOOL,
        ),
    ],
)
def test_each_structured_evidence_source_remains_separate_and_weighted(
    evidence: TemplateEvidence,
    expected: Template,
):
    decision = TemplateClassifier(EqualTemplateEncoder()).classify(
        evidence,
        load_template_profiles(),
    )

    assert decision.label == expected.value


def test_template_classifier_reuses_profile_embeddings():
    encoder = DeterministicTemplateEncoder()
    classifier = TemplateClassifier(encoder)
    profiles = load_template_profiles()

    classifier.classify(TemplateEvidence("과제.pdf", "수행평가"), profiles)
    classifier.classify(TemplateEvidence("수료증.pdf", "기관이 발급"), profiles)

    assert len(encoder.batches) == 3


def test_template_profiles_must_be_exactly_the_fixed_five_with_one_version():
    profiles = load_template_profiles()

    with pytest.raises(ValueError, match="정확히 일치"):
        ordered_template_profiles(profiles[:-1])

    changed = TemplateProfile(
        template=profiles[-1].template,
        prototype_texts=profiles[-1].prototype_texts,
        file_name_indicators=profiles[-1].file_name_indicators,
        lexical_indicators=profiles[-1].lexical_indicators,
        pmi_collocations=profiles[-1].pmi_collocations,
        ocr_layout_indicators=profiles[-1].ocr_layout_indicators,
        visual_indicators=profiles[-1].visual_indicators,
        evidence_weights=profiles[-1].evidence_weights,
        version="2",
    )
    with pytest.raises(ValueError, match="하나의 프로필 버전"):
        TemplateClassifier(EqualTemplateEncoder()).classify(
            TemplateEvidence("문서.pdf", "일반 안내"),
            (*profiles[:-1], changed),
        )


def test_template_classifier_rejects_wrong_encoder_and_personal_example_scores():
    class WrongSizeEncoder:
        """Expose an invalid vector size for constructor validation."""

        model_id = E5_MODEL_ID
        vector_size = 10

    with pytest.raises(ValueError, match="384"):
        TemplateClassifier(WrongSizeEncoder())
    with pytest.raises(ValueError, match="중복"):
        TemplateEvidence(
            "문서.pdf",
            "본문",
            personal_example_scores=(
                CandidateScore(Template.ASSIGNMENT.value, 0.8),
                CandidateScore(Template.ASSIGNMENT.value, 0.7),
            ),
        )
    with pytest.raises(ValueError, match="고정 템플릿"):
        TemplateEvidence(
            "문서.pdf",
            "본문",
            personal_example_scores=(CandidateScore("미확인", 0.5),),
        )


def test_template_evidence_weights_are_finite_nonnegative_and_not_all_zero():
    with pytest.raises(ValueError, match="0 이상의"):
        TemplateEvidenceWeights(1, 1, -1, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="양수"):
        TemplateEvidenceWeights(0, 0, 0, 0, 0, 0, 0)
