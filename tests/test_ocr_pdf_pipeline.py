from __future__ import annotations

import threading
import sys
from types import SimpleNamespace

import pytest

from sort_pilot.classifier_engine import extract as extract_module
from sort_pilot.classifier_engine.extract import Feature, _pdf, _pdf_page_indices, extract


def _ocr_result(text: str, confidence: float):
    return SimpleNamespace(txts=(text,), boxes=None, scores=(confidence,))


def test_long_pdf_sampling_is_first_three_middle_and_last():
    assert _pdf_page_indices(5) == (0, 1, 2, 3, 4)
    assert _pdf_page_indices(6) == (0, 1, 2, 3, 5)
    assert _pdf_page_indices(11) == (0, 1, 2, 5, 10)


def test_600_page_pdf_loads_only_five_selected_pages(monkeypatch, tmp_path):
    class Rect:
        width = 600
        height = 800

    class Page:
        rect = Rect()

        def get_text(self, _kind):
            return "normal native document text " * 6

        def get_image_info(self, **_kwargs):
            return []

    class Document:
        page_count = 600
        metadata = {}

        def __init__(self):
            self.loaded = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def load_page(self, index):
            self.loaded.append(index)
            return Page()

    document = Document()
    monkeypatch.setitem(sys.modules, "pymupdf", SimpleNamespace(open=lambda _path: document))
    extract_module._PDF_CACHE_LOCAL = threading.local()
    path = tmp_path / "large.pdf"
    path.write_bytes(b"fake")

    result = _pdf(path, 20_000)

    assert document.loaded == [0, 1, 2, 300, 599]
    assert result.numeric_features["pdf_page_count"] == 600.0
    assert result.numeric_features["pdf_sampled_page_count"] == 5.0


def test_pdf_cache_uses_path_size_and_mtime_without_reextracting(monkeypatch, tmp_path):
    path = tmp_path / "cached.pdf"
    path.write_bytes(b"one")
    calls = []
    sentinel = object()

    def fake_extract(value, limit):
        calls.append((value, limit))
        return sentinel

    extract_module._PDF_CACHE_LOCAL = threading.local()
    monkeypatch.setattr(extract_module, "_extract_pdf_pages", fake_extract)

    assert extract_module._pdf(path, 20_000) is sentinel
    assert extract_module._pdf(path, 20_000) is sentinel
    assert len(calls) == 1

    path.write_bytes(b"different-size")
    assert extract_module._pdf(path, 20_000) is sentinel
    assert len(calls) == 2


def test_pdf_uses_good_embedded_text_without_ocr(monkeypatch, tmp_path):
    import pymupdf

    path = tmp_path / "text.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((40, 70), "normal embedded text " * 10)
    document.set_metadata({"title": "Korean algebra guide", "author": "Teacher"})
    document.save(path)
    document.close()
    monkeypatch.setattr(
        extract_module,
        "_ocr_pdf_page",
        lambda *_args: (_ for _ in ()).throw(AssertionError("OCR must not run")),
    )

    result = _pdf(path, 20_000)

    assert "normal embedded text" in result.text
    assert result.numeric_features["pdf_page_count"] == 1.0
    assert result.numeric_features["pdf_scan_ratio"] == 0.0
    assert result.quality == "ok"
    assert {feature.src for feature in result.metadata_features} == {"pdf_meta"}


def test_pdf_runs_at_most_one_scan_page_at_150_dpi(monkeypatch, tmp_path):
    import pymupdf

    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    for _ in range(5):
        document.new_page().insert_text((40, 70), "tiny")
    document.save(path)
    document.close()
    calls = []

    def fake_ocr(_page, dpi):
        calls.append(dpi)
        return _ocr_result("한국어 스캔 문서", 0.91), 0.91

    monkeypatch.setattr(extract_module, "_ocr_pdf_page", fake_ocr)

    result = _pdf(path, 20_000)

    assert calls == [150]
    assert "한국어 스캔 문서" in result.text
    assert result.numeric_features["pdf_scan_ratio"] == 1.0
    assert result.ocr_confidence == pytest.approx(0.91)
    assert result.quality == "ok"


def test_pdf_timeout_marks_quality_without_trying_another_page(monkeypatch, tmp_path):
    import pymupdf

    path = tmp_path / "timeout.pdf"
    document = pymupdf.open()
    for _ in range(5):
        document.new_page()
    document.save(path)
    document.close()
    calls = []

    def timed_out(_page, dpi):
        calls.append(dpi)
        raise TimeoutError

    monkeypatch.setattr(extract_module, "_ocr_pdf_page", timed_out)

    result = _pdf(path, 20_000)

    assert calls == [150]
    assert result.quality == "failed"
    assert result.numeric_features["pdf_scan_ratio"] == 1.0


@pytest.mark.parametrize("suffix,format_name", [
    (".jpg", "JPEG"),
    (".png", "PNG"),
    (".bmp", "BMP"),
    (".webp", "WEBP"),
    (".tiff", "TIFF"),
])
def test_all_required_image_formats_run_ocr(monkeypatch, tmp_path, suffix, format_name):
    from PIL import Image

    path = tmp_path / f"made-up{suffix}"
    Image.new("RGB", (160, 90), "white").save(path, format=format_name)
    calls = []

    def fake_ocr(value):
        calls.append(value)
        extract_module._OCR_LOCAL.last_text = "한국어 촬영 문서"
        extract_module._OCR_LOCAL.last_template_text = "한국어 촬영 문서"
        extract_module._OCR_LOCAL.last_layout_evidence = ("한국어 촬영 문서",)
        extract_module._OCR_LOCAL.last_confidence = 0.95
        return [Feature("한국어", "ocr")]

    extract_module._OCR_LOCAL = threading.local()
    monkeypatch.setattr(extract_module, "_ocr", fake_ocr)

    vector = extract(path)

    assert calls == [path]
    assert vector.natural_text == "한국어 촬영 문서"
    assert vector.extraction_quality == "ok"
    assert vector.ocr_confidence == pytest.approx(0.95)


def test_exif_photo_is_not_skipped_by_ocr(monkeypatch, tmp_path):
    from PIL import Image

    path = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[271] = "Made-up Camera"
    Image.new("RGB", (120, 180), "white").save(path, exif=exif)

    def fake_ocr(_value):
        extract_module._OCR_LOCAL.last_text = "칠판 수학 문제"
        extract_module._OCR_LOCAL.last_template_text = "칠판 수학 문제"
        extract_module._OCR_LOCAL.last_layout_evidence = ()
        extract_module._OCR_LOCAL.last_confidence = 0.9
        return [Feature("수학", "ocr")]

    extract_module._OCR_LOCAL = threading.local()
    monkeypatch.setattr(extract_module, "_ocr", fake_ocr)

    vector = extract(path)

    assert vector.route == "photo"
    assert vector.natural_text == "칠판 수학 문제"
    assert any(feature.t == "exif:camera_present" for feature in vector.features)


def test_low_image_ocr_confidence_marks_review_quality(monkeypatch, tmp_path):
    from PIL import Image

    path = tmp_path / "weak.png"
    Image.new("RGB", (100, 100), "white").save(path)

    def fake_ocr(_value):
        extract_module._OCR_LOCAL.last_text = "희미한 글자"
        extract_module._OCR_LOCAL.last_template_text = "희미한 글자"
        extract_module._OCR_LOCAL.last_layout_evidence = ()
        extract_module._OCR_LOCAL.last_confidence = 0.3
        return [Feature("희미", "ocr")]

    extract_module._OCR_LOCAL = threading.local()
    monkeypatch.setattr(extract_module, "_ocr", fake_ocr)

    vector = extract(path)

    assert vector.extraction_quality == "low_confidence"
    assert vector.ocr_confidence == pytest.approx(0.3)
    serialized = vector.to_dict()
    assert "희미한 글자" not in str(serialized)
    assert serialized["extraction_quality"] == "low_confidence"
