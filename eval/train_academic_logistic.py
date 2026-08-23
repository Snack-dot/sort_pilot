from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Sequence

import numpy as np

from sort_pilot.classification import (
    ACADEMIC_TOP_CATEGORY,
    ACADEMIC_TYPES,
    AcademicFeatureBuilder,
    AcademicTrainingEvidence,
    FastEmbedE5Encoder,
    HashedWordCharacterTfidf,
    LogisticFitConfig,
    fit_multinomial_logistic,
    load_academic_type_profiles,
    load_subject_profiles,
    personal_similarity_features,
)
from sort_pilot.classifier_engine.extract import extract
from sort_pilot.sandbox import default_sandbox_root, require_in_sandbox, require_sandbox_file


LABEL_COLUMNS = (
    "filename",
    "top_category",
    "subject",
    "academic_type",
    "source_group",
)
STATE_DIRECTORY = ".sort_pilot_state"
TRAINING_DIRECTORY = "logistic"
LABEL_FILE = "training_labels.csv"
MODEL_CACHE_DIRECTORY = Path(STATE_DIRECTORY) / "models" / "fastembed"
L2_CANDIDATES = (0.01, 0.1, 1.0)
REPEATS = 5
SPLITS = 2
PRECISION_TARGET = 0.90
RANDOM_SEED = 20260823


@dataclass(frozen=True, slots=True)
class LabelRow:
    """One human-approved academic label resolved to a sandbox file."""

    path: Path
    filename: str
    subject: str
    academic_type: str
    source_group: str
    family_group: str


def _load_labels(sandbox_root: Path) -> tuple[LabelRow, ...]:
    path = require_sandbox_file(sandbox_root / LABEL_FILE, sandbox_root)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != LABEL_COLUMNS:
            raise ValueError(f"Training label columns must be exactly {LABEL_COLUMNS}.")
        raw_rows = tuple(reader)
    if len(raw_rows) < 300:
        raise ValueError("Academic logistic training requires at least 300 labels.")
    filenames = tuple(row["filename"].strip() for row in raw_rows)
    if len(filenames) != len(set(filenames)):
        raise ValueError("Training labels contain duplicate filenames.")

    allowed_subjects = {
        profile.label for profile in load_subject_profiles()
    }
    rows: list[LabelRow] = []
    for raw in raw_rows:
        if raw["top_category"].strip() != ACADEMIC_TOP_CATEGORY:
            raise ValueError("Phase-one labels must all use the 학업 top category.")
        filename = raw["filename"].strip()
        source = require_sandbox_file(sandbox_root / filename, sandbox_root)
        subject = raw["subject"].strip()
        academic_type = raw["academic_type"].strip()
        source_group = raw["source_group"].strip()
        if subject not in allowed_subjects:
            raise ValueError(f"Label subject is outside the student catalog: {subject}")
        if academic_type not in ACADEMIC_TYPES:
            raise ValueError(f"Unsupported academic type label: {academic_type}")
        if not source_group:
            raise ValueError("Every label needs a non-empty source_group.")
        rows.append(
            LabelRow(
                path=source,
                filename=filename,
                subject=subject,
                academic_type=academic_type,
                source_group=source_group,
                family_group=_family_group(filename),
            )
        )
    return tuple(rows)


def _family_group(filename: str) -> str:
    """Keep likely editions/problem-answer siblings in one evaluation group."""
    value = unicodedata.normalize("NFC", Path(filename).stem).casefold()
    value = re.sub(
        r"(?:정답(?:지|표)?|답지|해설(?:지)?|문제(?:지)?|교사용|학생용|빠른정답)",
        " ",
        value,
    )
    value = re.sub(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", " uuid ", value)
    value = re.sub(r"\d+", " # ", value)
    tokens = re.findall(r"[가-힣a-z]+|#", value)
    normalized = " ".join(tokens[:12]).strip() or unicodedata.normalize("NFC", filename)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _extract_evidence(
    rows: Sequence[LabelRow],
) -> tuple[tuple[LabelRow, ...], tuple[AcademicTrainingEvidence, ...], dict[str, int]]:
    accepted_rows: list[LabelRow] = []
    values: list[AcademicTrainingEvidence] = []
    quality = Counter()
    total = len(rows)
    for completed, row in enumerate(rows, 1):
        vector = extract(row.path)
        quality[vector.extraction_quality] += 1
        lexical = tuple(
            dict.fromkeys(
                feature.t
                for feature in vector.features
                if feature.src in {"body", "ocr"}
                and not feature.t.startswith(("bi:", "tri:"))
            )
        )
        pmi = tuple(
            dict.fromkeys(
                feature.t.split(":", 1)[1]
                for feature in vector.features
                if feature.src == "body" and feature.t.startswith(("bi:", "tri:"))
            )
        )
        accepted_rows.append(row)
        values.append(
            AcademicTrainingEvidence(
                file_name=row.filename,
                natural_text=vector.natural_text,
                template_natural_text=vector.template_natural_text,
                lexical_terms=lexical,
                pmi_collocations=pmi,
                ocr_layout_terms=vector.ocr_layout_evidence,
                numeric_features=vector.numeric_features,
            )
        )
        if completed == 1 or completed % 20 == 0 or completed == total:
            print(f"EXTRACT_PROGRESS={completed}/{total}", flush=True)
    return tuple(accepted_rows), tuple(values), dict(quality)


def _stratified_group_splits(
    targets: Sequence[str],
    groups: Sequence[str],
    *,
    labels: Sequence[str],
    repeats: int = REPEATS,
    splits: int = SPLITS,
    seed: int = RANDOM_SEED,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    """Create deterministic repeated group-disjoint, approximately stratified folds."""
    target_values = tuple(targets)
    group_values = tuple(groups)
    if len(target_values) != len(group_values) or len(target_values) < splits:
        raise ValueError("Grouped split inputs are invalid.")
    label_index = {label: position for position, label in enumerate(labels)}
    if any(value not in label_index for value in target_values):
        raise ValueError("Grouped split target is outside the label set.")
    members: dict[str, list[int]] = {}
    for index, group in enumerate(group_values):
        members.setdefault(group, []).append(index)
    if len(members) < splits:
        raise ValueError("Grouped cross-validation needs at least two groups.")

    overall = np.zeros(len(labels), dtype=np.float64)
    group_counts: dict[str, np.ndarray] = {}
    for group, indices in members.items():
        counts = np.zeros(len(labels), dtype=np.float64)
        for index in indices:
            counts[label_index[target_values[index]]] += 1
        group_counts[group] = counts
        overall += counts
    expected = overall / splits
    result: list[tuple[np.ndarray, np.ndarray]] = []
    all_indices = np.arange(len(target_values))
    for repeat in range(repeats):
        rng = np.random.default_rng(seed + repeat)
        tie_break = {group: float(rng.random()) for group in members}
        ordered_groups = sorted(
            members,
            key=lambda group: (
                -float(group_counts[group].max()),
                -len(members[group]),
                tie_break[group],
            ),
        )
        fold_counts = np.zeros((splits, len(labels)), dtype=np.float64)
        fold_sizes = np.zeros(splits, dtype=np.float64)
        assignments: list[list[str]] = [[] for _ in range(splits)]
        for group in ordered_groups:
            scores: list[tuple[float, float, int]] = []
            for fold in range(splits):
                proposed = fold_counts.copy()
                proposed[fold] += group_counts[group]
                label_error = float(np.square((proposed - expected) / (expected + 1.0)).sum())
                size_error = float(fold_sizes[fold] + len(members[group]))
                scores.append((label_error, size_error, fold))
            selected = min(scores)[2]
            assignments[selected].append(group)
            fold_counts[selected] += group_counts[group]
            fold_sizes[selected] += len(members[group])
        for fold_groups in assignments:
            validation = np.asarray(
                sorted(index for group in fold_groups for index in members[group]),
                dtype=np.int64,
            )
            training = np.setdiff1d(all_indices, validation, assume_unique=True)
            if not len(training) or not len(validation):
                raise RuntimeError("Grouped split produced an empty partition.")
            result.append((training, validation))
    return tuple(result)


def _source_splits(groups: Sequence[str]) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    values = np.asarray(tuple(groups))
    unique = tuple(dict.fromkeys(values.tolist()))
    if len(unique) < 2:
        raise ValueError("Strict source-held-out evaluation needs at least two source groups.")
    all_indices = np.arange(len(values))
    return tuple(
        (
            all_indices[values != group],
            all_indices[values == group],
        )
        for group in unique
    )


def _axis_features(
    base: np.ndarray,
    embeddings: np.ndarray,
    documents: Sequence[str],
    targets: Sequence[str],
    labels: Sequence[str],
    training: np.ndarray,
    validation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    training_documents = tuple(documents[index] for index in training)
    validation_documents = tuple(documents[index] for index in validation)
    tfidf = HashedWordCharacterTfidf.fit(training_documents)
    train_embeddings = embeddings[training]
    train_targets = tuple(targets[index] for index in training)
    train_personal = personal_similarity_features(
        train_embeddings,
        train_embeddings,
        train_targets,
        labels,
        query_reference_indices=tuple(range(len(training))),
    )
    validation_personal = personal_similarity_features(
        embeddings[validation],
        train_embeddings,
        train_targets,
        labels,
    )
    return (
        np.column_stack((base[training], tfidf.transform(training_documents), train_personal)),
        np.column_stack((base[validation], tfidf.transform(validation_documents), validation_personal)),
    )


def _macro_f1(expected: Sequence[str], predicted: Sequence[str], labels: Sequence[str]) -> float:
    scores: list[float] = []
    for label in labels:
        true_positive = sum(a == label and b == label for a, b in zip(expected, predicted))
        false_positive = sum(a != label and b == label for a, b in zip(expected, predicted))
        false_negative = sum(a == label and b != label for a, b in zip(expected, predicted))
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return mean(scores)


def _evaluate_splits(
    base: np.ndarray,
    embeddings: np.ndarray,
    documents: Sequence[str],
    targets: Sequence[str],
    labels: Sequence[str],
    base_feature_names: Sequence[str],
    splits: Sequence[tuple[np.ndarray, np.ndarray]],
    l2: float,
) -> dict:
    feature_names = tuple(base_feature_names) + HashedWordCharacterTfidf.schema_feature_names() + tuple(
        f"personal:{label}" for label in labels
    )
    fold_metrics: list[dict] = []
    all_correct: list[bool] = []
    all_confidence: list[float] = []
    for fold, (training, validation) in enumerate(splits, 1):
        train_x, validation_x = _axis_features(
            base, embeddings, documents, targets, labels, training, validation
        )
        train_targets = tuple(targets[index] for index in training)
        present_labels = tuple(label for label in labels if label in train_targets)
        model, fit = fit_multinomial_logistic(
            train_x,
            train_targets,
            feature_names,
            labels=present_labels,
            config=LogisticFitConfig(l2=l2, max_epochs=1_200),
        )
        probabilities = model.predict_proba(validation_x)
        positions = np.argmax(probabilities, axis=1)
        predicted = tuple(model.labels[int(index)] for index in positions)
        expected = tuple(targets[index] for index in validation)
        correct = tuple(a == b for a, b in zip(expected, predicted, strict=True))
        confidence = probabilities[np.arange(len(validation)), positions]
        fold_metrics.append(
            {
                "fold": fold,
                "count": len(validation),
                "accuracy": sum(correct) / len(correct),
                "macro_f1": _macro_f1(expected, predicted, labels),
                "train_labels": list(model.labels),
                "epochs": fit.epochs,
                "converged": fit.converged,
            }
        )
        all_correct.extend(correct)
        all_confidence.extend(float(value) for value in confidence)
    return {
        "folds": fold_metrics,
        "correct": tuple(all_correct),
        "confidence": tuple(all_confidence),
        "accuracy_mean": mean(value["accuracy"] for value in fold_metrics),
        "accuracy_std": pstdev(value["accuracy"] for value in fold_metrics),
        "macro_f1_mean": mean(value["macro_f1"] for value in fold_metrics),
        "macro_f1_std": pstdev(value["macro_f1"] for value in fold_metrics),
    }


def _calibrate_threshold(correct: Sequence[bool], confidence: Sequence[float]) -> dict:
    candidates = sorted(set(float(value) for value in confidence))
    choices: list[tuple[float, float, float, int]] = []
    for threshold in candidates:
        accepted = [
            outcome
            for outcome, score in zip(correct, confidence, strict=True)
            if score >= threshold
        ]
        if not accepted:
            continue
        precision = sum(accepted) / len(accepted)
        coverage = len(accepted) / len(correct)
        if precision >= PRECISION_TARGET:
            choices.append((coverage, precision, threshold, len(accepted)))
    if not choices:
        return {
            "threshold": 1.0000001,
            "precision": None,
            "coverage": 0.0,
            "review_rate": 1.0,
            "accepted": 0,
            "target": PRECISION_TARGET,
            "target_met": False,
        }
    coverage, precision, threshold, accepted = max(
        choices, key=lambda value: (value[0], value[1], value[2])
    )
    return {
        "threshold": threshold,
        "precision": precision,
        "coverage": coverage,
        "review_rate": 1.0 - coverage,
        "accepted": accepted,
        "target": PRECISION_TARGET,
        "target_met": True,
    }


def _public_evaluation(value: dict) -> dict:
    return {
        key: item
        for key, item in value.items()
        if key not in {"correct", "confidence"}
    }


def _select_l2(
    base: np.ndarray,
    embeddings: np.ndarray,
    documents: Sequence[str],
    targets: Sequence[str],
    labels: Sequence[str],
    feature_names: Sequence[str],
    splits: Sequence[tuple[np.ndarray, np.ndarray]],
) -> tuple[float, dict]:
    candidates: dict[str, dict] = {}
    raw: dict[float, dict] = {}
    for value in L2_CANDIDATES:
        evaluation = _evaluate_splits(
            base, embeddings, documents, targets, labels, feature_names, splits, value
        )
        raw[value] = evaluation
        candidates[str(value)] = _public_evaluation(evaluation)
    selected = max(
        L2_CANDIDATES,
        key=lambda value: (
            raw[value]["macro_f1_mean"],
            raw[value]["accuracy_mean"],
            value,
        ),
    )
    return selected, {"selected_l2": selected, "candidates": candidates}


def _fit_full_model(
    base: np.ndarray,
    embeddings: np.ndarray,
    documents: Sequence[str],
    tfidf: HashedWordCharacterTfidf,
    targets: Sequence[str],
    labels: Sequence[str],
    feature_names: Sequence[str],
    l2: float,
):
    personal = personal_similarity_features(
        embeddings,
        embeddings,
        targets,
        labels,
        query_reference_indices=tuple(range(len(embeddings))),
    )
    complete_names = (
        tuple(feature_names)
        + tfidf.feature_names
        + tuple(f"personal:{label}" for label in labels)
    )
    return fit_multinomial_logistic(
        np.column_stack((base, tfidf.transform(documents), personal)),
        targets,
        complete_names,
        labels=labels,
        config=LogisticFitConfig(l2=l2, max_epochs=2_000),
    )


def _distribution(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items(), key=lambda item: (-item[1], item[0])))


def _write_json(path: Path, value: object, sandbox_root: Path) -> None:
    target = require_in_sandbox(path, sandbox_root, label="training report")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=target.parent, prefix=target.stem, suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_references(
    path: Path,
    sandbox_root: Path,
    subject_embeddings: np.ndarray,
    type_embeddings: np.ndarray,
    subject_targets: Sequence[str],
    type_targets: Sequence[str],
    subject_labels: Sequence[str],
) -> None:
    target = require_in_sandbox(path, sandbox_root, label="training references")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=target.parent, prefix=target.stem, suffix=".npz")
    os.close(descriptor)
    temporary = Path(name)
    subject_index = {label: index for index, label in enumerate(subject_labels)}
    type_index = {label: index for index, label in enumerate(ACADEMIC_TYPES)}
    try:
        with temporary.open("wb") as stream:
            np.savez_compressed(
                stream,
                subject_embeddings=np.asarray(subject_embeddings, dtype=np.float32),
                academic_type_embeddings=np.asarray(type_embeddings, dtype=np.float32),
                subject_targets=np.asarray(
                    [subject_index[value] for value in subject_targets], dtype=np.int16
                ),
                academic_type_targets=np.asarray(
                    [type_index[value] for value in type_targets], dtype=np.int8
                ),
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def train() -> dict:
    """Train both phase-one academic axes from sandbox-only data and save artifacts."""
    sandbox_root = default_sandbox_root().resolve()
    if not sandbox_root.is_dir():
        raise FileNotFoundError(sandbox_root)
    labeled_rows = _load_labels(sandbox_root)
    model_cache = require_in_sandbox(
        sandbox_root / MODEL_CACHE_DIRECTORY,
        sandbox_root,
        label="E5 model cache",
    )
    if not model_cache.is_dir():
        raise FileNotFoundError(
            f"Local E5 cache is required inside the sandbox: {model_cache}"
        )
    output = require_in_sandbox(
        sandbox_root / STATE_DIRECTORY / TRAINING_DIRECTORY,
        sandbox_root,
        label="training output",
    )
    output.mkdir(parents=True, exist_ok=True)

    rows, evidence, extraction_quality = _extract_evidence(labeled_rows)
    encoder = FastEmbedE5Encoder(model_cache, allow_download=False, batch_size=16)
    base = AcademicFeatureBuilder(
        encoder,
        load_subject_profiles(),
        load_academic_type_profiles(),
    ).build(evidence)
    subject_targets = tuple(row.subject for row in rows)
    type_targets = tuple(row.academic_type for row in rows)
    observed_subjects = tuple(
        label for label in base.subject_labels if label in set(subject_targets)
    )
    family_groups = tuple(row.family_group for row in rows)
    source_groups = tuple(row.source_group for row in rows)
    family_subject_splits = _stratified_group_splits(
        subject_targets, family_groups, labels=observed_subjects
    )
    family_type_splits = _stratified_group_splits(
        type_targets, family_groups, labels=ACADEMIC_TYPES
    )

    subject_l2, subject_selection = _select_l2(
        base.subject_matrix,
        base.subject_embeddings,
        base.subject_texts,
        subject_targets,
        observed_subjects,
        base.subject_feature_names,
        family_subject_splits,
    )
    type_l2, type_selection = _select_l2(
        base.academic_type_matrix,
        base.academic_type_embeddings,
        base.academic_type_texts,
        type_targets,
        ACADEMIC_TYPES,
        base.academic_type_feature_names,
        family_type_splits,
    )
    family_subject = _evaluate_splits(
        base.subject_matrix,
        base.subject_embeddings,
        base.subject_texts,
        subject_targets,
        observed_subjects,
        base.subject_feature_names,
        family_subject_splits,
        subject_l2,
    )
    family_type = _evaluate_splits(
        base.academic_type_matrix,
        base.academic_type_embeddings,
        base.academic_type_texts,
        type_targets,
        ACADEMIC_TYPES,
        base.academic_type_feature_names,
        family_type_splits,
        type_l2,
    )
    subject_threshold = _calibrate_threshold(
        family_subject["correct"], family_subject["confidence"]
    )
    type_threshold = _calibrate_threshold(
        family_type["correct"], family_type["confidence"]
    )

    strict_splits = _source_splits(source_groups)
    strict_subject = _evaluate_splits(
        base.subject_matrix,
        base.subject_embeddings,
        base.subject_texts,
        subject_targets,
        observed_subjects,
        base.subject_feature_names,
        strict_splits,
        subject_l2,
    )
    strict_type = _evaluate_splits(
        base.academic_type_matrix,
        base.academic_type_embeddings,
        base.academic_type_texts,
        type_targets,
        ACADEMIC_TYPES,
        base.academic_type_feature_names,
        strict_splits,
        type_l2,
    )
    subject_model, subject_fit = _fit_full_model(
        base.subject_matrix,
        base.subject_embeddings,
        base.subject_texts,
        base.subject_tfidf,
        subject_targets,
        observed_subjects,
        base.subject_feature_names,
        subject_l2,
    )
    type_model, type_fit = _fit_full_model(
        base.academic_type_matrix,
        base.academic_type_embeddings,
        base.academic_type_texts,
        base.academic_type_tfidf,
        type_targets,
        ACADEMIC_TYPES,
        base.academic_type_feature_names,
        type_l2,
    )
    subject_model.save(output / "subject_model.npz", sandbox_root)
    type_model.save(output / "academic_type_model.npz", sandbox_root)
    base.subject_tfidf.save(output / "subject_text_tfidf.npz", sandbox_root)
    base.academic_type_tfidf.save(
        output / "academic_type_text_tfidf.npz", sandbox_root
    )
    for stale_name in ("text_tfidf.npz", "text_tfidf.json"):
        require_in_sandbox(
            output / stale_name,
            sandbox_root,
            label="obsolete TF-IDF artifact",
        ).unlink(missing_ok=True)
    _write_references(
        output / "personal_references.npz",
        sandbox_root,
        base.subject_embeddings,
        base.academic_type_embeddings,
        subject_targets,
        type_targets,
        observed_subjects,
    )

    subject_baseline_accuracy = sum(
        expected == predicted
        for expected, predicted in zip(subject_targets, base.subject_baseline, strict=True)
    ) / len(rows)
    type_baseline_accuracy = sum(
        expected == predicted
        for expected, predicted in zip(type_targets, base.academic_type_baseline, strict=True)
    ) / len(rows)
    warnings: list[str] = []
    for label, count in _distribution(subject_targets).items():
        if count < 5:
            warnings.append(
                f"subject '{label}' has only {count} labels; variance and recall are unstable"
            )
    report = {
        "version": "academic-logistic-training-v2",
        "scope": {
            "sandbox": str(sandbox_root),
            "top_category": ACADEMIC_TOP_CATEGORY,
            "path_contract": "학업/{과목}/{교재|문제지|정답지}",
            "labels": len(rows),
            "labels_available": len(labeled_rows),
            "extraction_quality": extraction_quality,
            "labels_excluded_for_review": len(labeled_rows) - len(rows),
            "source_groups": len(set(source_groups)),
            "family_groups": len(set(family_groups)),
            "subject_distribution": _distribution(subject_targets),
            "academic_type_distribution": _distribution(type_targets),
        },
        "validation": {
            "method": "5x repeated 2-fold family-group CV plus strict leave-source-out CV",
            "subject": {
                "l2_selection": subject_selection,
                "family_group_cv": _public_evaluation(family_subject),
                "strict_source_cv": _public_evaluation(strict_subject),
                "threshold": subject_threshold,
                "weighted_policy_baseline_accuracy": subject_baseline_accuracy,
            },
            "academic_type": {
                "l2_selection": type_selection,
                "family_group_cv": _public_evaluation(family_type),
                "strict_source_cv": _public_evaluation(strict_type),
                "threshold": type_threshold,
                "weighted_policy_baseline_accuracy": type_baseline_accuracy,
            },
        },
        "final_fit": {
            "text_features": {
                "word_tfidf": True,
                "character_tfidf": True,
                "raw_vocabulary_persisted": False,
                "pdf_numeric_features": True,
            },
            "subject": {
                "labels": list(subject_model.labels),
                "features": len(subject_model.feature_names),
                "l2": subject_l2,
                "epochs": subject_fit.epochs,
                "loss": subject_fit.final_loss,
                "converged": subject_fit.converged,
            },
            "academic_type": {
                "labels": list(type_model.labels),
                "features": len(type_model.feature_names),
                "l2": type_l2,
                "epochs": type_fit.epochs,
                "loss": type_fit.final_loss,
                "converged": type_fit.converged,
            },
        },
        "warnings": warnings,
        "privacy": {
            "raw_text_persisted": False,
            "ocr_text_persisted": False,
            "tfidf_raw_vocabulary_persisted": False,
            "filenames_in_report": False,
            "network_used": False,
        },
    }
    _write_json(output / "training_report.json", report, sandbox_root)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train local 학업 subject/type logistic models from Downloads/sandbox only."
    )
    parser.parse_args()
    train()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
