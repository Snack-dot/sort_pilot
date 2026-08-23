from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from sort_pilot.classification import (
    ACADEMIC_TOP_CATEGORY,
    ACADEMIC_TYPES,
    LogisticFitConfig,
    MultinomialLogisticModel,
    fit_multinomial_logistic,
    load_academic_type_profiles,
    personal_similarity_features,
)
from sort_pilot.sandbox import SandboxViolationError


def test_academic_type_profiles_match_user_approved_phase_one_hierarchy():
    profiles = load_academic_type_profiles()

    assert ACADEMIC_TOP_CATEGORY == "학업"
    assert ACADEMIC_TYPES == ("교재", "문제지", "정답지")
    assert tuple(profile.label for profile in profiles) == ACADEMIC_TYPES
    assert all(profile.version == "1" for profile in profiles)


def test_numpy_multinomial_logistic_learns_three_separable_classes():
    features = np.asarray(
        [
            [3.0, 0.0],
            [2.5, 0.2],
            [0.0, 3.0],
            [0.2, 2.5],
            [-3.0, -3.0],
            [-2.5, -2.8],
        ]
    )
    targets = ("국어", "국어", "수학", "수학", "영어", "영어")

    model, report = fit_multinomial_logistic(
        features,
        targets,
        ("x", "y"),
        labels=("국어", "수학", "영어"),
        config=LogisticFitConfig(l2=0.01, max_epochs=1_500),
    )

    assert model.predict(features) == targets
    assert np.allclose(model.predict_proba(features).sum(axis=1), 1.0)
    assert report.final_loss > 0
    assert report.epochs <= 1_500


def test_logistic_artifact_round_trip_stays_inside_explicit_sandbox(tmp_path: Path):
    features = np.asarray([[2.0], [1.0], [-1.0], [-2.0]])
    model, _report = fit_multinomial_logistic(
        features,
        ("교재", "교재", "문제지", "문제지"),
        ("signal",),
        labels=("교재", "문제지"),
        config=LogisticFitConfig(l2=0.01, max_epochs=800),
    )
    path = tmp_path / "state" / "model.npz"

    model.save(path, tmp_path)
    loaded = MultinomialLogisticModel.load(path, tmp_path)

    assert loaded.labels == model.labels
    assert loaded.feature_names == model.feature_names
    assert loaded.predict(features) == model.predict(features)
    with pytest.raises(SandboxViolationError):
        model.save(tmp_path.parent / "escaped.npz", tmp_path)


def test_personal_similarity_excludes_the_training_row_itself():
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.0, 1.0],
        ]
    )
    targets = ("국어", "국어", "수학")

    values = personal_similarity_features(
        embeddings,
        embeddings,
        targets,
        ("국어", "수학"),
        query_reference_indices=(0, 1, 2),
    )

    assert values[0, 0] == pytest.approx(0.8)
    assert values[1, 0] == pytest.approx(0.8)
    assert values[2, 1] == -1.0
    assert np.all(values <= 1.0)
