from __future__ import annotations

import pytest

from sort_pilot.classification import (
    Activity,
    AxisRoutingDecision,
    AxisDecision,
    CandidateScore,
    DecisionSource,
    EducationalClassificationResult,
    PolicyRoute,
    RoutingThresholds,
    SubjectEvidence,
    SubjectProfile,
    eligible_subject_profiles,
    route_axis,
)
from sort_pilot.curriculum import (
    CurriculumProfile,
    CurriculumProfileStore,
    SchoolLevel,
    Semester,
    default_profile,
)


def decision(label: str, source: DecisionSource = DecisionSource.LOCAL) -> AxisDecision:
    return AxisDecision(
        label=label,
        score=0.91,
        margin=0.32,
        source=source,
        candidates=(CandidateScore(label, 0.91),),
        evidence=("filename:수학",),
    )


def test_default_profile_adds_explicit_non_subject_fallbacks() -> None:
    profile = default_profile(SchoolLevel.MIDDLE, 1, Semester.FIRST)

    assert "수학" in profile.allowed_subjects
    assert profile.subject_candidates[-3:] == ("비교과", "공통", "과목미확인")
    assert profile.to_dict()["curriculum_version"] == "SORT_PILOT_KR_SECONDARY_V1"


def test_result_renders_requested_student_hierarchy() -> None:
    profile = default_profile(SchoolLevel.MIDDLE, 1, Semester.FIRST)
    result = EducationalClassificationResult(
        curriculum=profile,
        subject=decision("수학"),
        activity=decision(Activity.ASSIGNMENT.value),
    )

    assert result.folder == "학생/중학생/1학년/1학기/수학/과제"
    assert result.to_dict()["subject"]["source"] == "local_classifier"
    assert result.needs_review is False


def test_non_subject_activity_uses_explicit_extracurricular_axis() -> None:
    profile = default_profile(SchoolLevel.HIGH, 2, Semester.COMMON)
    result = EducationalClassificationResult(
        curriculum=profile,
        subject=decision("비교과"),
        activity=decision(Activity.OUT_OF_SCHOOL.value, DecisionSource.GEMMA),
    )

    assert result.folder == "학생/고등학생/2학년/공통/비교과/교외활동"


def test_result_rejects_subject_outside_curriculum_candidates() -> None:
    profile = CurriculumProfile(SchoolLevel.MIDDLE, 1, Semester.FIRST, ("국어", "수학"))

    with pytest.raises(ValueError, match="교육과정 후보"):
        EducationalClassificationResult(
            curriculum=profile,
            subject=decision("경제"),
            activity=decision(Activity.ACADEMIC.value),
        )


def test_review_source_must_be_marked_for_review() -> None:
    with pytest.raises(ValueError, match="needs_review"):
        decision("과목미확인", DecisionSource.REVIEW)


def test_curriculum_profile_round_trips_atomically(tmp_path) -> None:
    store = CurriculumProfileStore(tmp_path / "curriculum.json")
    assert store.load() is None
    profile = CurriculumProfile(
        SchoolLevel.HIGH,
        2,
        Semester.SECOND,
        ("국어", "수학", "경제"),
    )

    store.save(profile)
    loaded = store.load()

    assert loaded == profile
    assert loaded.subject_candidates == ("국어", "수학", "경제", "비교과", "공통", "과목미확인")
    assert not list(tmp_path.glob("curriculum-profile-*.tmp"))


def test_curriculum_store_reports_corruption_instead_of_resetting(tmp_path) -> None:
    path = tmp_path / "curriculum.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="교육과정 프로필"):
        CurriculumProfileStore(path).load()


def test_old_curriculum_version_loads_but_requires_migration(tmp_path) -> None:
    profile = CurriculumProfile(
        SchoolLevel.MIDDLE,
        3,
        Semester.COMMON,
        ("국어", "수학"),
        curriculum_version="legacy-v0",
    )
    store = CurriculumProfileStore(tmp_path / "curriculum.json")
    store.save(profile)

    assert store.load().requires_migration is True


def test_subject_profiles_are_bounded_and_ordered_by_curriculum() -> None:
    curriculum = CurriculumProfile(
        SchoolLevel.MIDDLE,
        1,
        Semester.FIRST,
        ("수학", "국어"),
    )
    profiles = (
        SubjectProfile("영어", ("영어 독해와 문법",), ("영문법",)),
        SubjectProfile("국어", ("국어 문학과 문법",), ("문학",)),
        SubjectProfile("수학", ("수와 연산, 함수, 기하",), ("함수",)),
    )

    eligible = eligible_subject_profiles(curriculum, profiles)

    assert [profile.label for profile in eligible] == ["수학", "국어"]
    assert SubjectEvidence("함수문제.pdf", "일차함수 문제", ("함수",)).lexical_terms == ("함수",)


def test_policy_routes_each_axis_by_score_and_margin() -> None:
    thresholds = RoutingThresholds(high_score=0.8, high_margin=0.2, gemma_score=0.45)
    high = decision("수학")
    narrow_margin = AxisDecision("수학", 0.91, 0.01, DecisionSource.LOCAL)
    low = AxisDecision("과목미확인", 0.2, 0.1, DecisionSource.LOCAL)

    accepted = route_axis(high, thresholds, "hybrid-v1")
    fallback = route_axis(narrow_margin, thresholds, "hybrid-v1")
    review = route_axis(low, thresholds, "hybrid-v1")

    assert isinstance(accepted, AxisRoutingDecision)
    assert accepted.route is PolicyRoute.ACCEPT_LOCAL
    assert fallback.route is PolicyRoute.GEMMA_FALLBACK
    assert review.route is PolicyRoute.NEEDS_REVIEW


def test_explicit_local_abstention_never_reaches_gemma() -> None:
    thresholds = RoutingThresholds(high_score=0.8, high_margin=0.2, gemma_score=0.45)
    abstained = AxisDecision(
        "과목미확인",
        0.9,
        0.5,
        DecisionSource.REVIEW,
        needs_review=True,
    )

    assert route_axis(abstained, thresholds, "hybrid-v1").route is PolicyRoute.NEEDS_REVIEW


def test_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="순서"):
        RoutingThresholds(high_score=0.4, high_margin=0.2, gemma_score=0.5)
