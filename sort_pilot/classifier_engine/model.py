from __future__ import annotations

import json
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from .types import Decision, FeatureVector


class NaiveBayesModel:
    """Persisted multinomial Naive Bayes model for local folder classification."""

    def __init__(self, path: Path, alpha: float = 0.3):
        """Initialize model state and load persisted weights when present."""
        self.path = path
        self.alpha = alpha
        self.categories: dict[str, dict[str, float]] = {}
        self.tokens: dict[str, dict[str, float]] = {}
        self.load()

    def load(self) -> None:
        """Load categories, token weights, and smoothing parameters."""
        if not self.path.exists(): return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.categories, self.tokens = data.get("categories", {}), data.get("tokens", {})
        self.alpha = data.get("params", {}).get("alpha", self.alpha)

    def save(self) -> None:
        """Persist model state using fsync and atomic replacement."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 3, "categories": self.categories, "tokens": self.tokens, "params": {"alpha": self.alpha}}
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix="model-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, indent=2); out.flush(); os.fsync(out.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    def apply(self, deltas: list[tuple[str, str, float]]) -> None:
        """Apply bounded token-weight changes to category totals."""
        for token, category, delta in deltas:
            bucket = self.tokens.setdefault(token, {})
            before = bucket.get(category, 0.0)
            bucket[category] = max(0.0, before + delta)
            meta = self.categories.setdefault(category, {"docs": 0.0, "total": 0.0})
            meta["total"] = max(0.0, meta.get("total", 0.0) + bucket[category] - before)

    def score(self, vector: FeatureVector, candidates: list[str], weights: dict[str, float], theta_auto=.55, theta_suggest=.15, min_evidence=3.0) -> Decision:
        """Score candidate categories and return a gated, explained decision."""
        candidates = candidates or sorted(self.categories)
        if not candidates:
            return Decision(None, 0, 0, 0, "unsorted", "t2a")
        vocab = max(len(self.tokens), 1); total_docs = sum(v.get("docs", 0) for v in self.categories.values())
        scores = {}; contributions = defaultdict(dict); n_eff = 0.0
        for category in candidates:
            docs = self.categories.get(category, {}).get("docs", 0)
            score = math.log((docs + self.alpha) / (total_docs + self.alpha * len(candidates)))
            denom = self.categories.get(category, {}).get("total", 0) + self.alpha * vocab
            for feature in vector.features:
                if feature.t not in self.tokens: continue
                weight = weights.get(feature.src, 1.0) * feature.n; n_eff += weight / len(candidates)
                term = weight * math.log((self.tokens[feature.t].get(category, 0) + self.alpha) / denom)
                score += term; contributions[feature.t][category] = term
            scores[category] = score
        ranked = sorted(scores, key=scores.get, reverse=True); top = ranked[0]; runner = ranked[1] if len(ranked) > 1 else top
        margin = (scores[top] - scores[runner]) / max(n_eff, 1)
        action = "auto" if n_eff >= min_evidence and margin >= theta_auto else "suggest" if n_eff >= min_evidence and margin >= theta_suggest else "unsorted"
        explanation = sorted(({"feature": t, "contribution": vals.get(top, 0)-vals.get(runner, 0)} for t, vals in contributions.items()), key=lambda x: abs(x["contribution"]), reverse=True)[:8]
        return Decision(top, scores[top], margin, n_eff, action, "t2a", explanation)
