from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sort_pilot.classification import (
    AxisDecision,
    AxisRoutingDecision,
    CandidateScore,
    DecisionSource,
    EducationalClassificationResult,
    EvidenceContribution,
    OrganizationPlan,
    PolicyRoute,
    RoutingThresholds,
    SubjectEvidence,
    SubjectProfile,
    Template,
    eligible_subject_profiles,
    route_axis,
)
from sort_pilot.curriculum import (
    OCCUPATION,
    SUBJECT_CATALOG_VERSION,
    Semester,
    StudentProfile,
    StudentProfileStore,
    StudentType,
    default_profile,
    load_subject_catalog,
)


def decision(label: str, source: DecisionSource = DecisionSource.LOCAL) -> AxisDecision:
    return AxisDecision(
        label=label,
        raw_score=0.91,
        calibrated_confidence=0.88,
        margin=0.32,
        candidates=(CandidateScore(label, 0.91),),
        evidence=(EvidenceContribution("filename", 0.25, label),),
        source=source,
        model_version="model-v1",
        profile_version="profile-v1",
        policy_version="policy-v1",
    )


def abstention() -> AxisDecision:
    return AxisDecision(
        label=None,
        raw_score=0.0,
        calibrated_confidence=None,
        margin=0.0,
        candidates=(),
        evidence=(),
        source=DecisionSource.REVIEW,
        model_version="model-v1",
        profile_version="profile-v1",
        policy_version="policy-v1",
        needs_review=True,
    )


def result(
    subject: AxisDecision | None = None,
    template: AxisDecision | None = None,
) -> EducationalClassificationResult:
    return EducationalClassificationResult(
        student=default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
        subject=subject or decision("수학"),
        template=template or decision(Template.ASSIGNMENT.value),
    )


def test_catalog_has_one_fixed_version_and_only_student_types() -> None:
    catalog = load_subject_catalog()

    assert catalog.version == SUBJECT_CATALOG_VERSION == "KR_STUDENT_2026_MVP_V1"
    assert catalog.occupation == OCCUPATION == "학생"
    assert tuple(student_type.value for student_type in StudentType) == ("중학생", "고등학생")
    assert tuple(semester.value for semester in Semester) == ("1학기", "2학기")
    assert "수학" in catalog.subjects_for(StudentType.MIDDLE)
    assert "한국사" in catalog.subjects_for(StudentType.HIGH)


def test_catalog_prohibits_artificial_fallback_subjects() -> None:
    subjects = {
        subject
        for student_type in StudentType
        for subject in load_subject_catalog().subjects_for(student_type)
    }

    assert subjects.isdisjoint({"기타", "미확인", "분류미확인", "공통", "비교과", "과목미확인"})


def test_catalog_rejects_unexpected_fields(tmp_path: Path) -> None:
    path = tmp_path / "subjects.json"
    data = json.loads(
        Path("sort_pilot/curriculum/data/subjects_2026.json").read_text(encoding="utf-8")
    )
    data["school_timetable"] = []
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="과목 카탈로그"):
        load_subject_catalog(path)


def test_default_profile_loads_candidates_from_catalog() -> None:
    profile = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)

    assert profile.allowed_subjects == load_subject_catalog().subjects_for(StudentType.MIDDLE)
    assert profile.to_dict() == {
        "occupation": "학생",
        "student_type": "중학생",
        "grade": 1,
        "semester": "1학기",
        "catalog_version": "KR_STUDENT_2026_MVP_V1",
    }


def test_student_profile_rejects_stale_catalog_and_non_student_scope() -> None:
    with pytest.raises(ValueError, match="카탈로그 버전"):
        StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST, catalog_version="legacy-v0")
    with pytest.raises(ValueError, match="학생뿐"):
        StudentProfile(StudentType.HIGH, 2, Semester.SECOND, occupation="교사")


@pytest.mark.parametrize("grade", [0, 4, True, 1.0])
def test_student_profile_accepts_only_integer_grades_one_through_three(grade: object) -> None:
    with pytest.raises(ValueError, match="학년"):
        StudentProfile(StudentType.MIDDLE, grade, Semester.FIRST)


def test_institution_labels_and_non_semester_fallbacks_are_not_enum_values() -> None:
    with pytest.raises(ValueError):
        StudentType("중학교")
    with pytest.raises(ValueError):
        StudentType("고등학교")
    with pytest.raises(ValueError):
        Semester("공통")
    with pytest.raises(ValueError):
        Semester("미확인")


def test_template_enum_contains_exactly_five_fixed_templates() -> None:
    assert tuple(template.value for template in Template) == (
        "학습자료",
        "과제",
        "교내활동",
        "교외활동",
        "증빙서류",
    )


def test_result_renders_exact_six_directory_hierarchy_for_each_template() -> None:
    for template in Template:
        classification = result(template=decision(template.value))

        assert classification.folder.split("/") == [
            "학생",
            "중학생",
            "1학년",
            "1학기",
            "수학",
            template.value,
        ]


def test_result_contains_exactly_subject_and_template_classification_axes() -> None:
    serialized = result().to_dict()

    assert set(serialized) == {"student", "subject", "template", "folder", "needs_review"}
    assert not hasattr(result(), "document_type")


def test_axis_serialization_retains_complete_required_representation() -> None:
    serialized = decision("수학").to_dict()

    assert serialized == {
        "label": "수학",
        "raw_score": 0.91,
        "calibrated_confidence": 0.88,
        "margin": 0.32,
        "candidates": [{"label": "수학", "raw_score": 0.91}],
        "evidence": [{"name": "filename", "value": 0.25, "detail": "수학"}],
        "source": "local_classifier",
        "model_version": "model-v1",
        "profile_version": "profile-v1",
        "policy_version": "policy-v1",
        "needs_review": False,
    }


def test_axis_rejects_invalid_scores_candidate_order_and_versions() -> None:
    with pytest.raises(ValueError, match="원점수"):
        CandidateScore("수학", math.inf)
    with pytest.raises(ValueError, match="보정 신뢰도"):
        AxisDecision(
            "수학", 0.9, 1.1, 0.2, (), (), DecisionSource.LOCAL, "m", "p", "v"
        )
    with pytest.raises(ValueError, match="내림차순"):
        AxisDecision(
            "수학",
            0.9,
            None,
            0.2,
            (CandidateScore("국어", 0.4), CandidateScore("수학", 0.8)),
            (),
            DecisionSource.LOCAL,
            "m",
            "p",
            "v",
        )
    with pytest.raises(ValueError, match="model_version"):
        AxisDecision("수학", 0.9, None, 0.2, (), (), DecisionSource.LOCAL, "", "p", "v")


def test_result_rejects_subject_label_and_candidates_outside_catalog() -> None:
    with pytest.raises(ValueError, match="과목 결정"):
        result(subject=decision("경제"))
    invalid_candidate = AxisDecision(
        "수학",
        0.9,
        None,
        0.2,
        (CandidateScore("경제", 0.9),),
        (),
        DecisionSource.LOCAL,
        "m",
        "p",
        "v",
    )
    with pytest.raises(ValueError, match="과목 후보"):
        result(subject=invalid_candidate)


def test_result_rejects_template_label_and_candidates_outside_fixed_five() -> None:
    with pytest.raises(ValueError, match="템플릿 분류"):
        result(template=decision("분류미확인"))
    invalid_candidate = AxisDecision(
        Template.ASSIGNMENT.value,
        0.9,
        None,
        0.2,
        (CandidateScore("분류미확인", 0.9),),
        (),
        DecisionSource.LOCAL,
        "m",
        "p",
        "v",
    )
    with pytest.raises(ValueError, match="템플릿 후보"):
        result(template=invalid_candidate)


@pytest.mark.parametrize("unresolved_axis", ["subject", "template"])
def test_unresolved_axis_cannot_render_folder_or_produce_organization_plan(
    unresolved_axis: str,
    tmp_path: Path,
) -> None:
    classification = result(
        subject=abstention() if unresolved_axis == "subject" else None,
        template=abstention() if unresolved_axis == "template" else None,
    )

    with pytest.raises(ValueError, match="모두 확정"):
        _ = classification.folder
    with pytest.raises(ValueError, match="모두 확정"):
        OrganizationPlan.from_classification(Path("과제.pdf"), tmp_path, classification)
    assert classification.to_dict()[unresolved_axis]["label"] is None
    assert classification.to_dict()["folder"] is None
    assert classification.needs_review is True


def test_resolved_result_produces_exact_filename_preserving_organization_plan(
    tmp_path: Path,
) -> None:
    source = tmp_path / "함수숙제.pdf"
    destination_root = tmp_path / "organized"
    plan = OrganizationPlan.from_classification(source, destination_root, result())

    assert plan.source == source
    assert plan.destination == (
        destination_root / "학생" / "중학생" / "1학년" / "1학기" / "수학" / "과제" / source.name
    )


def test_review_source_and_nullable_label_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="needs_review"):
        AxisDecision(None, 0.0, None, 0.0, (), (), DecisionSource.REVIEW, "m", "p", "v")
    with pytest.raises(ValueError, match="needs_review"):
        AxisDecision("수학", 0.0, None, 0.0, (), (), DecisionSource.LOCAL, "m", "p", "v", True)
    with pytest.raises(ValueError, match="검토 출처"):
        AxisDecision(None, 0.0, None, 0.0, (), (), DecisionSource.LOCAL, "m", "p", "v", True)


def test_student_profile_round_trips_atomically(tmp_path: Path) -> None:
    store = StudentProfileStore(tmp_path / "student.json")
    assert store.load() is None
    profile = StudentProfile(StudentType.HIGH, 2, Semester.SECOND)

    store.save(profile)

    assert store.load() == profile
    assert not list(tmp_path.glob("student-profile-*.tmp"))


def test_student_profile_rejects_unexpected_fields() -> None:
    data = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST).to_dict()
    data["school_name"] = "unexpected"

    with pytest.raises(ValueError, match="학생 프로필"):
        StudentProfile.from_dict(data)


def test_student_store_rejects_unexpected_document_fields(tmp_path: Path) -> None:
    path = tmp_path / "student.json"
    profile = StudentProfile(StudentType.MIDDLE, 1, Semester.FIRST).to_dict()
    path.write_text(
        json.dumps({"version": 1, "profile": profile, "extra": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="학생 프로필"):
        StudentProfileStore(path).load()


def test_student_store_reports_corruption_and_stale_catalog(tmp_path: Path) -> None:
    path = tmp_path / "student.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="학생 프로필"):
        StudentProfileStore(path).load()

    profile = StudentProfile(StudentType.MIDDLE, 3, Semester.FIRST).to_dict()
    profile["catalog_version"] = "legacy-v0"
    path.write_text(
        json.dumps({"version": 1, "profile": profile}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="학생 프로필"):
        StudentProfileStore(path).load()


def test_subject_profiles_are_bounded_and_ordered_by_catalog() -> None:
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)
    profiles = (
        SubjectProfile("영어", ("영어 독해와 문법",), ("영문법",)),
        SubjectProfile("수학", ("수와 연산, 함수, 기하",), ("함수",)),
        SubjectProfile("국어", ("국어 문학과 문법",), ("문학",)),
        SubjectProfile("경제", ("경제 원리와 시장",), ("시장",)),
    )

    eligible = eligible_subject_profiles(student, profiles)

    assert [profile.label for profile in eligible] == ["국어", "수학", "영어"]
    assert SubjectEvidence("함수문제.pdf", "일차함수 문제", ("함수",)).lexical_terms == ("함수",)


def test_policy_routes_each_axis_by_raw_score_and_margin() -> None:
    thresholds = RoutingThresholds(high_score=0.8, high_margin=0.2, gemma_score=0.45)
    high = decision("수학")
    narrow_margin = AxisDecision(
        "수학", 0.91, None, 0.01, (), (), DecisionSource.LOCAL, "m", "p", "v"
    )
    low = AxisDecision("수학", 0.2, None, 0.1, (), (), DecisionSource.LOCAL, "m", "p", "v")

    accepted = route_axis(high, thresholds, "hybrid-v1")
    fallback = route_axis(narrow_margin, thresholds, "hybrid-v1")
    review = route_axis(low, thresholds, "hybrid-v1")

    assert isinstance(accepted, AxisRoutingDecision)
    assert accepted.route is PolicyRoute.ACCEPT_LOCAL
    assert fallback.route is PolicyRoute.GEMMA_FALLBACK
    assert review.route is PolicyRoute.NEEDS_REVIEW


def test_explicit_local_abstention_never_reaches_gemma() -> None:
    thresholds = RoutingThresholds(high_score=0.8, high_margin=0.2, gemma_score=0.45)

    assert route_axis(abstention(), thresholds, "hybrid-v1").route is PolicyRoute.NEEDS_REVIEW


def test_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="순서"):
        RoutingThresholds(high_score=0.4, high_margin=0.2, gemma_score=0.5)
