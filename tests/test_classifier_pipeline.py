from pathlib import Path
from unittest.mock import patch
import zipfile

import numpy as np

from sort_pilot.classifier_engine.actions import Executor, collision_free
from sort_pilot.classifier_engine.config import Config
from sort_pilot.classifier_engine.extract import extract, normalize_filename, tokenize
from sort_pilot.classifier_engine.learning import feedback
from sort_pilot.classifier_engine.model import NaiveBayesModel
from sort_pilot.classifier_engine.pipeline import Pipeline
from sort_pilot.classifier_engine.store import Store
from sort_pilot.classifier_engine.tier1 import DEFAULT_RULES, evaluate
from sort_pilot.classifier_engine.topics import vector_terms
from sort_pilot.classifier_engine.types import Feature, FeatureVector
from sort_pilot.classifier_engine.vision import derived, postprocess
from sort_pilot.classifier_engine import extract as extract_module


def test_filename_and_korean_normalization():
    assert normalize_filename(Path("KakaoTalk_20260809_123456.jpg")) == ["kakaotalk"]
    assert tokenize("회의록에서 회의록을") == ["회의록", "회의록"]


def test_model_feedback_and_scoring(tmp_path):
    model = NaiveBayesModel(tmp_path / "model.json")
    vector = FeatureVector("x", "x.pdf", 1, [Feature("invoice", "body", 3)])
    feedback(model, vector, "PurchaseSignal")
    decision = model.score(vector, ["PurchaseSignal", "ResearchSignal"], {"body": 1}, .1, .01, 1)
    assert decision.category == "PurchaseSignal"
    assert decision.explanation


def test_atomic_model_roundtrip(tmp_path):
    model = NaiveBayesModel(tmp_path / "model.json")
    model.apply([("과제", "UserSignal", 8)])
    model.save()
    assert NaiveBayesModel(tmp_path / "model.json").tokens["과제"]["UserSignal"] == 8


def test_default_topic_patterns_are_evidence_marks_not_categories():
    decision, marks = evaluate(Path("assignment.pdf"), DEFAULT_RULES)
    assert decision is None
    assert {mark.t for mark in marks} == {"topic_hint:coursework"}


def test_pipeline_loads_persisted_engine_config(tmp_path):
    root = tmp_path / "engine"
    expected = Config(theta_auto=0.91, destination_root=str(tmp_path / "dest"))
    expected.save(root / "config.json")
    pipeline = Pipeline(root=root)
    try:
        assert pipeline.config.theta_auto == 0.91
        assert pipeline.config.destination_root == str(tmp_path / "dest")
    finally:
        pipeline.close()


def test_dry_run_and_collision(tmp_path):
    source = tmp_path / "invoice.pdf"
    source.write_text("invoice")
    store = Store(tmp_path / "state.db")
    executor = Executor(store, dry_run=True)
    destination = executor.execute(source, tmp_path / "sorted", "UserChosen")
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


def test_topic_terms_use_content_and_never_filename_or_metadata():
    vector = FeatureVector(
        "x",
        "misleading-invoice-name.txt",
        1,
        [
            Feature("invoice", "filename", 9),
            Feature("txt", "ext", 9),
            Feature("quantum", "body", 3),
            Feature("telescope", "ocr", 2),
            Feature("obj:laptop", "obj", 1),
        ],
    )

    assert vector_terms(vector, {"filename": 3, "body": 1, "ocr": 0.6, "obj": 0.8}) == {
        "quantum": 3.0,
        "telescope": 1.2,
        "obj:laptop": 0.8,
    }


def test_text_extraction_preserves_a_large_body_vocabulary(tmp_path):
    path = tmp_path / "rich-context.txt"
    expected = {
        f"contextword{chr(97 + first)}{chr(97 + second)}"
        for first in range(5)
        for second in range(24)
    }
    path.write_text(" ".join(sorted(expected)), encoding="utf-8")

    vector = extract(path)
    body = {feature.t for feature in vector.features if feature.src == "body"}

    assert expected <= body


def test_odt_extraction_reads_the_actual_content_payload(tmp_path):
    path = tmp_path / "project.odt"
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <office:document-content
      xmlns:office='urn:oasis:names:tc:opendocument:xmlns:office:1.0'
      xmlns:text='urn:oasis:names:tc:opendocument:xmlns:text:1.0'>
      <office:body><office:text><text:p>nebula roadmap milestone context</text:p></office:text></office:body>
    </office:document-content>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.xml", xml)

    vector = extract(path)
    body = {feature.t for feature in vector.features if feature.src == "body"}

    assert {"nebula", "roadmap", "milestone", "context"} <= body


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
