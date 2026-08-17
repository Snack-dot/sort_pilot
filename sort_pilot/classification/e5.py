from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from sort_pilot.curriculum import StudentProfile

from .result import AxisDecision, CandidateScore, DecisionSource, EvidenceContribution
from .subject import SubjectEvidence, SubjectProfile, eligible_subject_profiles


E5_MODEL_ID = "intfloat/multilingual-e5-small"
E5_VECTOR_SIZE = 384
E5_RANKING_POLICY_VERSION = "phase-3-ranking"


class SubjectTextEncoder(Protocol):
    """Minimal 384-dimensional text-encoder boundary used by subject ranking."""

    model_id: str
    vector_size: int

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one dense row per supplied natural-language text."""
        ...


def _embedding_matrix(
    values: object,
    expected_rows: int,
) -> np.ndarray:
    """Validate finite nonzero 384-dimensional embedding rows."""
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.shape != (expected_rows, E5_VECTOR_SIZE):
        raise ValueError(
            f"E5 임베딩 크기는 ({expected_rows}, {E5_VECTOR_SIZE})여야 합니다."
        )
    if not np.isfinite(matrix).all():
        raise ValueError("E5 임베딩 값은 모두 유한해야 합니다.")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("E5 임베딩 벡터는 영벡터일 수 없습니다.")
    return matrix / norms


class FastEmbedE5Encoder:
    """CPU-only FastEmbed adapter for the exact multilingual E5-small model."""

    model_id = E5_MODEL_ID
    vector_size = E5_VECTOR_SIZE

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        allow_download: bool = False,
        threads: int | None = None,
        batch_size: int = 16,
    ) -> None:
        """Initialize from local cache unless an explicit caller allows download."""
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("E5 배치 크기는 1 이상의 정수여야 합니다.")
        try:
            from fastembed import TextEmbedding
            from fastembed.common.model_description import ModelSource, PoolingType
        except ImportError as exc:
            raise RuntimeError("FastEmbed 0.8.0이 설치되어야 합니다.") from exc

        supported = {item["model"] for item in TextEmbedding.list_supported_models()}
        if self.model_id not in supported:
            TextEmbedding.add_custom_model(
                model=self.model_id,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=self.model_id),
                dim=self.vector_size,
                model_file="onnx/model.onnx",
                description="Multilingual E5-small subject embeddings",
                license="mit",
            )
        try:
            self._model = TextEmbedding(
                model_name=self.model_id,
                cache_dir=str(cache_dir) if cache_dir is not None else None,
                threads=threads,
                providers=["CPUExecutionProvider"],
                cuda=False,
                local_files_only=not allow_download,
            )
        except Exception as exc:
            mode = "다운로드 허용" if allow_download else "로컬 캐시 전용"
            raise RuntimeError(f"E5-small 모델을 초기화할 수 없습니다 ({mode}).") from exc
        self.batch_size = batch_size

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Generate normalized 384-dimensional embeddings through FastEmbed."""
        if not texts or not all(isinstance(text, str) and text.strip() for text in texts):
            raise ValueError("E5 입력은 비어 있지 않은 자연어 문자열 목록이어야 합니다.")
        try:
            values = list(self._model.embed(list(texts), batch_size=self.batch_size))
        except Exception as exc:
            raise RuntimeError("E5-small 임베딩 생성에 실패했습니다.") from exc
        return _embedding_matrix(values, len(texts))


class E5SubjectClassifier:
    """Rank catalog subjects using E5-small cosine similarity only."""

    model_id = E5_MODEL_ID

    def __init__(self, encoder: SubjectTextEncoder) -> None:
        """Bind an exact 384-dimensional multilingual E5-small encoder."""
        if encoder.model_id != self.model_id or encoder.vector_size != E5_VECTOR_SIZE:
            raise ValueError("과목 분류기는 정확한 384차원 multilingual-e5-small이 필요합니다.")
        self.encoder = encoder
        self._profile_cache: dict[tuple[SubjectProfile, ...], np.ndarray] = {}

    def _profile_embeddings(self, profiles: tuple[SubjectProfile, ...]) -> np.ndarray:
        """Generate and cache one normalized average vector per subject profile."""
        cached = self._profile_cache.get(profiles)
        if cached is not None:
            return cached

        texts: list[str] = []
        owners: list[int] = []
        for index, profile in enumerate(profiles):
            for text in profile.prototype_texts:
                texts.append(f"passage: {text}")
                owners.append(index)
        prototype_matrix = _embedding_matrix(self.encoder.encode(texts), len(texts))
        rows: list[np.ndarray] = []
        for index in range(len(profiles)):
            average = prototype_matrix[np.asarray(owners) == index].mean(axis=0)
            rows.append(_embedding_matrix((average,), 1)[0])
        matrix = np.asarray(rows, dtype=np.float32)
        self._profile_cache[profiles] = matrix
        return matrix

    def classify(
        self,
        evidence: SubjectEvidence,
        student: StudentProfile,
        profiles: tuple[SubjectProfile, ...],
    ) -> AxisDecision:
        """Rank catalog subjects and retain raw cosine similarity and margin."""
        eligible = eligible_subject_profiles(student, profiles)
        if not eligible:
            raise ValueError("선택한 학생 유형에 사용할 과목 프로필이 없습니다.")
        versions = {profile.version for profile in eligible}
        if len(versions) != 1:
            raise ValueError("한 번의 과목 순위에는 하나의 프로필 버전만 사용할 수 있습니다.")

        profile_matrix = self._profile_embeddings(eligible)
        query_matrix = _embedding_matrix(
            self.encoder.encode((f"query: {evidence.embedding_text}",)),
            1,
        )
        similarities = np.clip(profile_matrix @ query_matrix[0], -1.0, 1.0)
        ranked = sorted(
            zip(eligible, similarities, strict=True),
            key=lambda item: -float(item[1]),
        )
        candidates = tuple(
            CandidateScore(profile.label, float(similarity))
            for profile, similarity in ranked
        )
        top_score = candidates[0].raw_score
        margin = top_score - candidates[1].raw_score if len(candidates) > 1 else 0.0
        top_profile, top_similarity = ranked[0]
        return AxisDecision(
            label=top_profile.label,
            raw_score=top_score,
            calibrated_confidence=None,
            margin=max(0.0, margin),
            candidates=candidates,
            evidence=(
                EvidenceContribution(
                    name="e5_similarity",
                    value=float(top_similarity),
                    detail=self.model_id,
                ),
            ),
            source=DecisionSource.LOCAL,
            model_version=self.model_id,
            profile_version=next(iter(versions)),
            policy_version=E5_RANKING_POLICY_VERSION,
            needs_review=False,
        )
