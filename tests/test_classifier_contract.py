from __future__ import annotations

from pathlib import Path

from sort_pilot.classifier_engine import ClassifierEngine
from sort_pilot.classifier_engine.config import Config


def engine(tmp_path: Path) -> ClassifierEngine:
    """Create one isolated extraction-only analyzer."""
    return ClassifierEngine(Config(), tmp_path / "analyzer")


def test_analyze_record_extracts_terms_without_decision_storage(tmp_path: Path) -> None:
    path = tmp_path / "운영체제과제.txt"
    path.write_text("운영체제 프로세스 스케줄링 강의", encoding="utf-8")
    analyzer = engine(tmp_path)

    record = analyzer.analyze_record(path)

    assert record.family == "문서"
    assert record.terms
    assert not record.content_extraction_failed
    assert not (tmp_path / "analyzer" / "state.db").exists()


def test_public_json_contract_keeps_order_and_fallback_family(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    image = tmp_path / "photo.jpg"
    document.write_text("local content", encoding="utf-8")
    image.write_bytes(b"not-a-real-image")
    analyzer = engine(tmp_path)

    assert analyzer.analyze_json(document) == {
        "filepath": document.resolve().as_posix(),
        "folder": "문서/미분류",
    }
    assert analyzer.analyze_many_json([document, image]) == {
        "results": [
            {"filepath": document.resolve().as_posix(), "folder": "문서/미분류"},
            {"filepath": image.resolve().as_posix(), "folder": "이미지/미분류"},
        ]
    }


def test_invalid_supported_content_is_marked_for_manual_review(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not-a-real-pdf")
    analyzer = engine(tmp_path)

    record = analyzer.analyze_record(path)

    assert record.terms == {}
    assert record.content_extraction_failed
