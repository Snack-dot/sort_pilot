from __future__ import annotations

import random
from pathlib import Path

from .extract import extract


def feedback(model, vector, chosen: str, predicted: str | None = None, demote=.5):
    deltas = []
    for feature in vector.features:
        deltas.append((feature.t, chosen, feature.n))
        if predicted and predicted != chosen: deltas.append((feature.t, predicted, -feature.n * demote))
    model.categories.setdefault(chosen, {"docs": 0, "total": 0})["docs"] += 1
    model.apply(deltas); model.save(); return deltas


def bootstrap(model, root: Path, limit=200) -> dict[str, int]:
    counts = {}
    for category in (p for p in root.iterdir() if p.is_dir()):
        files = [p for p in category.rglob("*") if p.is_file()]; random.Random(0).shuffle(files)
        for path in files[:limit]: feedback(model, extract(path), category.name)
        counts[category.name] = min(len(files), limit)
    return counts


def calibrate(history: list[tuple[float, bool]], floor=.97, default=.55) -> float:
    if len(history) < 50: return default
    for threshold in sorted({margin for margin, _ in history}):
        chosen = [ok for margin, ok in history if margin >= threshold]
        if chosen and sum(chosen) / len(chosen) >= floor: return threshold
    return max(margin for margin, _ in history)

