from __future__ import annotations

import hashlib
import json
import random
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .classifier_engine.extract import supports_content_analysis
from .classifier_engine.hierarchy import TYPE_FAMILIES, route_type
from .classifier_engine.topics import (
    AnalysisRecord,
    TopicClassifier,
    TopicProfile,
    TopicProfileStore,
    TopicProposal,
    contextual_terms,
    humanize_term,
    normalize_tag,
    validate_topic_name,
)
from .models import ApprovedFileMove, FileSuggestion
from .scanner import collect_candidates


@dataclass(slots=True)
class CalibrationCluster:
    """Editable topic candidate built from one sample cluster."""

    id: str
    family: str
    record_indexes: list[int]
    topic: str
    tags: list[str] = field(default_factory=list)
    excluded: bool = False
    existing_profile_id: str | None = None


@dataclass(slots=True)
class CalibrationDraft:
    """In-memory calibration result; nothing is persisted until user approval."""

    records: list[AnalysisRecord]
    clusters: list[CalibrationCluster]

    def surfaced_records(self) -> list[AnalysisRecord]:
        """Return only the records referenced by a surfaced cluster, in index order."""
        used = sorted({index for cluster in self.clusters for index in cluster.record_indexes})
        return [self.records[index] for index in used]


class CalibrationSampler:
    """Choose bounded, extension-diverse top-level samples and remember prior files."""

    def __init__(self, state_path: Path, per_family: int = 3, rng: random.Random | None = None) -> None:
        """Configure local state, family limit, and an injectable random source."""
        self.state_path = state_path
        self.per_family = per_family
        self.rng = rng or random.SystemRandom()

    def select(self, roots: Iterable[Path]) -> list[Path]:
        """Return up to ``per_family`` candidates per fixed type family."""
        candidates: list[tuple[int, Path]] = []
        for root_index, root in enumerate(roots):
            if not root.is_dir():
                continue
            for path in collect_candidates(root):
                if supports_content_analysis(path):
                    candidates.append((root_index, path.resolve()))
        seen = self._load_seen()
        selected: list[Path] = []
        for family in TYPE_FAMILIES:
            family_items = [(root, path) for root, path in candidates if route_type(path) == family]
            unseen = [item for item in family_items if self.fingerprint(item[1]) not in seen]
            repeat = [item for item in family_items if self.fingerprint(item[1]) in seen]
            selected.extend(self._stratified(unseen, self.per_family))
            remaining = self.per_family - sum(route_type(path) == family for path in selected)
            if remaining > 0:
                selected.extend(self._stratified(repeat, remaining))
        return selected

    def remember(self, paths: Iterable[Path]) -> None:
        """Atomically record approved sample fingerprints for future reruns."""
        self.remember_fingerprints(self.fingerprint(path) for path in paths)

    def remember_fingerprints(self, fingerprints: Iterable[str]) -> None:
        """Atomically record fingerprints captured before sample files were moved."""
        seen = self._load_seen()
        seen.update(fingerprints)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "seen": sorted(seen)}
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.state_path.parent, delete=False, suffix=".tmp"
        ) as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            temporary = Path(stream.name)
        temporary.replace(self.state_path)

    def _stratified(self, items: list[tuple[int, Path]], limit: int) -> list[Path]:
        """Round-robin shuffled root/extension buckets up to the requested limit."""
        buckets: dict[tuple[int, str], list[Path]] = defaultdict(list)
        for root, path in items:
            buckets[(root, path.suffix.casefold())].append(path)
        for values in buckets.values():
            self.rng.shuffle(values)
        keys = list(buckets)
        self.rng.shuffle(keys)
        chosen: list[Path] = []
        while keys and len(chosen) < limit:
            next_keys: list[tuple[int, str]] = []
            for key in keys:
                values = buckets[key]
                if values and len(chosen) < limit:
                    chosen.append(values.pop())
                if values:
                    next_keys.append(key)
            keys = next_keys
        return chosen

    def _load_seen(self) -> set[str]:
        """Read remembered fingerprints, treating absent or corrupt state as empty."""
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {str(value) for value in data.get("seen", [])}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return set()

    @staticmethod
    def fingerprint(path: Path) -> str:
        """Hash path metadata without storing a readable private path."""
        stat = path.stat()
        value = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}"
        return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


class CalibrationService:
    """Build drafts, apply local tag suggestions, and persist approved profiles."""

    def __init__(self, classifier: TopicClassifier, store: TopicProfileStore) -> None:
        """Bind the classifier and persistent profile store used by calibration."""
        self.classifier = classifier
        self.store = store

    def build_draft(
        self,
        records: list[AnalysisRecord],
        suggestions: dict[str, tuple[str, tuple[str, ...]]] | None = None,
        min_cluster_size: int = 1,
    ) -> CalibrationDraft:
        """Convert automatic clusters of at least ``min_cluster_size`` records into editable topic groups."""
        clusters: list[CalibrationCluster] = []
        proposals = [
            proposal
            for proposal in self.classifier.discover(records)
            if len(proposal.record_indexes) >= min_cluster_size
        ]
        for proposal in proposals:
            cluster_id = self.cluster_id(proposal)
            suggested = (suggestions or {}).get(cluster_id)
            topic = suggested[0] if suggested else self.fallback_topic(proposal)
            vocabulary = [
                term
                for term, _ in sorted(
                    proposal.aggregate_weights.items(), key=lambda item: (-item[1], item[0])
                )[:60]
            ]
            vocabulary_keys = {normalize_tag(term) for term in vocabulary}
            model_tags = [
                tag
                for tag in suggested[1]
                if normalize_tag(tag) in vocabulary_keys
            ] if suggested else []
            tags = model_tags + vocabulary
            clusters.append(
                CalibrationCluster(
                    id=cluster_id,
                    family=proposal.family,
                    record_indexes=list(proposal.record_indexes),
                    topic=topic,
                    tags=list(dict.fromkeys(filter(None, map(normalize_tag, tags)))),
                )
            )
        return CalibrationDraft(records, clusters)

    def save_draft(self, draft: CalibrationDraft) -> list[TopicProfile]:
        """Build and atomically persist profiles from the approved calibration draft."""
        profiles = self.profiles_from_draft(draft)
        self.store.save(profiles)
        return profiles

    def profiles_from_draft(self, draft: CalibrationDraft) -> list[TopicProfile]:
        """Build profiles from a draft without mutating persistent state."""
        profiles = self.store.load()
        by_id = {profile.id: profile for profile in profiles}
        by_name = {(profile.family, profile.name.casefold()): profile for profile in profiles}
        for cluster in draft.clusters:
            if cluster.excluded or not cluster.record_indexes:
                continue
            name = validate_topic_name(cluster.topic)
            key = cluster.family, name.casefold()
            profile = by_id.get(cluster.existing_profile_id or "") or by_name.get(key)
            if profile is None:
                profile = self.store.new_profile(cluster.family, name, cluster.tags, origin="discovered")
                profiles.append(profile)
            else:
                profile = TopicProfile(
                    id=profile.id,
                    family=profile.family,
                    name=name,
                    tags=tuple(dict.fromkeys(filter(None, map(normalize_tag, cluster.tags)))),
                    example_weights=profile.example_weights,
                    example_count=profile.example_count,
                    negative_weights=profile.negative_weights,
                    negative_count=profile.negative_count,
                    origin=profile.origin,
                    enabled=profile.enabled,
                    created_at=profile.created_at,
                    updated_at=profile.updated_at,
                )
            examples = [draft.records[index] for index in cluster.record_indexes]
            profile = merge_profile_evidence(profile, examples)
            by_id[profile.id] = profile
            by_name[key] = profile
        final = [by_id.get(profile.id, profile) for profile in profiles]
        self.store._validate_profiles(final)
        return final

    @staticmethod
    def seed_changes(
        draft: CalibrationDraft,
        desktop_folder: Path,
        downloads_folder: Path,
    ) -> list[ApprovedFileMove]:
        """Build immediate approved moves for every non-excluded calibration seed."""
        changes: list[ApprovedFileMove] = []
        desktop = desktop_folder.resolve()
        downloads = downloads_folder.resolve()
        for cluster in draft.clusters:
            if cluster.excluded:
                continue
            topic = validate_topic_name(cluster.topic)
            for index in cluster.record_indexes:
                record = draft.records[index]
                source = record.source.resolve()
                destination_root = "desktop" if source.is_relative_to(desktop) else "downloads"
                if not source.is_relative_to(desktop) and not source.is_relative_to(downloads):
                    destination_root = "current"
                suggestion = FileSuggestion(
                    record.file_path,
                    record.file_name,
                    record.suggested_name,
                    f"{cluster.family}/{topic}",
                    f"보정 시드로 확인한 주제 '{topic}'",
                )
                changes.append(ApprovedFileMove(suggestion, destination_root, suggestion.folder, True))
        return changes

    @staticmethod
    def cluster_id(proposal: TopicProposal) -> str:
        """Return a stable opaque identifier shared with the local tagger."""
        value = f"{proposal.family}|{'|'.join(proposal.representative_files)}|{proposal.record_indexes}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def fallback_topic(proposal: TopicProposal) -> str:
        """Create a deterministic human-editable fallback, preferring collocation phrases over loose terms."""
        collocation = next(
            (humanize_term(term) for term in proposal.top_terms if term.startswith(("bi:", "tri:"))),
            None,
        )
        humanized = [word for word in (humanize_term(term) for term in proposal.top_terms) if word]
        source = collocation or " ".join(humanized[:2]).strip()
        if not source and proposal.representative_files:
            source = Path(proposal.representative_files[0]).stem
        cleaned = "".join("_" if char in '<>:"/\\|?*' else char for char in source).strip(" ._")
        return cleaned[:60] or f"Topic-{proposal.record_indexes[0] + 1}"


def merge_profile_evidence(
    profile: TopicProfile,
    records: Iterable[AnalysisRecord],
    *,
    negative: bool = False,
) -> TopicProfile:
    """Merge averaged record terms into positive or negative profile evidence."""
    records = list(records)
    if not records:
        return profile
    new_weights = TopicClassifier.aggregate_terms(contextual_terms(record.terms) for record in records)
    old_weights = profile.negative_weights if negative else profile.example_weights
    old_count = profile.negative_count if negative else profile.example_count
    new_count = len(records)
    total_count = old_count + new_count
    terms = set(old_weights) | set(new_weights)
    merged = {
        term: (old_weights.get(term, 0.0) * old_count + new_weights.get(term, 0.0) * new_count)
        / total_count
        for term in terms
    }
    values = {"negative_weights": merged, "negative_count": total_count} if negative else {
        "example_weights": merged,
        "example_count": total_count,
    }
    from dataclasses import replace

    return replace(profile, **values)


def learn_correction(
    profiles: list[TopicProfile],
    record: AnalysisRecord,
    predicted_topic: str | None,
    chosen_topic: str,
) -> list[TopicProfile]:
    """Apply signed feedback for one successfully moved file."""
    chosen = next(
        profile
        for profile in profiles
        if profile.family == record.family and profile.name.casefold() == chosen_topic.casefold()
    )
    result: list[TopicProfile] = []
    for profile in profiles:
        if profile.id == chosen.id:
            profile = merge_profile_evidence(profile, [record])
        elif (
            predicted_topic
            and predicted_topic.casefold() != chosen_topic.casefold()
            and profile.family == record.family
            and profile.name.casefold() == predicted_topic.casefold()
        ):
            profile = merge_profile_evidence(profile, [record], negative=True)
        result.append(profile)
    return result
