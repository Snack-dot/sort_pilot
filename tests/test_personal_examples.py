from __future__ import annotations

import json
from pathlib import Path

import pytest

from sort_pilot.classification.e5 import E5_MODEL_ID, E5_VECTOR_SIZE
from sort_pilot.classification.personal_examples import (
    PERSONAL_EXAMPLE_DOCUMENT_VERSION,
    PERSONAL_EXAMPLE_POLICY_VERSION,
    AxisPersonalExamplePolicy,
    OriginalPrediction,
    PersonalExample,
    PersonalExamplePolicy,
    PersonalExampleStore,
    PersonalExampleVersions,
    load_personal_example_policy,
)
from sort_pilot.curriculum import (
    SUBJECT_CATALOG_VERSION,
    Semester,
    StudentType,
    default_profile,
)


def _embedding(first: float = 1.0, second: float = 0.0) -> tuple[float, ...]:
    return (first, second, *(0.0 for _ in range(E5_VECTOR_SIZE - 2)))


def _versions() -> PersonalExampleVersions:
    return PersonalExampleVersions(
        catalog_version=SUBJECT_CATALOG_VERSION,
        embedding_model_version=E5_MODEL_ID,
        subject_profile_version="subject-v1",
        template_profile_version="template-v1",
        subject_policy_version="subject-policy-v1",
        template_policy_version="template-policy-v1",
    )


def _example(
    fingerprint: str = "a" * 40,
    *,
    subject: str = "수학",
    template: str = "과제",
    embedding: tuple[float, ...] | None = None,
) -> PersonalExample:
    return PersonalExample(
        fingerprint=fingerprint,
        embedding=embedding or _embedding(),
        approved_subject=subject,
        approved_template=template,
        original_prediction=OriginalPrediction("과학", "학습자료"),
        lexical_evidence=("함수", "문제 풀이"),
        versions=_versions(),
    )


def _policy(minimum: float = 0.8) -> PersonalExamplePolicy:
    return PersonalExamplePolicy(
        subject=AxisPersonalExamplePolicy(0.2, minimum),
        template=AxisPersonalExamplePolicy(0.4, minimum),
    )


def test_personal_example_contains_only_plan_required_local_fields():
    serialized = _example().to_dict()

    assert set(serialized) == {
        "fingerprint",
        "embedding",
        "approved_subject",
        "approved_template",
        "original_prediction",
        "lexical_evidence",
        "versions",
    }
    assert set(serialized["original_prediction"]) == {"subject", "template"}
    assert "path" not in json.dumps(serialized, ensure_ascii=False).casefold()
    assert "natural_text" not in serialized


def test_personal_example_normalizes_embedding_and_bounds_lexical_evidence():
    example = PersonalExample(
        fingerprint="b" * 64,
        embedding=_embedding(3.0, 4.0),
        approved_subject="수학",
        approved_template="과제",
        original_prediction=OriginalPrediction(None, None),
        lexical_evidence=tuple(f"근거-{index}-" + "가" * 100 for index in range(100)),
        versions=_versions(),
    )

    assert example.embedding[:2] == pytest.approx((0.6, 0.8))
    assert len(example.lexical_evidence) == 80
    assert all(len(value) <= 80 for value in example.lexical_evidence)


def test_personal_example_rejects_invalid_fingerprint_embedding_and_labels():
    with pytest.raises(ValueError, match="fingerprint"):
        _example("not-a-fingerprint")
    with pytest.raises(ValueError, match="384차원"):
        _example(embedding=(1.0, 0.0))
    with pytest.raises(ValueError, match="과목 카탈로그"):
        _example(subject="천문점성술")
    with pytest.raises(ValueError, match="다섯 템플릿"):
        _example(template="기타")


def test_store_round_trips_atomically_and_replaces_same_fingerprint(tmp_path: Path):
    path = tmp_path / "personal_examples.json"
    store = PersonalExampleStore(path)
    first = _example()
    corrected = _example(subject="과학", template="학습자료")

    assert store.load() == ()
    store.add((first,))
    assert store.load() == (first,)
    store.add((corrected,))

    assert store.load() == (corrected,)
    assert not list(tmp_path.glob("personal-examples-*.tmp"))
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == PERSONAL_EXAMPLE_DOCUMENT_VERSION
    assert len(document["examples"]) == 1


def test_store_rejects_unexpected_fields_and_duplicate_fingerprints(tmp_path: Path):
    path = tmp_path / "personal_examples.json"
    value = {
        "version": PERSONAL_EXAMPLE_DOCUMENT_VERSION,
        "examples": [_example().to_dict()],
        "unexpected": True,
    }
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="개인 예시"):
        PersonalExampleStore(path).load()
    with pytest.raises(ValueError, match="중복"):
        PersonalExampleStore(tmp_path / "new.json").save((_example(), _example()))


def test_nearest_scores_are_per_label_catalog_bounded_and_thresholded(tmp_path: Path):
    store = PersonalExampleStore(tmp_path / "personal_examples.json")
    store.save(
        (
            _example("a" * 40, subject="수학", template="과제", embedding=_embedding(1, 0)),
            _example("b" * 40, subject="과학", template="학습자료", embedding=_embedding(0.8, 0.6)),
            _example("c" * 40, subject="한국사", template="증빙서류", embedding=_embedding(1, 0)),
        )
    )
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)

    scores = store.nearest_scores(_embedding(1, 0), student, _policy(0.75))

    assert [item.label for item in scores.subject] == ["수학", "과학"]
    assert [item.raw_score for item in scores.subject] == pytest.approx([1.0, 0.8])
    assert [item.label for item in scores.template] == ["과제", "증빙서류", "학습자료"]
    assert "한국사" not in {item.label for item in scores.subject}


def test_strict_personal_example_policy_loader(tmp_path: Path):
    path = tmp_path / "policy.json"
    value = {
        "version": PERSONAL_EXAMPLE_POLICY_VERSION,
        "subject": {"weight": 0.2, "minimum_similarity": 0.8},
        "template": {"weight": 0.4, "minimum_similarity": 0.7},
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    load_personal_example_policy.cache_clear()
    try:
        assert load_personal_example_policy(path).to_dict() == value
        value["extra"] = True
        invalid = tmp_path / "invalid.json"
        invalid.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(RuntimeError, match="개인 예시 정책"):
            load_personal_example_policy(invalid)
    finally:
        load_personal_example_policy.cache_clear()
