"""Labeled synthetic corpus and metrics for the student classifier."""

from .corpus import (
    CorpusCase,
    Prediction,
    load_corpus,
    load_predictions,
)
from .metrics import EvaluationReport, evaluate_predictions

__all__ = [
    "CorpusCase",
    "EvaluationReport",
    "Prediction",
    "evaluate_predictions",
    "load_corpus",
    "load_predictions",
]
