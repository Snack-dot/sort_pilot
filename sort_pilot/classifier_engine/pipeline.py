from __future__ import annotations

from pathlib import Path

from .config import Config, data_dir
from .extract import extract, is_processable
from .model import NaiveBayesModel
from .store import Store
from .tier1 import evaluate, load_rules
from .types import Decision, Tier3Stub


class Pipeline:
    """Orchestrate local extraction, tiered classification, and decision logging."""

    def __init__(self, config: Config | None = None, root: Path | None = None):
        """Load configuration, state storage, model weights, and tier-three stub."""
        self.config = config or Config()
        self.root = root or data_dir()
        self.store = Store(self.root / "state.db")
        self.model = NaiveBayesModel(self.root / "classifier_weights.json")
        self.tier3 = Tier3Stub()

    def categories(self) -> list[str]:
        """Return destination folders and learned model categories."""
        root = Path(self.config.destination_root)
        disk = [p.name for p in root.iterdir() if p.is_dir()] if root.exists() else []
        return sorted(set(disk) | set(self.model.categories))

    def extract_vector(self, path: Path):
        """Extract one feature vector without making a legacy flat-category decision."""
        if not is_processable(path, self.config.exclusions):
            raise ValueError(f"Excluded or incomplete file: {path}")
        return extract(path, self.config.max_content_mb)

    def classify(self, path: Path) -> tuple[object, Decision, int]:
        """Classify a processable path and persist its decision."""
        if not is_processable(path, self.config.exclusions):
            raise ValueError(f"Excluded or incomplete file: {path}")
        tier1, marks = evaluate(path, load_rules(self.root / "rules.json"))
        vector = extract(path, self.config.max_content_mb)
        vector.features.extend(marks)
        decision = tier1 or self.model.score(vector, self.categories(), self.config.source_weights,
            self.config.theta_auto, self.config.theta_suggest, self.config.min_evidence)
        if decision.action == "unsorted" and self.config.tier3_enabled:
            decision = self.tier3.classify(vector, self.categories()) or decision
        decision_id = self.store.record_decision(vector, decision)
        return vector, decision, decision_id

    def safe_classify(self, path: Path):
        """Return an unsorted decision instead of propagating extraction failures."""
        try: return self.classify(path)
        except Exception:
            from .types import FeatureVector, path_id
            stat = path.stat()
            vector = FeatureVector(path_id(path), str(path), stat.st_size, partial=True)
            decision = Decision(None, 0, 0, 0, "unsorted", "error")
            return vector, decision, self.store.record_decision(vector, decision)

    def close(self) -> None:
        """Close the pipeline's worker-local SQLite connection."""
        self.store.close()
