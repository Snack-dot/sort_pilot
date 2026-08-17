from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from sort_pilot.curriculum import StudentProfile

from .calibrated_policy import CalibratedPolicy
from .e5 import E5SubjectClassifier, E5_VECTOR_SIZE, SubjectTextEncoder, _embedding_matrix
from .gemma_fallback import (
    BoundedExtractedEvidence,
    ClassificationAxis,
    ConstrainedGemmaFallback,
    GemmaFallbackCancelled,
    GemmaFallbackRequest,
)
from .personal_examples import (
    PersonalExamplePolicy,
    PersonalExampleStore,
)
from .optional_evidence import Phase8OptionalEvidence, load_phase8_optional_evidence
from .policy import AxisRoutingDecision, PolicyRoute, route_axis
from .result import (
    AxisDecision,
    DecisionSource,
    EducationalClassificationResult,
    EvidenceContribution,
)
from .subject import SubjectEvidence, SubjectProfile
from .template import TemplateClassifier, TemplateEvidence, TemplateProfile


MAX_CLASSIFICATION_TEXT_CHARACTERS = 8_000
MAX_CLASSIFICATION_EVIDENCE_ITEMS = 160
_FINGERPRINT = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True, slots=True)
class EducationalClassificationInput:
    """One extracted file's path-free evidence plus its separate source path."""

    source: Path
    fingerprint: str
    file_name: str
    natural_text: str
    template_natural_text: str | None = None
    lexical_evidence: tuple[str, ...] = ()
    pmi_collocations: tuple[str, ...] = ()
    ocr_layout_evidence: tuple[str, ...] = ()
    visual_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate source identity and bound every classification evidence channel."""
        if not isinstance(self.source, Path) or not self.source.name:
            raise ValueError("교육 분류 입력에는 원본 파일 경로가 필요합니다.")
        if self.source.name != self.file_name or "/" in self.file_name or "\\" in self.file_name:
            raise ValueError("교육 분류 입력의 파일 이름은 원본 경로와 일치해야 합니다.")
        if not isinstance(self.fingerprint, str) or not _FINGERPRINT.fullmatch(
            self.fingerprint
        ):
            raise ValueError("교육 분류 입력 fingerprint가 올바르지 않습니다.")
        if not isinstance(self.natural_text, str):
            raise ValueError("교육 분류 자연어 근거는 문자열이어야 합니다.")
        object.__setattr__(
            self,
            "natural_text",
            self.natural_text[:MAX_CLASSIFICATION_TEXT_CHARACTERS],
        )
        if self.template_natural_text is not None and not isinstance(
            self.template_natural_text,
            str,
        ):
            raise ValueError("템플릿 자연어 근거는 문자열이어야 합니다.")
        object.__setattr__(
            self,
            "template_natural_text",
            (
                self.natural_text
                if self.template_natural_text is None
                else self.template_natural_text[:MAX_CLASSIFICATION_TEXT_CHARACTERS]
            ),
        )
        for field in (
            "lexical_evidence",
            "pmi_collocations",
            "ocr_layout_evidence",
            "visual_evidence",
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or not all(isinstance(value, str) for value in values):
                raise ValueError("교육 분류의 구조화 근거는 문자열 튜플이어야 합니다.")
            object.__setattr__(
                self,
                field,
                tuple(
                    dict.fromkeys(
                        value.strip()
                        for value in values[:MAX_CLASSIFICATION_EVIDENCE_ITEMS]
                        if value.strip()
                    )
                ),
            )


@dataclass(frozen=True, slots=True)
class EducationalClassificationOutput:
    """Classification, embedding, fingerprint, and lexical evidence for preview."""

    source: Path
    fingerprint: str
    classification: EducationalClassificationResult
    embedding: tuple[float, ...]
    lexical_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require a matching source and one normalized 384-dimensional embedding."""
        if not isinstance(self.source, Path) or not isinstance(
            self.classification, EducationalClassificationResult
        ):
            raise ValueError("교육 분류 출력에는 원본 경로와 분류 결과가 필요합니다.")
        normalized = _embedding_matrix((self.embedding,), 1)[0]
        object.__setattr__(self, "embedding", tuple(float(value) for value in normalized))


def _routed_local_decision(routing: AxisRoutingDecision) -> AxisDecision:
    """Finalize a high local decision or turn weak evidence into review state."""
    local = routing.local_decision
    combined_policy = f"{routing.policy_version}+{local.policy_version}"
    if routing.route is PolicyRoute.ACCEPT_LOCAL:
        return replace(local, policy_version=combined_policy)
    if routing.route is PolicyRoute.NEEDS_REVIEW:
        return AxisDecision(
            label=None,
            raw_score=local.raw_score,
            calibrated_confidence=local.calibrated_confidence,
            margin=local.margin,
            candidates=local.candidates,
            evidence=(
                *local.evidence,
                EvidenceContribution("routing", 0.0, routing.reason),
            ),
            source=DecisionSource.REVIEW,
            model_version=local.model_version,
            profile_version=local.profile_version,
            policy_version=combined_policy,
            needs_review=True,
        )
    raise ValueError("Gemma fallback 경로는 Gemma 결과 없이 확정할 수 없습니다.")


class EducationalClassificationService:
    """Run both calibrated axes, personal examples, and constrained Gemma locally."""

    def __init__(
        self,
        encoder: SubjectTextEncoder,
        subject_profiles: tuple[SubjectProfile, ...],
        template_profiles: tuple[TemplateProfile, ...],
        calibrated_policy: CalibratedPolicy,
        personal_policy: PersonalExamplePolicy,
        personal_examples: PersonalExampleStore,
        gemma: ConstrainedGemmaFallback,
        optional_evidence: Phase8OptionalEvidence | None = None,
    ) -> None:
        """Bind exact local classifiers, policies, examples, and fallback."""
        self.encoder = encoder
        self.subject_classifier = E5SubjectClassifier(encoder)
        self.template_classifier = TemplateClassifier(encoder)
        self.subject_profiles = subject_profiles
        self.template_profiles = template_profiles
        self.calibrated_policy = calibrated_policy
        self.personal_policy = personal_policy
        self.personal_examples = personal_examples
        self.gemma = gemma
        self.optional_evidence = optional_evidence or load_phase8_optional_evidence()

    def classify_many(
        self,
        inputs: Sequence[EducationalClassificationInput],
        student: StudentProfile,
        progress: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[EducationalClassificationOutput, ...]:
        """Classify ordered inputs with independent subject/template routing."""
        ordered = tuple(inputs)
        if not ordered:
            return ()
        if not all(isinstance(item, EducationalClassificationInput) for item in ordered):
            raise ValueError("교육 분류 입력 목록이 올바르지 않습니다.")
        if not isinstance(student, StudentProfile):
            raise ValueError("교육 분류에는 저장된 학생 프로필이 필요합니다.")
        self._raise_if_cancelled(cancelled)
        subject_inputs = tuple(
            SubjectEvidence(item.file_name, item.natural_text).embedding_text
            for item in ordered
        )
        template_inputs = tuple(
            SubjectEvidence(
                item.file_name,
                item.template_natural_text or "",
            ).embedding_text
            for item in ordered
        )
        unique_inputs = tuple(dict.fromkeys((*subject_inputs, *template_inputs)))
        unique_embeddings = _embedding_matrix(
            self.encoder.encode(tuple(f"query: {value}" for value in unique_inputs)),
            len(unique_inputs),
        )
        embedding_index = {value: index for index, value in enumerate(unique_inputs)}
        subject_embeddings = np.asarray(
            [unique_embeddings[embedding_index[value]] for value in subject_inputs],
            dtype=np.float32,
        )
        template_embeddings = np.asarray(
            [unique_embeddings[embedding_index[value]] for value in template_inputs],
            dtype=np.float32,
        )
        local: list[tuple[AxisRoutingDecision, AxisRoutingDecision]] = []
        for completed, (item, subject_embedding, template_embedding) in enumerate(
            zip(ordered, subject_embeddings, template_embeddings, strict=True),
            1,
        ):
            self._raise_if_cancelled(cancelled)
            personal = self.personal_examples.nearest_scores(
                tuple(float(value) for value in subject_embedding),
                student,
                self.personal_policy,
            )
            subject_evidence = SubjectEvidence(
                item.file_name,
                item.natural_text,
                item.lexical_evidence,
                personal.subject,
            )
            template_evidence = TemplateEvidence(
                file_name=item.file_name,
                natural_text=item.template_natural_text or "",
                lexical_terms=item.lexical_evidence,
                pmi_collocations=(
                    item.pmi_collocations if self.optional_evidence.pmi else ()
                ),
                ocr_layout_terms=(
                    item.ocr_layout_evidence
                    if self.optional_evidence.ocr_layout
                    else ()
                ),
                visual_terms=(
                    item.visual_evidence
                    if self.optional_evidence.yolo_lvis_visual
                    else ()
                ),
                personal_example_scores=personal.template,
            )
            subject = self.subject_classifier.classify(
                subject_evidence,
                student,
                self.subject_profiles,
                query_embedding=subject_embedding,
                personal_example_weight=self.personal_policy.subject.weight,
                lexical_weight=self.optional_evidence.subject_kiwi_lexical_weight,
            )
            template = self.template_classifier.classify(
                template_evidence,
                self.template_profiles,
                query_embedding=template_embedding,
                personal_example_weight=self.personal_policy.template.weight,
            )
            local.append(
                (
                    route_axis(
                        subject,
                        self.calibrated_policy.subject,
                        self.calibrated_policy.version,
                    ),
                    route_axis(
                        template,
                        self.calibrated_policy.template,
                        self.calibrated_policy.version,
                    ),
                )
            )
            if progress:
                progress(completed, len(ordered))

        final: list[list[AxisDecision | None]] = [[None, None] for _ in ordered]
        fallback_requests: list[GemmaFallbackRequest] = []
        fallback_owners: list[tuple[int, int]] = []
        for index, (item, routes) in enumerate(zip(ordered, local, strict=True)):
            for axis_index, (axis, routing) in enumerate(
                zip(ClassificationAxis, routes, strict=True)
            ):
                if routing.route is PolicyRoute.GEMMA_FALLBACK:
                    fallback_requests.append(
                        GemmaFallbackRequest(
                            axis=axis,
                            student=student,
                            routing=routing,
                            evidence=BoundedExtractedEvidence(
                                file_name=item.file_name,
                                natural_text=(
                                    item.natural_text
                                    if axis_index == 0
                                    else item.template_natural_text or ""
                                ),
                                structured=routing.local_decision.evidence,
                            ),
                        )
                    )
                    fallback_owners.append((index, axis_index))
                else:
                    final[index][axis_index] = _routed_local_decision(routing)

        self._raise_if_cancelled(cancelled)
        if fallback_requests:
            fallback_decisions = self.gemma.resolve_many(
                fallback_requests,
                cancelled=cancelled,
            )
            for owner, decision in zip(fallback_owners, fallback_decisions, strict=True):
                final[owner[0]][owner[1]] = decision
        self._raise_if_cancelled(cancelled)

        outputs = []
        for item, embedding, decisions in zip(
            ordered,
            subject_embeddings,
            final,
            strict=True,
        ):
            subject, template = decisions
            if not isinstance(subject, AxisDecision) or not isinstance(template, AxisDecision):
                raise RuntimeError("교육 분류 축이 완성되지 않았습니다.")
            outputs.append(
                EducationalClassificationOutput(
                    source=item.source,
                    fingerprint=item.fingerprint,
                    classification=EducationalClassificationResult(student, subject, template),
                    embedding=tuple(float(value) for value in embedding),
                    lexical_evidence=item.lexical_evidence,
                )
            )
        return tuple(outputs)

    @staticmethod
    def _raise_if_cancelled(cancelled: Callable[[], bool] | None) -> None:
        """Raise the Phase 6 cancellation result before each bounded local stage."""
        if cancelled is not None and cancelled():
            raise GemmaFallbackCancelled("교육 분류가 취소되었습니다.")
