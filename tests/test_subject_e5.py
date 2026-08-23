from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from sort_pilot.classification import (
    DEFAULT_SUBJECT_PROFILES_PATH,
    E5_MODEL_ID,
    E5_VECTOR_SIZE,
    E5SubjectClassifier,
    FastEmbedE5Encoder,
    SubjectEvidence,
    SubjectProfile,
    load_subject_profiles,
)
from sort_pilot.curriculum import Semester, StudentProfile, StudentType, load_subject_catalog


class DeterministicEncoder:
    """Small deterministic 384-dimensional encoder for subject-ranking tests."""

    model_id = E5_MODEL_ID
    vector_size = E5_VECTOR_SIZE

    def __init__(self) -> None:
        """Start with no recorded batches."""
        self.batches: list[tuple[str, ...]] = []

    def encode(self, texts) -> np.ndarray:
        """Map selected natural-language concepts to orthogonal unit directions."""
        batch = tuple(texts)
        self.batches.append(batch)
        rows: list[np.ndarray] = []
        for text in batch:
            row = np.zeros(E5_VECTOR_SIZE, dtype=np.float32)
            if any(term in text for term in ("수와 연산", "방정식", "함수")):
                row[0] = 1.0
            elif any(term in text for term in ("영어 듣기", "영문 독해")):
                row[1] = 1.0
            elif "통합과학" in text:
                row[2] = 1.0
            else:
                row[3] = 1.0
            rows.append(row)
        return np.asarray(rows, dtype=np.float32)


def test_natural_language_profiles_cover_exact_catalog_subjects():
    profiles = load_subject_profiles()
    catalog = load_subject_catalog()
    expected = tuple(dict.fromkeys((*catalog.middle_subjects, *catalog.high_subjects)))

    assert tuple(profile.label for profile in profiles) == expected
    assert all(profile.version == "3" for profile in profiles)
    assert all(profile.prototype_texts for profile in profiles)
    assert all(profile.keywords for profile in profiles)
    assert all(profile.label in profile.keywords for profile in profiles)


@pytest.mark.parametrize(
    "change", ["extra", "missing_subject", "invalid_texts", "invalid_aliases"]
)
def test_subject_profile_loader_rejects_non_catalog_documents(tmp_path: Path, change: str):
    data = json.loads(DEFAULT_SUBJECT_PROFILES_PATH.read_text(encoding="utf-8"))
    if change == "extra":
        data["unexpected"] = True
    elif change == "missing_subject":
        del data["subjects"]["수학"]
    elif change == "invalid_texts":
        data["subjects"]["수학"] = "수학 설명"
    else:
        data["subjects"]["수학"]["filename_aliases"] = "수학"
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    load_subject_profiles.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            load_subject_profiles(path)
    finally:
        load_subject_profiles.cache_clear()


def test_subject_profile_loader_rejects_duplicate_filename_aliases(tmp_path: Path):
    data = json.loads(DEFAULT_SUBJECT_PROFILES_PATH.read_text(encoding="utf-8"))
    data["subjects"]["사회"]["filename_aliases"].append("수학")
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    load_subject_profiles.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            load_subject_profiles(path)
    finally:
        load_subject_profiles.cache_clear()


def test_subject_evidence_embeds_natural_text_but_not_structured_lexical_terms():
    evidence = SubjectEvidence(
        "일차함수_연습.pdf",
        "기울기와 절편을 구하는 문제",
        ("structured:lexical",),
    )

    assert evidence.embedding_text == "일차함수 연습\n기울기와 절편을 구하는 문제"
    assert "structured:lexical" not in evidence.embedding_text


def test_e5_subject_classifier_ranks_only_selected_catalog_subjects_and_keeps_scores():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산, 방정식과 함수를 학습한다.",), version="1"),
        SubjectProfile("통합과학", ("통합과학의 여러 영역을 학습한다.",), version="1"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)

    decision = classifier.classify(
        SubjectEvidence("방정식 문제.pdf", "함수의 값을 구한다."),
        student,
        profiles,
    )

    assert decision.label == "수학"
    assert tuple(candidate.label for candidate in decision.candidates) == ("수학", "영어")
    assert "통합과학" not in {candidate.label for candidate in decision.candidates}
    assert decision.raw_score == pytest.approx(1.0)
    assert decision.margin == pytest.approx(1.0)
    assert decision.calibrated_confidence is None
    assert decision.model_version == E5_MODEL_ID
    assert decision.profile_version == "1"
    assert decision.evidence[0].name == "e5_similarity"
    assert all(text.startswith("passage: ") for text in encoder.batches[0])
    assert encoder.batches[1][0].startswith("query: ")


def test_e5_subject_classifier_reuses_profile_embeddings():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)

    classifier.classify(SubjectEvidence("함수.pdf", "함수 문제"), student, profiles)
    classifier.classify(SubjectEvidence("방정식.pdf", "방정식 문제"), student, profiles)

    assert len(encoder.batches) == 3


def test_subject_kiwi_lexical_evidence_stays_structured_and_inspectable():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산, 방정식과 함수를 학습한다.",), version="1"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)
    equal_embedding = np.zeros(E5_VECTOR_SIZE, dtype=np.float32)
    equal_embedding[3] = 1.0

    decision = classifier.classify(
        SubjectEvidence("연습.pdf", "일반 내용", ("방정식", "함수")),
        student,
        profiles,
        query_embedding=equal_embedding,
        lexical_weight=0.05,
    )

    assert decision.label == "수학"
    assert decision.raw_score == pytest.approx(0.05)
    assert decision.evidence[-1].name == "kiwi_lexical"
    assert decision.evidence[-1].value == pytest.approx(0.05)
    assert len(encoder.batches) == 1
    assert all(text.startswith("passage: ") for text in encoder.batches[0])


def test_subject_filename_alias_prefers_longest_specific_match():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("사회", ("사회 현상을 배운다.",), keywords=("사회",), version="2"),
        SubjectProfile("통합사회", ("통합사회 현상을 배운다.",), keywords=("통합사회",), version="2"),
    )
    student = StudentProfile(StudentType.HIGH, 1, Semester.FIRST)

    decision = classifier.classify(
        SubjectEvidence("통합사회_문제.pdf", ""),
        student,
        profiles,
        filename_weight=0.15,
    )

    assert decision.label == "통합사회"
    assert decision.evidence[2].name == "filename_alias"
    assert decision.evidence[2].value == pytest.approx(0.15)


def test_subject_filename_alias_matches_unicode_decomposed_filenames():
    """macOS/APFS reports Korean filenames pre-decomposed (NFD); matching must not break."""
    decomposed_name = unicodedata.normalize("NFD", "통합사회_문제.pdf")
    assert decomposed_name != "통합사회_문제.pdf"

    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("사회", ("사회 현상을 배운다.",), keywords=("사회",), version="2"),
        SubjectProfile("통합사회", ("통합사회 현상을 배운다.",), keywords=("통합사회",), version="2"),
    )
    student = StudentProfile(StudentType.HIGH, 1, Semester.FIRST)

    decision = classifier.classify(
        SubjectEvidence(decomposed_name, ""),
        student,
        profiles,
        filename_weight=0.15,
    )

    assert decision.label == "통합사회"
    assert decision.evidence[2].value == pytest.approx(0.15)


def test_subject_filename_alias_score_is_zero_with_no_match():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), keywords=("영어",), version="2"),
        SubjectProfile("수학", ("수와 연산, 방정식과 함수를 학습한다.",), keywords=("수학",), version="2"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)

    decision = classifier.classify(
        SubjectEvidence("방정식 문제.pdf", "함수의 값을 구한다."),
        student,
        profiles,
        filename_weight=0.15,
    )

    assert decision.label == "수학"
    assert decision.evidence[2].name == "filename_alias"
    assert decision.evidence[2].value == pytest.approx(0.0)


@pytest.mark.parametrize("value", [-0.1, float("nan"), True])
def test_subject_classifier_rejects_invalid_filename_weight(value):
    classifier = E5SubjectClassifier(DeterministicEncoder())
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )

    with pytest.raises(ValueError, match="파일명 별칭"):
        classifier.classify(
            SubjectEvidence("자료.pdf", "일반 내용"),
            StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST),
            profiles,
            filename_weight=value,
        )


def test_subject_pmi_collocation_evidence_stays_structured_and_inspectable():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile(
            "사회", ("사회 현상을 배운다.",), pmi_collocations=("수요 공급",), version="3"
        ),
        SubjectProfile(
            "도덕", ("도덕적 가치를 배운다.",), pmi_collocations=("윤리적 판단",), version="3"
        ),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)
    equal_embedding = np.zeros(E5_VECTOR_SIZE, dtype=np.float32)
    equal_embedding[3] = 1.0

    decision = classifier.classify(
        SubjectEvidence(
            "자료.pdf", "일반 내용", pmi_collocations=("수요 공급 균형",)
        ),
        student,
        profiles,
        query_embedding=equal_embedding,
        pmi_weight=0.1,
    )

    assert decision.label == "사회"
    assert decision.evidence[3].name == "pmi_collocation"
    assert decision.evidence[3].value == pytest.approx(0.1)


def test_subject_pmi_collocation_score_is_zero_with_no_match():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), keywords=("영어",), version="3"),
        SubjectProfile("수학", ("수와 연산, 방정식과 함수를 학습한다.",), keywords=("수학",), version="3"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)

    decision = classifier.classify(
        SubjectEvidence("방정식 문제.pdf", "함수의 값을 구한다.", pmi_collocations=("전혀 관련없음",)),
        student,
        profiles,
        pmi_weight=0.1,
    )

    assert decision.label == "수학"
    assert decision.evidence[3].value == pytest.approx(0.0)


@pytest.mark.parametrize("value", [-0.1, float("nan"), True])
def test_subject_classifier_rejects_invalid_pmi_weight(value):
    classifier = E5SubjectClassifier(DeterministicEncoder())
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )

    with pytest.raises(ValueError, match="PMI 연어"):
        classifier.classify(
            SubjectEvidence("자료.pdf", "일반 내용"),
            StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST),
            profiles,
            pmi_weight=value,
        )


def test_subject_language_signal_boosts_english_for_predominantly_latin_text():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    # Neither prototype text contains a DeterministicEncoder trigger substring, so both
    # map to the same orthogonal row -- E5 similarity is a true tie, isolating language_weight.
    profiles = (
        SubjectProfile("영어", ("영어 과목을 학습한다.",), version="1"),
        SubjectProfile("정보", ("정보 과목에서 알고리즘을 학습한다.",), version="1"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)
    equal_embedding = np.zeros(E5_VECTOR_SIZE, dtype=np.float32)
    equal_embedding[3] = 1.0
    english_text = (
        "Dear Principal Jones, I hope this letter finds you well. "
        "I am writing to express my concern about the school cafeteria menu today."
    )

    decision = classifier.classify(
        SubjectEvidence("자료.pdf", english_text),
        student,
        profiles,
        query_embedding=equal_embedding,
        language_weight=0.12,
    )

    assert decision.label == "영어"
    assert decision.evidence[4].name == "language_signal"
    assert decision.evidence[4].value == pytest.approx(0.12)


def test_subject_language_signal_is_zero_for_korean_text_or_short_text():
    encoder = DeterministicEncoder()
    classifier = E5SubjectClassifier(encoder)
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )
    student = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST)

    korean_decision = classifier.classify(
        SubjectEvidence("방정식 문제.pdf", "함수의 값을 구하고 그래프를 그려서 풀이 과정을 자세히 설명하시오."),
        student,
        profiles,
        language_weight=0.12,
    )
    short_english_decision = classifier.classify(
        SubjectEvidence("문제.pdf", "Dear Sir"),
        student,
        profiles,
        language_weight=0.12,
    )

    assert korean_decision.evidence[4].value == pytest.approx(0.0)
    assert short_english_decision.evidence[4].value == pytest.approx(0.0)


@pytest.mark.parametrize("value", [-0.1, float("nan"), True])
def test_subject_classifier_rejects_invalid_language_weight(value):
    classifier = E5SubjectClassifier(DeterministicEncoder())
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )

    with pytest.raises(ValueError, match="언어 신호"):
        classifier.classify(
            SubjectEvidence("자료.pdf", "일반 내용"),
            StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST),
            profiles,
            language_weight=value,
        )


@pytest.mark.parametrize("value", [-0.1, float("nan"), True])
def test_subject_classifier_rejects_invalid_kiwi_lexical_weight(value):
    classifier = E5SubjectClassifier(DeterministicEncoder())
    profiles = (
        SubjectProfile("영어", ("영어 듣기와 영문 독해를 학습한다.",), version="1"),
        SubjectProfile("수학", ("수와 연산과 함수를 학습한다.",), version="1"),
    )

    with pytest.raises(ValueError, match="Kiwi 어휘"):
        classifier.classify(
            SubjectEvidence("자료.pdf", "일반 내용"),
            StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST),
            profiles,
            lexical_weight=value,
        )


def test_e5_subject_classifier_rejects_wrong_vector_size():
    class WrongSizeEncoder:
        model_id = E5_MODEL_ID
        vector_size = 10

    with pytest.raises(ValueError, match="384"):
        E5SubjectClassifier(WrongSizeEncoder())


def test_fastembed_adapter_forces_cpu_and_defaults_to_local_cache(monkeypatch):
    calls: dict[str, object] = {}

    class FakeTextEmbedding:
        """Record FastEmbed configuration without loading a model."""

        @classmethod
        def list_supported_models(cls):
            """Pretend E5-small still needs explicit registration."""
            return []

        @classmethod
        def add_custom_model(cls, **kwargs):
            """Record the exact custom model description."""
            calls["registration"] = kwargs

        def __init__(self, **kwargs):
            """Record constructor arguments."""
            calls["constructor"] = kwargs

        def embed(self, texts, batch_size):
            """Return finite nonzero 384-dimensional rows."""
            calls["batch_size"] = batch_size
            return [np.ones(E5_VECTOR_SIZE, dtype=np.float32) for _ in texts]

    class FakeModelSource:
        """Stand in for FastEmbed's model-source description."""

        def __init__(self, *, hf):
            """Retain the requested Hugging Face model identifier."""
            self.hf = hf

    class FakePoolingType:
        """Expose the mean-pooling value used by the adapter."""

        MEAN = "mean"

    fastembed_module = ModuleType("fastembed")
    fastembed_module.TextEmbedding = FakeTextEmbedding
    common_module = ModuleType("fastembed.common")
    description_module = ModuleType("fastembed.common.model_description")
    description_module.ModelSource = FakeModelSource
    description_module.PoolingType = FakePoolingType
    monkeypatch.setitem(sys.modules, "fastembed", fastembed_module)
    monkeypatch.setitem(sys.modules, "fastembed.common", common_module)
    monkeypatch.setitem(
        sys.modules,
        "fastembed.common.model_description",
        description_module,
    )
    encoder = FastEmbedE5Encoder(batch_size=4)
    matrix = encoder.encode(("query: 수학 문제",))

    registration = calls["registration"]
    constructor = calls["constructor"]
    assert registration["model"] == E5_MODEL_ID
    assert registration["dim"] == E5_VECTOR_SIZE
    assert registration["model_file"] == "onnx/model.onnx"
    assert constructor["providers"] == ["CPUExecutionProvider"]
    assert constructor["cuda"] is False
    assert constructor["local_files_only"] is True
    assert calls["batch_size"] == 4
    assert matrix.shape == (1, E5_VECTOR_SIZE)
