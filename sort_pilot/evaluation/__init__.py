"""Labeled synthetic corpus and metrics for the student classifier."""

from .corpus import (
    CorpusCase,
    Prediction,
    load_corpus,
    load_predictions,
)
from .metrics import EvaluationReport, evaluate_predictions
from .phase8 import (
    MAXIMUM_P95_LATENCY_RATIO,
    MAXIMUM_PEAK_MEMORY_MB,
    MINIMUM_ACCURACY_GAIN,
    PHASE8_CORPUS_VERSION,
    SIGNIFICANCE_ALPHA,
    PairedAccuracy,
    Phase8Case,
    Phase8GateReport,
    ResourceMeasurement,
    load_phase8_corpus,
    paired_accuracy,
)

__all__ = [
    "CorpusCase",
    "EvaluationReport",
    "MAXIMUM_P95_LATENCY_RATIO",
    "MAXIMUM_PEAK_MEMORY_MB",
    "MINIMUM_ACCURACY_GAIN",
    "PHASE8_CORPUS_VERSION",
    "SIGNIFICANCE_ALPHA",
    "PairedAccuracy",
    "Phase8Case",
    "Phase8GateReport",
    "Prediction",
    "ResourceMeasurement",
    "evaluate_predictions",
    "load_corpus",
    "load_phase8_corpus",
    "load_predictions",
    "paired_accuracy",
]
