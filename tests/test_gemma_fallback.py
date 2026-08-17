from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sort_pilot.classification import (
    AxisDecision,
    AxisRoutingDecision,
    BoundedExtractedEvidence,
    CandidateScore,
    ClassificationAxis,
    ConstrainedGemmaFallback,
    DecisionSource,
    EvidenceContribution,
    GemmaFallbackCache,
    GemmaFallbackCancelled,
    GemmaFallbackRequest,
    NEEDS_REVIEW_OUTPUT,
    PolicyRoute,
    Template,
)
from sort_pilot.curriculum import Semester, StudentType, default_profile


def _local_decision(labels: tuple[str, ...]) -> AxisDecision:
    scores = tuple(
        CandidateScore(label, 0.80 - index * 0.10)
        for index, label in enumerate(labels)
    )
    return AxisDecision(
        label=labels[0],
        raw_score=scores[0].raw_score,
        calibrated_confidence=None,
        margin=scores[0].raw_score - scores[1].raw_score,
        candidates=scores,
        evidence=(EvidenceContribution("local_rank", 0.8, "made-up evidence"),),
        source=DecisionSource.LOCAL,
        model_version="local-model-v1",
        profile_version="profiles-v1",
        policy_version="ranking-v1",
        needs_review=False,
    )


def _request(
    axis: ClassificationAxis = ClassificationAxis.SUBJECT,
    *,
    file_name: str = "수학과_물리_비교.txt",
    text: str = "함수와 힘을 함께 비교하는 만든 문서",
    route: PolicyRoute = PolicyRoute.GEMMA_FALLBACK,
    labels: tuple[str, ...] | None = None,
) -> GemmaFallbackRequest:
    if labels is None:
        labels = (
            tuple(template.value for template in Template)
            if axis is ClassificationAxis.TEMPLATE
            else ("수학", "과학")
        )
    local = _local_decision(labels)
    return GemmaFallbackRequest(
        axis=axis,
        student=default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
        routing=AxisRoutingDecision(route, local, "calibrated-v1", "made-up ambiguity"),
        evidence=BoundedExtractedEvidence(
            file_name=file_name,
            natural_text=text,
            structured=(EvidenceContribution("lexical", 0.4, "함수, 힘"),),
        ),
    )


def _fallback(tmp_path: Path, *, ready: bool = True) -> ConstrainedGemmaFallback:
    installer = SimpleNamespace(
        ready=ready,
        server_path=Path("llama-server.exe"),
        model_path=Path("gemma.gguf"),
    )
    return ConstrainedGemmaFallback(
        installer,
        GemmaFallbackCache(tmp_path / "gemma-fallback-cache.json"),
    )


def _prepare_fake_server(fallback: ConstrainedGemmaFallback) -> Mock:
    process = Mock()
    process.poll.return_value = 0
    fallback._free_port = lambda: 12345
    fallback._start_process = Mock(return_value=process)
    fallback._wait_until_ready = Mock(return_value=None)
    return process


def test_only_policy_routed_ambiguity_can_reach_gemma():
    with pytest.raises(ValueError, match="모호한 축"):
        _request(route=PolicyRoute.ACCEPT_LOCAL)
    with pytest.raises(ValueError, match="모호한 축"):
        _request(route=PolicyRoute.NEEDS_REVIEW)


def test_template_request_requires_exactly_the_five_fixed_templates():
    request = _request(ClassificationAxis.TEMPLATE)

    assert request.supplied_candidates == tuple(template.value for template in Template)
    with pytest.raises(ValueError, match="고정된 다섯 템플릿"):
        _request(ClassificationAxis.TEMPLATE, labels=("학습자료", "과제"))


def test_request_rejects_path_candidates_and_evidence_paths():
    with pytest.raises(ValueError, match="경로가 아닌"):
        _request(labels=("수학/과제", "물리학"))
    with pytest.raises(ValueError, match="파일 경로"):
        BoundedExtractedEvidence(file_name="C:\\private\\수학.txt")


def test_subject_request_rejects_candidates_outside_selected_student_catalog():
    with pytest.raises(ValueError, match="과목 카탈로그"):
        _request(labels=("수학", "물리학"))


def test_extracted_evidence_is_bounded_before_prompting():
    evidence = BoundedExtractedEvidence(
        file_name="가" * 300,
        natural_text="나" * 5_000,
        structured=tuple(
            EvidenceContribution(f"근거-{index}" + "다" * 100, 0.1, "라" * 300)
            for index in range(20)
        ),
    )

    assert len(evidence.file_name) == 240
    assert len(evidence.natural_text) == 4_000
    assert len(evidence.structured) == 16
    assert all(len(item.name) <= 80 for item in evidence.structured)
    assert all(len(item.detail) <= 240 for item in evidence.structured)


def test_prompt_contains_only_supplied_per_axis_candidates_and_bounded_evidence():
    subject = _request()
    template = _request(ClassificationAxis.TEMPLATE)

    payload = ConstrainedGemmaFallback._request_payload((subject, template))
    prompt = json.loads(payload["messages"][0]["content"].split("\n", 1)[1])
    subject_item, template_item = prompt["items"]

    assert subject_item["axis"] == "subject"
    assert [item["label"] for item in subject_item["ranked_candidates"]] == [
        "수학",
        "과학",
    ]
    assert template_item["axis"] == "template"
    assert [item["label"] for item in template_item["ranked_candidates"]] == [
        template.value for template in Template
    ]
    output_contract = payload["response_format"]["json_schema"]["schema"]
    assert output_contract["properties"]["0"]["enum"] == [
        "수학",
        "과학",
        NEEDS_REVIEW_OUTPUT,
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "document_type" not in serialized
    assert '"folder"' not in serialized
    assert '"path"' not in serialized


def test_response_accepts_only_exact_supplied_candidates_or_needs_review():
    request = _request()

    assert ConstrainedGemmaFallback._parse_batch_response(
        '```json\n{"0":"과학"}\n```',
        (request,),
    ) == {0: "과학"}
    assert ConstrainedGemmaFallback._parse_batch_response(
        '{"0":"Needs Review"}',
        (request,),
    ) == {0: NEEDS_REVIEW_OUTPUT}
    assert ConstrainedGemmaFallback._parse_batch_response(
        '{"0":"화학"}',
        (request,),
    ) == {}
    assert ConstrainedGemmaFallback._parse_batch_response(
        '{"0":"수학/과제"}',
        (request,),
    ) == {}
    with pytest.raises(ValueError, match="요청하지 않은"):
        ConstrainedGemmaFallback._parse_batch_response(
            '{"0":"수학","extra":"과학"}',
            (request,),
        )


def test_unavailable_gemma_returns_needs_review_without_caching(tmp_path: Path):
    fallback = _fallback(tmp_path, ready=False)
    progress = []

    result = fallback.resolve_many(
        (_request(),),
        lambda done, total: progress.append((done, total)),
    )

    assert result[0].label is None
    assert result[0].needs_review
    assert result[0].source is DecisionSource.REVIEW
    assert fallback.cache.load() == {}
    assert progress == [(1, 1)]


def test_batch_retries_only_unresolved_axis_requests(tmp_path: Path):
    fallback = _fallback(tmp_path)
    _prepare_fake_server(fallback)
    responses = iter(
        [
            {"choices": [{"message": {"content": '{"0":"수학"}'}}]},
            {"choices": [{"message": {"content": '{"0":"과학"}'}}]},
        ]
    )
    fallback._post_json = Mock(side_effect=responses)
    progress = []
    first = _request(file_name="첫째.txt")
    second = _request(
        file_name="둘째.txt",
        labels=("과학", "사회"),
    )

    results = fallback.resolve_many(
        (first, second),
        lambda done, total: progress.append((done, total)),
    )

    assert [result.label for result in results] == ["수학", "과학"]
    assert all(result.source is DecisionSource.GEMMA for result in results)
    assert fallback._post_json.call_count == 2
    retry_prompt = fallback._post_json.call_args_list[1].args[1]["messages"][0]["content"]
    assert "둘째.txt" in retry_prompt
    assert "첫째.txt" not in retry_prompt
    assert progress == [(1, 2), (2, 2)]


def test_invalid_outputs_exhaust_retries_then_remain_needs_review(tmp_path: Path):
    fallback = _fallback(tmp_path)
    _prepare_fake_server(fallback)
    fallback._post_json = Mock(
        return_value={"choices": [{"message": {"content": '{"0":"새 과목"}'}}]}
    )

    result = fallback.resolve_many((_request(),))[0]

    assert fallback._post_json.call_count == 3
    assert result.label is None
    assert result.source is DecisionSource.REVIEW
    assert fallback.cache.load() == {}


def test_each_valid_result_is_cached_immediately_without_raw_evidence(tmp_path: Path):
    fallback = _fallback(tmp_path)
    _prepare_fake_server(fallback)
    fallback._post_json = Mock(
        side_effect=[
            {"choices": [{"message": {"content": '{"0":"수학"}'}}]},
            RuntimeError("made-up interruption"),
            RuntimeError("made-up interruption"),
        ]
    )
    first = _request(file_name="민감하지않은_만든자료.txt")
    second = _request(file_name="둘째.txt", labels=("과학", "사회"))

    results = fallback.resolve_many((first, second))
    cache_text = fallback.cache.path.read_text(encoding="utf-8")

    assert results[0].label == "수학"
    assert results[1].needs_review
    assert "민감하지않은_만든자료" not in cache_text
    assert "함수와 힘" not in cache_text
    assert set(json.loads(cache_text)) == {"version", "entries"}

    cached_only = _fallback(tmp_path, ready=False).resolve_many((first,))[0]
    assert cached_only.label == "수학"
    assert cached_only.source is DecisionSource.CACHE


def test_valid_needs_review_output_is_cached_as_review_state(tmp_path: Path):
    fallback = _fallback(tmp_path)
    _prepare_fake_server(fallback)
    fallback._post_json = Mock(
        return_value={
            "choices": [{"message": {"content": '{"0":"Needs Review"}'}}]
        }
    )
    request = _request()

    first = fallback.resolve_many((request,))[0]
    second = _fallback(tmp_path, ready=False).resolve_many((request,))[0]

    assert first.needs_review and second.needs_review
    assert first.source is DecisionSource.REVIEW
    assert second.source is DecisionSource.REVIEW
    assert fallback._post_json.call_count == 1


def test_cache_key_changes_with_model_visible_evidence_and_policy():
    first = _request(text="첫 번째 만든 근거")
    changed_evidence = _request(text="두 번째 만든 근거")
    local = _local_decision(("수학", "과학"))
    changed_policy = GemmaFallbackRequest(
        ClassificationAxis.SUBJECT,
        default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
        AxisRoutingDecision(
            PolicyRoute.GEMMA_FALLBACK,
            local,
            "calibrated-v2",
            "made-up ambiguity",
        ),
        first.evidence,
    )

    assert ConstrainedGemmaFallback.cache_key(first) != ConstrainedGemmaFallback.cache_key(
        changed_evidence
    )
    assert ConstrainedGemmaFallback.cache_key(first) != ConstrainedGemmaFallback.cache_key(
        changed_policy
    )


def test_cancellation_stops_before_start_and_terminates_active_process(tmp_path: Path):
    fallback = _fallback(tmp_path)
    fallback._start_process = Mock()

    with pytest.raises(GemmaFallbackCancelled, match="취소"):
        fallback.resolve_many((_request(),), cancelled=lambda: True)
    fallback._start_process.assert_not_called()

    process = Mock()
    process.poll.return_value = None
    fallback._active_process = process
    fallback.cancel()
    process.terminate.assert_called_once_with()
