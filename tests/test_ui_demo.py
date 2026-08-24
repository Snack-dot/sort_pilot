from __future__ import annotations

import sys

import ui_demo
from sort_pilot.curriculum import Semester, StudentType, default_profile
from sort_pilot.educational_preview import build_preview_groups
from sort_pilot.simple_classifier import classify_for_ui_test


def test_ui_demo_builds_four_sample_groups_without_ai_runtime_imports() -> None:
    assert "onnxruntime" not in sys.modules
    assert "fastembed" not in sys.modules

    outputs = classify_for_ui_test(
        ui_demo.sample_inputs(),
        default_profile(StudentType.MIDDLE, 1, Semester.FIRST),
    )
    groups = build_preview_groups(outputs)

    assert len(outputs) == 28
    assert sorted(group.count for group in groups) == [3, 5, 8, 12]
    assert groups[-1].title == "확인이 필요한 파일"
    assert groups[-1].count == 3
