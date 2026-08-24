from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from sort_pilot.classification import EducationalClassificationInput
from sort_pilot.curriculum import Semester, StudentType, default_profile
from sort_pilot.educational_preview import EducationalPreviewDialog
from sort_pilot.simple_classifier import classify_for_ui_test


DEMO_ROOT = Path("C:/SortPilot-UI-Demo")


def _sample_input(path: Path, index: int) -> EducationalClassificationInput:
    """Build one path-only sample without reading or creating a real file."""
    fingerprint = hashlib.sha1(f"sort-pilot-ui-demo-{index}".encode()).hexdigest()
    return EducationalClassificationInput(
        source=path,
        fingerprint=fingerprint,
        file_name=path.name,
        natural_text="",
    )


def sample_inputs() -> tuple[EducationalClassificationInput, ...]:
    """Return grouped fake files for the standalone UI preview."""
    names = (
        *(f"수학_워크시트_{index:02}.pdf" for index in range(1, 13)),
        *(f"현장학습_사진_{index:02}.png" for index in range(1, 6)),
        *(f"과제묶음_{index:02}.zip" for index in range(1, 9)),
        *(f"확인필요_{index:02}.bin" for index in range(1, 4)),
    )
    return tuple(
        _sample_input(
            (DEMO_ROOT / ("Desktop" if index % 2 else "Downloads") / name),
            index,
        )
        for index, name in enumerate(names, start=1)
    )


def run() -> int:
    """Open only the grouped preview with fake data and no application services."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sort Pilot UI Preview")
    student = default_profile(StudentType.MIDDLE, 1, Semester.FIRST)
    outputs = classify_for_ui_test(sample_inputs(), student)
    dialog = EducationalPreviewDialog(
        outputs,
        DEMO_ROOT / "Desktop",
        DEMO_ROOT / "Downloads",
        test_mode=True,
    )
    dialog.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
