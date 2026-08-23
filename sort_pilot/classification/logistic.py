from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from sort_pilot.sandbox import require_in_sandbox


LOGISTIC_MODEL_VERSION = "academic-logistic-v1"


@dataclass(frozen=True, slots=True)
class LogisticFitConfig:
    """Deterministic optimizer settings for one multinomial model."""

    l2: float = 0.1
    learning_rate: float = 0.03
    max_epochs: int = 2_000
    tolerance: float = 1e-7
    patience: int = 30
    balanced_classes: bool = True

    def __post_init__(self) -> None:
        for value, name, allow_zero in (
            (self.l2, "l2", True),
            (self.learning_rate, "learning_rate", False),
            (self.tolerance, "tolerance", False),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or (not allow_zero and value == 0)
            ):
                raise ValueError(f"{name} must be a valid finite value.")
        if type(self.max_epochs) is not int or self.max_epochs < 1:
            raise ValueError("max_epochs must be a positive integer.")
        if type(self.patience) is not int or self.patience < 1:
            raise ValueError("patience must be a positive integer.")
        if type(self.balanced_classes) is not bool:
            raise ValueError("balanced_classes must be bool.")


@dataclass(frozen=True, slots=True)
class LogisticFitReport:
    """Observable optimizer outcome without retaining private examples."""

    epochs: int
    final_loss: float
    converged: bool


@dataclass(frozen=True, slots=True)
class MultinomialLogisticModel:
    """Small NumPy multinomial logistic model with an inspectable feature schema."""

    labels: tuple[str, ...]
    feature_names: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray
    intercept: np.ndarray
    version: str = LOGISTIC_MODEL_VERSION

    def __post_init__(self) -> None:
        if self.version != LOGISTIC_MODEL_VERSION:
            raise ValueError("Unsupported logistic model version.")
        if len(self.labels) < 2 or len(self.labels) != len(set(self.labels)):
            raise ValueError("A logistic model needs at least two unique labels.")
        if not all(isinstance(value, str) and value.strip() for value in self.labels):
            raise ValueError("Logistic labels must be non-empty strings.")
        if not self.feature_names or len(self.feature_names) != len(set(self.feature_names)):
            raise ValueError("Logistic feature names must be non-empty and unique.")
        if not all(
            isinstance(value, str) and value.strip() for value in self.feature_names
        ):
            raise ValueError("Logistic feature names must be non-empty strings.")

        feature_count = len(self.feature_names)
        label_count = len(self.labels)
        arrays = {
            "mean": np.asarray(self.mean, dtype=np.float64),
            "scale": np.asarray(self.scale, dtype=np.float64),
            "weights": np.asarray(self.weights, dtype=np.float64),
            "intercept": np.asarray(self.intercept, dtype=np.float64),
        }
        expected = {
            "mean": (feature_count,),
            "scale": (feature_count,),
            "weights": (label_count, feature_count),
            "intercept": (label_count,),
        }
        for name, value in arrays.items():
            if value.shape != expected[name] or not np.isfinite(value).all():
                raise ValueError(f"Invalid logistic {name} array.")
            if name == "scale" and np.any(value <= 0):
                raise ValueError("Logistic feature scales must be positive.")
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    def predict_proba(self, features: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
        """Return stable per-label softmax probabilities."""
        matrix = _feature_matrix(features, len(self.feature_names))
        normalized = (matrix - self.mean) / self.scale
        logits = normalized @ self.weights.T + self.intercept
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        return probabilities

    def predict(self, features: Sequence[Sequence[float]] | np.ndarray) -> tuple[str, ...]:
        """Return one configured label per row."""
        indices = np.argmax(self.predict_proba(features), axis=1)
        return tuple(self.labels[int(index)] for index in indices)

    def save(self, path: Path, sandbox_root: Path) -> None:
        """Atomically save model arrays and metadata inside the sandbox only."""
        target = require_in_sandbox(path, sandbox_root, label="logistic model")
        if target.suffix.casefold() != ".npz":
            raise ValueError("Logistic model path must end in .npz.")
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata_path = target.with_suffix(".json")
        metadata = {
            "version": self.version,
            "labels": list(self.labels),
            "feature_names": list(self.feature_names),
        }
        array_temp = _temporary_path(target.parent, target.stem, ".npz")
        metadata_temp = _temporary_path(target.parent, target.stem, ".json")
        try:
            with array_temp.open("wb") as stream:
                np.savez_compressed(
                    stream,
                    mean=self.mean,
                    scale=self.scale,
                    weights=self.weights,
                    intercept=self.intercept,
                )
                stream.flush()
                os.fsync(stream.fileno())
            metadata_temp.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(array_temp, target)
            os.replace(metadata_temp, metadata_path)
        finally:
            array_temp.unlink(missing_ok=True)
            metadata_temp.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path, sandbox_root: Path) -> "MultinomialLogisticModel":
        """Load a validated model only from the sandbox."""
        target = require_in_sandbox(path, sandbox_root, label="logistic model")
        metadata_path = require_in_sandbox(
            target.with_suffix(".json"), sandbox_root, label="logistic metadata"
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or set(metadata) != {
            "version",
            "labels",
            "feature_names",
        }:
            raise ValueError("Invalid logistic metadata document.")
        with np.load(target, allow_pickle=False) as values:
            if set(values.files) != {"mean", "scale", "weights", "intercept"}:
                raise ValueError("Invalid logistic array artifact.")
            return cls(
                labels=tuple(metadata["labels"]),
                feature_names=tuple(metadata["feature_names"]),
                mean=values["mean"],
                scale=values["scale"],
                weights=values["weights"],
                intercept=values["intercept"],
                version=metadata["version"],
            )


def fit_multinomial_logistic(
    features: Sequence[Sequence[float]] | np.ndarray,
    targets: Sequence[str],
    feature_names: Sequence[str],
    *,
    labels: Sequence[str] | None = None,
    config: LogisticFitConfig | None = None,
) -> tuple[MultinomialLogisticModel, LogisticFitReport]:
    """Fit one deterministic class-balanced softmax model with Adam."""
    names = tuple(feature_names)
    matrix = _feature_matrix(features, len(names))
    target_values = tuple(targets)
    if len(target_values) != len(matrix) or not target_values:
        raise ValueError("Targets must match the non-empty feature matrix.")
    ordered_labels = tuple(labels or dict.fromkeys(target_values))
    if len(ordered_labels) < 2 or len(ordered_labels) != len(set(ordered_labels)):
        raise ValueError("Training requires at least two unique labels.")
    if any(value not in ordered_labels for value in target_values):
        raise ValueError("A training target is outside the configured labels.")
    missing = [value for value in ordered_labels if value not in target_values]
    if missing:
        raise ValueError(f"Training data has no examples for labels: {missing}")

    settings = config or LogisticFitConfig()
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale[scale < 1e-12] = 1.0
    normalized = (matrix - mean) / scale
    index = {label: position for position, label in enumerate(ordered_labels)}
    target_index = np.asarray([index[value] for value in target_values], dtype=np.int64)
    one_hot = np.eye(len(ordered_labels), dtype=np.float64)[target_index]

    sample_weight = np.ones(len(matrix), dtype=np.float64)
    if settings.balanced_classes:
        counts = np.bincount(target_index, minlength=len(ordered_labels)).astype(np.float64)
        sample_weight = len(matrix) / (len(ordered_labels) * counts[target_index])
    sample_weight /= sample_weight.mean()
    weighted_one_hot = one_hot * sample_weight[:, None]

    weights = np.zeros((len(ordered_labels), len(names)), dtype=np.float64)
    intercept = np.zeros(len(ordered_labels), dtype=np.float64)
    moment_w = np.zeros_like(weights)
    velocity_w = np.zeros_like(weights)
    moment_b = np.zeros_like(intercept)
    velocity_b = np.zeros_like(intercept)
    beta1 = 0.9
    beta2 = 0.999
    epsilon = 1e-8
    previous_loss = math.inf
    stable_epochs = 0
    converged = False
    final_loss = math.inf

    for epoch in range(1, settings.max_epochs + 1):
        logits = normalized @ weights.T + intercept
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        residual = probabilities * sample_weight[:, None] - weighted_one_hot
        gradient_w = residual.T @ normalized / len(matrix) + settings.l2 * weights
        gradient_b = residual.mean(axis=0)

        moment_w = beta1 * moment_w + (1.0 - beta1) * gradient_w
        velocity_w = beta2 * velocity_w + (1.0 - beta2) * gradient_w**2
        moment_b = beta1 * moment_b + (1.0 - beta1) * gradient_b
        velocity_b = beta2 * velocity_b + (1.0 - beta2) * gradient_b**2
        correction1 = 1.0 - beta1**epoch
        correction2 = 1.0 - beta2**epoch
        weights -= settings.learning_rate * (moment_w / correction1) / (
            np.sqrt(velocity_w / correction2) + epsilon
        )
        intercept -= settings.learning_rate * (moment_b / correction1) / (
            np.sqrt(velocity_b / correction2) + epsilon
        )

        true_probabilities = probabilities[np.arange(len(matrix)), target_index]
        final_loss = float(
            -np.mean(sample_weight * np.log(np.clip(true_probabilities, 1e-15, 1.0)))
            + 0.5 * settings.l2 * np.sum(weights**2)
        )
        if abs(previous_loss - final_loss) <= settings.tolerance * max(1.0, abs(previous_loss)):
            stable_epochs += 1
            if stable_epochs >= settings.patience:
                converged = True
                break
        else:
            stable_epochs = 0
        previous_loss = final_loss

    model = MultinomialLogisticModel(
        labels=ordered_labels,
        feature_names=names,
        mean=mean,
        scale=scale,
        weights=weights,
        intercept=intercept,
    )
    return model, LogisticFitReport(epoch, final_loss, converged)


def _feature_matrix(
    values: Sequence[Sequence[float]] | np.ndarray,
    expected_features: int,
) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1:] != (expected_features,) or not len(matrix):
        raise ValueError(
            f"Feature matrix must have shape (n, {expected_features}) with n >= 1."
        )
    if not np.isfinite(matrix).all():
        raise ValueError("Logistic features must all be finite.")
    return matrix


def _temporary_path(parent: Path, prefix: str, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(dir=parent, prefix=f"{prefix}-", suffix=suffix)
    os.close(descriptor)
    return Path(name)
