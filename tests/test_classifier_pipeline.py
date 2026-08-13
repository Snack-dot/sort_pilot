from pathlib import Path
from unittest.mock import patch

import numpy as np

from sort_pilot.classifier_engine.actions import Executor, collision_free
from sort_pilot.classifier_engine.extract import extract, normalize_filename, tokenize
from sort_pilot.classifier_engine.learning import feedback
from sort_pilot.classifier_engine.model import NaiveBayesModel
from sort_pilot.classifier_engine.store import Store
from sort_pilot.classifier_engine.types import Feature, FeatureVector
from sort_pilot.classifier_engine.vision import derived, postprocess
from sort_pilot.classifier_engine import extract as extract_module


def test_filename_and_korean_normalization():
    assert normalize_filename(Path("KakaoTalk_20260809_123456.jpg")) == ["kakaotalk"]
    assert tokenize("회의록에서 회의록을") == ["회의록", "회의록"]


def test_model_feedback_and_scoring(tmp_path):
    model = NaiveBayesModel(tmp_path / "model.json")
    vector = FeatureVector("x", "x.pdf", 1, [Feature("invoice", "body", 3)])
    feedback(model, vector, "Finance")
    decision = model.score(vector, ["Finance", "School"], {"body": 1}, .1, .01, 1)
    assert decision.category == "Finance"
    assert decision.explanation


def test_atomic_model_roundtrip(tmp_path):
    model = NaiveBayesModel(tmp_path / "model.json")
    model.apply([("과제", "School", 8)])
    model.save()
    assert NaiveBayesModel(tmp_path / "model.json").tokens["과제"]["School"] == 8


def test_dry_run_and_collision(tmp_path):
    source = tmp_path / "invoice.pdf"
    source.write_text("invoice")
    store = Store(tmp_path / "state.db")
    executor = Executor(store, dry_run=True)
    destination = executor.execute(source, tmp_path / "sorted", "Finance")
    assert source.exists() and not destination.exists()
    destination.parent.mkdir(parents=True)
    destination.write_text("old")
    assert collision_free(destination).name == "invoice (2).pdf"
    store.close()


def test_text_extraction(tmp_path):
    path = tmp_path / "회의록.txt"
    path.write_text("meeting agenda 회의록을", encoding="utf-8")
    vector = extract(path)
    assert {feature.t for feature in vector.features} >= {"회의록", "meeting", "agenda", "txt"}


def test_vision_postprocess_and_derived():
    output = np.zeros((1, 84, 2), dtype=np.float32)
    output[0, :4, 0] = [320, 320, 200, 200]
    output[0, 4, 0] = .9
    output[0, :4, 1] = [100, 100, 50, 50]
    output[0, 4 + 63, 1] = .8
    detections = postprocess(output)
    tokens = {feature.t for feature in derived(detections)}
    assert {"obj:person", "obj:laptop", "pair:laptop+person", "n_person:1"} <= tokens


def test_rapidocr_engine_is_reused_within_worker_thread():
    created = []

    class FakeRapidOCR:
        def __init__(self):
            created.append(self)

    extract_module._OCR_LOCAL = __import__("threading").local()
    with patch("rapidocr.RapidOCR", FakeRapidOCR):
        first = extract_module._ocr_engine()
        second = extract_module._ocr_engine()

    assert first is second
    assert len(created) == 1
