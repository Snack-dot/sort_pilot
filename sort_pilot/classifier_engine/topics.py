from __future__ import annotations

import json
import math
import os
import re
import tempfile
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from .embeddings import SEMANTIC_MATCH_THRESHOLD, doc_vectors, load_vocab, semantic_similarity
from .extract import SEMANTIC_FEATURE_SOURCES
from .hierarchy import TYPE_FAMILIES, UNSORTED_TOPIC, hierarchical_folder
from .types import FeatureVector

PROFILE_THRESHOLDS = {"문서": 0.25, "이미지": 0.20}
DISCOVERY_THRESHOLDS = {"문서": 0.30, "이미지": 0.22}
OTHER_PROFILE_THRESHOLD = 0.30
DISCOVERY_FAMILIES = frozenset(DISCOVERY_THRESHOLDS)
USER_ORIGINS = frozenset({"user", "discovered", "migration"})
WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
GENERIC_PREFIXES = ("image:", "aspect:", "color:", "n_person:", "n_objects:", "subject:")
GENERIC_TERMS = {"needs_content", "kakao_export", "no_ext"}
CONTEXT_PREFIX = "co:"
PAIR_WEIGHT_SCALE = 0.1
SMALL_BATCH_FLOOR_SCALE = 0.2


def utc_now() -> str:
    """Return a stable UTC timestamp for profile persistence."""
    return datetime.now(timezone.utc).isoformat()


def normalize_tag(tag: str) -> str:
    """Normalize a user tag for case-insensitive matching and persistence."""
    return " ".join(tag.casefold().strip().split())


def validate_topic_name(name: str) -> str:
    """Validate and return a single safe topic-folder name."""
    candidate = name.strip().rstrip(". ")
    if not candidate:
        raise ValueError("주제 폴더 이름을 입력하세요.")
    if candidate.casefold() == UNSORTED_TOPIC.casefold():
        raise ValueError(f"'{UNSORTED_TOPIC}'는 예약된 이름입니다.")
    if candidate in {".", ".."} or WINDOWS_INVALID.search(candidate):
        raise ValueError("폴더 이름에 사용할 수 없는 문자가 있습니다.")
    return candidate


@dataclass(frozen=True, slots=True)
class TopicProfile:
    """One family-specific semantic topic learned from tags or example features."""

    id: str
    family: str
    name: str
    tags: tuple[str, ...] = ()
    example_weights: dict[str, float] = field(default_factory=dict)
    example_count: int = 0
    negative_weights: dict[str, float] = field(default_factory=dict)
    negative_count: int = 0
    origin: str = "user"
    enabled: bool = True
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def pseudo_terms(self) -> dict[str, float]:
        """Combine learned contextual evidence with moderately weighted tag tokens."""
        terms = Counter(self.example_weights)
        for tag in self.tags:
            for token in tag_tokens(tag):
                terms[token] += 1.5
        return dict(terms)

    def negative_terms(self) -> dict[str, float]:
        """Return evidence learned from files moved away from this topic."""
        return dict(self.negative_weights)


@dataclass(slots=True)
class AnalysisRecord:
    """One extracted file awaiting family-specific topic assignment."""

    file_path: str
    file_name: str
    suggested_name: str
    family: str
    terms: dict[str, float]
    topic: str | None = None
    score: float = 0.0
    reason: str = ""
    engine_category: str | None = None
    engine_action: str = "unsorted"
    engine_tier: str = ""
    decision_id: int | None = None

    @property
    def source(self) -> Path:
        """Return the analyzed source path."""
        return Path(self.file_path)

    @property
    def folder(self) -> str:
        """Return the final two-level relative destination folder."""
        return hierarchical_folder(self.family, self.topic)


@dataclass(frozen=True, slots=True)
class TopicProposal:
    """A current-batch unmatched cluster awaiting a user-supplied topic name."""

    family: str
    record_indexes: tuple[int, ...]
    top_terms: tuple[str, ...]
    representative_files: tuple[str, ...]
    aggregate_weights: dict[str, float]


def tag_tokens(value: str) -> list[str]:
    """Tokenize a normalized tag without requiring the morphological analyzer."""
    return re.findall(r"[가-힣]+|[a-z][a-z0-9]*", normalize_tag(value))


def vector_terms(vector: FeatureVector, source_weights: dict[str, float]) -> dict[str, float]:
    """Convert only body/OCR/object evidence into terms used for semantic topics."""
    terms: Counter[str] = Counter()
    for feature in vector.features:
        token = normalize_tag(feature.t)
        if not token or token in GENERIC_TERMS or token.startswith(GENERIC_PREFIXES):
            continue
        if feature.src not in SEMANTIC_FEATURE_SOURCES:
            continue
        terms[token] += float(feature.n) * float(source_weights.get(feature.src, 1.0))
    return dict(terms)


def contextual_terms(
    terms: dict[str, float],
    max_terms: int = 40,
    max_pairs: int = 120,
) -> dict[str, float]:
    """Expand bounded base words with weighted within-file co-occurrence pairs."""
    ranked = [
        (term, weight)
        for term, weight in sorted(terms.items(), key=lambda item: (-item[1], item[0]))
        if weight > 0 and not term.startswith(CONTEXT_PREFIX)
    ][:max_terms]
    expanded = Counter({term: weight for term, weight in ranked})
    pairs: list[tuple[float, str]] = []
    for position, (left, left_weight) in enumerate(ranked):
        for right, right_weight in ranked[position + 1:]:
            first, second = sorted((left, right))
            pair = f"{CONTEXT_PREFIX}{first}|{second}"
            pairs.append((math.sqrt(left_weight * right_weight) * PAIR_WEIGHT_SCALE, pair))
    for weight, pair in sorted(pairs, key=lambda item: (-item[0], item[1]))[:max_pairs]:
        expanded[pair] = weight
    return dict(expanded)


class TopicProfileStore:
    """Atomic versioned JSON persistence for family-specific topic profiles."""

    def __init__(self, path: Path) -> None:
        """Create an empty user-owned profile document when none exists."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save([])

    def load(self) -> list[TopicProfile]:
        """Read and validate all persisted topic profiles."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data["profiles"]
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError(f"주제 프로필을 읽을 수 없습니다: {self.path}") from exc
        profiles = []
        removed_builtins = False
        for item in items:
            if str(item.get("origin", "user")) == "builtin":
                removed_builtins = True
                continue
            profiles.append(
                TopicProfile(
                    id=str(item["id"]),
                    family=str(item["family"]),
                    name=str(item["name"]),
                    tags=tuple(item.get("tags", ())),
                    example_weights={str(k): float(v) for k, v in item.get("example_weights", {}).items()},
                    example_count=int(item.get("example_count", 0)),
                    negative_weights={str(k): float(v) for k, v in item.get("negative_weights", {}).items()},
                    negative_count=int(item.get("negative_count", 0)),
                    origin=str(item.get("origin", "user")),
                    enabled=bool(item.get("enabled", True)),
                    created_at=str(item.get("created_at", utc_now())),
                    updated_at=str(item.get("updated_at", utc_now())),
                )
            )
        self._validate_profiles(profiles)
        if removed_builtins or int(data.get("version", 1)) < 3:
            self.save(profiles)
        return profiles

    def save(self, profiles: Iterable[TopicProfile]) -> None:
        """Validate and atomically replace the complete profile document."""
        normalized = list(profiles)
        self._validate_profiles(normalized)
        payload = {"version": 3, "profiles": [asdict(profile) for profile in normalized]}
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix="topic-profiles-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def upsert(self, profile: TopicProfile) -> TopicProfile:
        """Insert or replace one validated profile and return its normalized value."""
        profiles = self.load()
        normalized = replace(
            profile,
            name=validate_topic_name(profile.name),
            tags=tuple(dict.fromkeys(filter(None, map(normalize_tag, profile.tags)))),
            updated_at=utc_now(),
        )
        for index, current in enumerate(profiles):
            if current.id == normalized.id:
                profiles[index] = normalized
                break
        else:
            profiles.append(normalized)
        self.save(profiles)
        return normalized

    def delete(self, profile_id: str) -> None:
        """Delete a user-created profile without touching physical folders or files."""
        profiles = self.load()
        target = next((profile for profile in profiles if profile.id == profile_id), None)
        if target is None:
            return
        self.save(profile for profile in profiles if profile.id != profile_id)

    @staticmethod
    def new_profile(
        family: str,
        name: str,
        tags: Iterable[str] = (),
        example_weights: dict[str, float] | None = None,
        example_count: int = 0,
        origin: str = "user",
    ) -> TopicProfile:
        """Construct a new unsaved profile with normalized identity metadata."""
        return TopicProfile(
            id=uuid.uuid4().hex,
            family=family,
            name=validate_topic_name(name),
            tags=tuple(dict.fromkeys(filter(None, map(normalize_tag, tags)))),
            example_weights=example_weights or {},
            example_count=example_count,
            origin=origin,
        )

    @staticmethod
    def _validate_profiles(profiles: list[TopicProfile]) -> None:
        """Enforce family membership and case-insensitive name uniqueness."""
        seen: set[tuple[str, str]] = set()
        for profile in profiles:
            if profile.family not in TYPE_FAMILIES:
                raise ValueError(f"알 수 없는 파일 유형입니다: {profile.family}")
            if profile.origin not in USER_ORIGINS:
                raise ValueError(f"알 수 없는 사용자 주제 출처입니다: {profile.origin}")
            name = validate_topic_name(profile.name)
            key = profile.family, name.casefold()
            if key in seen:
                raise ValueError(f"'{profile.family}'에 같은 이름의 주제가 이미 있습니다: {name}")
            seen.add(key)

class TopicClassifier:
    """Match saved profiles and discover deterministic current-batch TF-IDF topics."""

    def assign_existing(
        self,
        records: list[AnalysisRecord],
        profiles: Iterable[TopicProfile],
    ) -> list[AnalysisRecord]:
        """Assign only enabled user-created or user-approved profiles per family."""
        enabled = [
            profile for profile in profiles
            if profile.enabled and profile.origin in USER_ORIGINS
        ]
        for family in TYPE_FAMILIES:
            family_records = [
                record for record in records
                if record.family == family and record.terms
            ]
            family_profiles = [profile for profile in enabled if profile.family == family]
            if not family_records or not family_profiles:
                continue
            contextual_records = {id(record): contextual_terms(record.terms) for record in family_records}
            documents = list(contextual_records.values())
            documents.extend(profile.pseudo_terms() for profile in family_profiles)
            documents.extend(
                profile.negative_terms() for profile in family_profiles if profile.negative_weights
            )
            idf = self._idf(documents)
            profile_vectors = {
                profile.id: self._tfidf(profile.pseudo_terms(), idf) for profile in family_profiles
            }
            negative_vectors = {
                profile.id: self._tfidf(profile.negative_terms(), idf)
                for profile in family_profiles
            }
            vocab = load_vocab()
            semantic_profile_vectors = (
                {
                    profile.id: doc_vectors(profile.pseudo_terms(), vocab, idf)
                    for profile in family_profiles
                }
                if vocab
                else {}
            )
            for record in family_records:
                record_vector = self._tfidf(contextual_records[id(record)], idf)
                profile, score, tag_match = self._best_profile(
                    record, record_vector, family_profiles, profile_vectors, negative_vectors
                )
                if profile is not None:
                    record.topic = profile.name
                    record.score = score
                    record.reason = (
                        f"사용자 태그 '{profile.name}' 일치" if tag_match
                        else f"{profile.name} 주제 유사도 {score:.3f}"
                    )
                elif vocab:
                    profile, score = self._semantic_match(
                        contextual_records[id(record)], family_profiles, semantic_profile_vectors, vocab, idf
                    )
                    if profile is not None:
                        record.topic = profile.name
                        record.score = score
                        record.reason = f"{profile.name} 의미 유사도 {score:.3f} (사전학습 단어 벡터)"
        return records

    @staticmethod
    def _semantic_match(
        raw_terms: dict[str, float],
        profiles: list[TopicProfile],
        semantic_profile_vectors: dict[str, list[np.ndarray]],
        vocab: dict[str, np.ndarray],
        idf: dict[str, float],
    ) -> tuple[TopicProfile | None, float]:
        """Rescue an unmatched record using pretrained word-vector similarity."""
        record_vectors = doc_vectors(raw_terms, vocab, idf)
        if not record_vectors:
            return None, 0.0
        scored = [
            (semantic_similarity(record_vectors, semantic_profile_vectors.get(profile.id, [])), profile)
            for profile in profiles
        ]
        if not scored:
            return None, 0.0
        score, profile = max(scored, key=lambda item: (item[0], item[1].name.casefold()))
        return (profile, score) if score >= SEMANTIC_MATCH_THRESHOLD else (None, 0.0)

    def discover(self, records: list[AnalysisRecord]) -> list[TopicProposal]:
        """Propose every unmatched file, grouping similar documents and images."""
        proposals: list[TopicProposal] = []
        for family in TYPE_FAMILIES:
            indexed = [
                (index, record)
                for index, record in enumerate(records)
                if record.family == family and not record.topic and record.terms
            ]
            if not indexed:
                continue
            expanded = {index: contextual_terms(record.terms) for index, record in indexed}
            idf = self._idf(list(expanded.values()))
            vectors = {index: self._tfidf(expanded[index], idf) for index, _ in indexed}
            vocab = load_vocab()
            semantic_vectors = (
                {index: doc_vectors(expanded[index], vocab, idf) for index, _ in indexed} if vocab else {}
            )
            clusters = self._stable_clusters(
                indexed,
                vectors,
                self._adaptive_threshold(
                    vectors,
                    DISCOVERY_THRESHOLDS.get(family, OTHER_PROFILE_THRESHOLD),
                ),
                semantic_vectors,
            )
            for indexes in clusters:
                aggregate = self.aggregate_terms(records[index].terms for index in indexes)
                centroid = self._centroid([vectors[index] for index in indexes])
                ranked = sorted(indexes, key=lambda index: (-self._cosine(vectors[index], centroid), records[index].file_path))
                top_terms = tuple(
                    term
                    for term, _ in sorted(aggregate.items(), key=lambda item: (-item[1], item[0]))[:20]
                    if not term.startswith(CONTEXT_PREFIX)
                )
                proposals.append(
                    TopicProposal(
                        family=family,
                        record_indexes=tuple(indexes),
                        top_terms=top_terms,
                        representative_files=tuple(records[index].file_name for index in ranked[:5]),
                        aggregate_weights=aggregate,
                    )
                )
        return sorted(proposals, key=lambda proposal: (proposal.family, proposal.record_indexes))

    @staticmethod
    def aggregate_terms(documents: Iterable[dict[str, float]]) -> dict[str, float]:
        """Average semantic term weights across examples for persistent profiles."""
        documents = list(documents)
        if not documents:
            return {}
        total: Counter[str] = Counter()
        for document in documents:
            total.update(document)
        return {term: weight / len(documents) for term, weight in total.items()}

    def _best_profile(
        self,
        record: AnalysisRecord,
        record_vector: dict[str, float],
        profiles: list[TopicProfile],
        profile_vectors: dict[str, dict[str, float]],
        negative_vectors: dict[str, dict[str, float]],
    ) -> tuple[TopicProfile | None, float, bool]:
        """Return the best threshold-qualified profile from one precedence group."""
        scored = [
            (
                max(
                    0.0,
                    self._cosine(record_vector, profile_vectors[profile.id])
                    - 0.65 * self._cosine(record_vector, negative_vectors[profile.id]),
                ),
                profile,
                self._tag_matches(record, profile),
            )
            for profile in profiles
        ]
        if scored:
            score, profile, tag_match = max(
                scored, key=lambda item: (item[0], item[1].name.casefold())
            )
            threshold = PROFILE_THRESHOLDS.get(record.family, OTHER_PROFILE_THRESHOLD)
            if score >= threshold:
                return profile, score, tag_match
        return None, 0.0, False

    @staticmethod
    def _tag_matches(record: AnalysisRecord, profile: TopicProfile) -> bool:
        """Return whether every token of any explicit tag occurs in content evidence."""
        record_terms = set(record.terms)
        return any(
            tokens and set(tokens) <= record_terms
            for tag, tokens in ((tag, tag_tokens(tag)) for tag in profile.tags)
        )

    @staticmethod
    def _idf(documents: list[dict[str, float]]) -> dict[str, float]:
        """Calculate smoothed inverse-document frequencies for sparse documents."""
        count = len(documents)
        frequency: Counter[str] = Counter()
        for document in documents:
            frequency.update(document.keys())
        return {term: math.log((1 + count) / (1 + seen)) + 1 for term, seen in frequency.items()}

    @staticmethod
    def _tfidf(terms: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
        """Create an L2-normalized sparse TF-IDF vector from weighted terms."""
        vector = {term: math.log1p(max(weight, 0.0)) * idf.get(term, 1.0) for term, weight in terms.items() if weight > 0}
        norm = math.sqrt(sum(value * value for value in vector.values()))
        return {term: value / norm for term, value in vector.items()} if norm else {}

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        """Return sparse cosine similarity for normalized or centroid vectors."""
        if not left or not right:
            return 0.0
        small, large = (left, right) if len(left) <= len(right) else (right, left)
        dot = sum(value * large.get(term, 0.0) for term, value in small.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @staticmethod
    def _centroid(vectors: list[dict[str, float]]) -> dict[str, float]:
        """Average sparse vectors into a cluster centroid."""
        if not vectors:
            return {}
        total: Counter[str] = Counter()
        for vector in vectors:
            total.update(vector)
        return {term: value / len(vectors) for term, value in total.items()}

    def _adaptive_threshold(self, vectors: dict[int, dict[str, float]], floor: float) -> float:
        """Derive a bounded merge threshold from the batch similarity distribution."""
        indexes = sorted(vectors)
        similarities: list[float] = []
        for position, left in enumerate(indexes):
            for right in indexes[position + 1:]:
                similarity = self._cosine(vectors[left], vectors[right])
                if similarity > 0:
                    similarities.append(similarity)
        if not similarities:
            return 1.0
        if len(vectors) <= 3:
            return floor * SMALL_BATCH_FLOOR_SCALE
        ordered = sorted(similarities)
        median = ordered[len(ordered) // 2]
        deviations = sorted(abs(value - median) for value in ordered)
        mad = deviations[len(deviations) // 2]
        return min(0.75, max(floor, median - mad))

    def _stable_clusters(
        self,
        indexed: list[tuple[int, AnalysisRecord]],
        vectors: dict[int, dict[str, float]],
        threshold: float,
        semantic_vectors: dict[int, list[np.ndarray]] | None = None,
    ) -> list[list[int]]:
        """Build deterministic similarity-connected clusters for user review.

        Two records connect if either their lexical co-occurrence cosine clears
        ``threshold`` or, when pretrained word vectors are loaded, their
        distinctive-word embedding similarity clears ``SEMANTIC_MATCH_THRESHOLD``.
        """
        semantic_vectors = semantic_vectors or {}
        ordered = [index for index, _ in sorted(indexed, key=lambda item: item[1].file_path.casefold())]
        clusters: list[list[int]] = []
        remaining = set(ordered)
        for seed in ordered:
            if seed not in remaining:
                continue
            remaining.remove(seed)
            cluster: list[int] = []
            pending = [seed]
            while pending:
                current = pending.pop()
                cluster.append(current)
                neighbors = [
                    candidate
                    for candidate in ordered
                    if candidate in remaining
                    and (
                        self._cosine(vectors[current], vectors[candidate]) >= threshold
                        or semantic_similarity(
                            semantic_vectors.get(current, []), semantic_vectors.get(candidate, [])
                        )
                        >= SEMANTIC_MATCH_THRESHOLD
                    )
                ]
                for candidate in neighbors:
                    remaining.remove(candidate)
                    pending.append(candidate)
            clusters.append(sorted(cluster))
        return clusters
