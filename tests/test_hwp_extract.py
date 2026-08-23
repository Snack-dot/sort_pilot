from __future__ import annotations

import struct
import zipfile
from pathlib import Path

from sort_pilot.classifier_engine.extract import (
    _decode_hwp_para_text,
    _hwp_records,
    extract,
    supports_content_analysis,
)


def test_hwp_and_hwpx_are_content_analyzable():
    assert supports_content_analysis(Path("document.hwp"))
    assert supports_content_analysis(Path("document.hwpx"))


def test_hwp_record_reader_handles_extended_payload_size():
    payload = "확률과 통계".encode("utf-16le")
    header = 67 | (0xFFF << 20)
    data = struct.pack("<II", header, len(payload)) + payload

    assert list(_hwp_records(data)) == [(67, payload)]


def test_hwp_para_text_drops_extended_controls_and_retains_display_text():
    control = struct.pack("<H", 2) + b"\x00" * 14
    payload = "수학".encode("utf-16le") + control + "문제".encode("utf-16le")

    assert _decode_hwp_para_text(payload) == "수학문제"


def test_hwpx_text_reaches_the_normal_feature_pipeline(tmp_path: Path):
    path = tmp_path / "수학자료.hwpx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "Contents/section0.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hs:sec xmlns:hs="urn:hancom:section" xmlns:hp="urn:hancom:paragraph">'
            '<hp:p><hp:run><hp:t>확률과 통계 문제의 정답과 풀이 과정</hp:t></hp:run></hp:p>'
            "</hs:sec>",
        )

    vector = extract(path)

    assert vector.partial is False
    assert "확률과 통계" in vector.natural_text
    assert any(feature.src == "body" for feature in vector.features)


def test_hwp_extractor_failure_is_bounded_as_partial(tmp_path: Path):
    path = tmp_path / "locked.hwp"
    path.write_bytes(b"not-an-ole-hwp")

    vector = extract(path)

    assert vector.partial is True
    assert vector.natural_text == ""
