"""Contracts shared by local classification, fallback policy, and preview."""

from .policy import AxisRoutingDecision, PolicyRoute, RoutingThresholds, route_axis
from .result import (
    AxisDecision,
    CandidateScore,
    DecisionSource,
    EducationalClassificationResult,
    EvidenceContribution,
    OrganizationPlan,
    Template,
)
from .subject import SubjectClassifier, SubjectEvidence, SubjectProfile, eligible_subject_profiles

__all__ = [
    "AxisRoutingDecision",
    "AxisDecision",
    "CandidateScore",
    "DecisionSource",
    "EducationalClassificationResult",
    "EvidenceContribution",
    "OrganizationPlan",
    "PolicyRoute",
    "RoutingThresholds",
    "SubjectClassifier",
    "SubjectEvidence",
    "SubjectProfile",
    "Template",
    "eligible_subject_profiles",
    "route_axis",
]
