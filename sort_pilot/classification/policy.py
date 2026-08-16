from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .result import AxisDecision


class PolicyRoute(str, Enum):
    """Next authority selected for one independently scored axis."""

    ACCEPT_LOCAL = "accept_local"
    GEMMA_FALLBACK = "gemma_fallback"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class RoutingThresholds:
    """Provisional raw-score and margin gates for one classifier axis."""

    high_score: float
    high_margin: float
    gemma_score: float

    def __post_init__(self) -> None:
        """Require finite, ordered thresholds without calling them probabilities."""
        values = (self.high_score, self.high_margin, self.gemma_score)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("분류 정책 임계값은 유한해야 합니다.")
        if self.gemma_score > self.high_score or self.high_margin < 0:
            raise ValueError("분류 정책 임계값의 순서가 올바르지 않습니다.")


@dataclass(frozen=True, slots=True)
class AxisRoutingDecision:
    """Observable policy outcome retaining the local evidence it routed."""

    route: PolicyRoute
    local_decision: AxisDecision
    policy_version: str
    reason: str


def route_axis(
    decision: AxisDecision,
    thresholds: RoutingThresholds,
    policy_version: str,
) -> AxisRoutingDecision:
    """Route one axis without allowing fallback to override a strong local result."""
    if decision.needs_review:
        return AxisRoutingDecision(
            PolicyRoute.NEEDS_REVIEW,
            decision,
            policy_version,
            "local classifier explicitly abstained",
        )
    if decision.score >= thresholds.high_score and decision.margin >= thresholds.high_margin:
        return AxisRoutingDecision(
            PolicyRoute.ACCEPT_LOCAL,
            decision,
            policy_version,
            "raw score and top-two margin cleared local-authority gates",
        )
    if decision.score >= thresholds.gemma_score:
        return AxisRoutingDecision(
            PolicyRoute.GEMMA_FALLBACK,
            decision,
            policy_version,
            "local evidence was plausible but not decisive",
        )
    return AxisRoutingDecision(
        PolicyRoute.NEEDS_REVIEW,
        decision,
        policy_version,
        "local evidence was insufficient for a bounded fallback",
    )
