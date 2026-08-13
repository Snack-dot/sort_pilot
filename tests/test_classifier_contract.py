from __future__ import annotations

from pathlib import Path

from sort_pilot.classifier_engine import ClassifierEngine
from sort_pilot.classifier_engine.config import Config
from sort_pilot.classifier_engine.learning import feedback
from sort_pilot.classifier_engine.pipeline import Pipeline
from sort_pilot.classifier_engine.topics import TopicProfileStore
from sort_pilot.classifier_engine.types import Feature, FeatureVector


def engine(tmp_path: Path, **config_values) -> ClassifierEngine:
    """Create an isolated real pipeline and empty user profile store."""
    config = Config(destination_root=str(tmp_path / "sorted"), **config_values)
    pipeline = Pipeline(config=config, root=tmp_path / "engine")
    profiles = TopicProfileStore(tmp_path / "profiles.json")
    return ClassifierEngine(pipeline=pipeline, profile_store=profiles)


def test_real_engine_decision_is_persisted_without_automatic_topic(tmp_path: Path) -> None:
    path = tmp_path / "운영체제과제.pdf"
    path.write_bytes(b"not-a-real-pdf")
    analyzer = engine(tmp_path)
    try:
        record = analyzer.analyze_record(path)
        assert record.engine_tier == "t2a"
        assert record.engine_action == "unsorted"
        assert record.decision_id is not None
        assert record.topic is None
        assert record.folder == "문서/미분류"
        assert analyzer.analyze_json(path) == {
            "filepath": path.resolve().as_posix(),
            "folder": "문서/미분류",
        }
    finally:
        analyzer.close()


def test_user_chosen_topics_drive_ordered_batch_json(tmp_path: Path) -> None:
    assignment = tmp_path / "assignment.pdf"
    receipt = tmp_path / "쿠팡영수증.png"
    assignment.write_bytes(b"assignment")
    receipt.write_bytes(b"not-a-real-image")
    analyzer = engine(tmp_path)
    analyzer.profile_store.upsert(
        analyzer.profile_store.new_profile("문서", "내과제", ["assignment"])
    )
    analyzer.profile_store.upsert(
        analyzer.profile_store.new_profile("이미지", "구매기록", ["영수증"])
    )
    try:
        result = analyzer.analyze_many_json([assignment, receipt])
        assert result == {
            "results": [
                {"filepath": assignment.resolve().as_posix(), "folder": "문서/내과제"},
                {"filepath": receipt.resolve().as_posix(), "folder": "이미지/구매기록"},
            ]
        }
    finally:
        analyzer.close()


def test_learned_engine_category_remains_evidence_until_user_maps_topic(tmp_path: Path) -> None:
    path = tmp_path / "quantum_notes.txt"
    path.write_text("quantum research", encoding="utf-8")
    analyzer = engine(tmp_path, theta_auto=-1.0, theta_suggest=-1.0, min_evidence=1.0)
    try:
        feedback(
            analyzer.pipeline.model,
            FeatureVector("train-1", "train-1", 1, [Feature("quantum", "filename", 4)]),
            "ResearchSignal",
        )
        feedback(
            analyzer.pipeline.model,
            FeatureVector("train-2", "train-2", 1, [Feature("holiday", "filename", 4)]),
            "TravelSignal",
        )
        record = analyzer.analyze_record(path)
        assert record.engine_tier == "t2a"
        assert record.engine_category == "ResearchSignal"
        assert record.engine_action == "auto"
        assert record.folder == "문서/미분류"

        analyzer.profile_store.upsert(
            analyzer.profile_store.new_profile("문서", "양자연구", ["quantum"])
        )
        assert analyzer.analyze(path).folder == "문서/양자연구"
    finally:
        analyzer.close()
