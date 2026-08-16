"""Contracts shared by local classification, fallback policy, and preview."""

from .policy import AxisRoutingDecision, PolicyRoute, RoutingThresholds, route_axis
from .result import (
    Activity,
    AxisDecision,
    CandidateScore,
    DecisionSource,
    EducationalClassificationResult,
)
from .subject import SubjectClassifier, SubjectEvidence, SubjectProfile, eligible_subject_profiles

__all__ = [
    "Activity",
    "AxisRoutingDecision",
    "AxisDecision",
    "CandidateScore",
    "DecisionSource",
    "EducationalClassificationResult",
    "PolicyRoute",
    "RoutingThresholds",
    "SubjectClassifier",
    "SubjectEvidence",
    "SubjectProfile",
    "eligible_subject_profiles",
    "route_axis",
]
