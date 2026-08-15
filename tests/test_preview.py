from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox

from sort_pilot.models import FileSuggestion
from sort_pilot.preview import PreviewDialog


class PreviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        existing = QApplication.instance()
        if existing is not None and not isinstance(existing, QApplication):
            raise unittest.SkipTest("A QCoreApplication already owns this test process")
        cls.app = existing or QApplication([])

    def test_full_organization_path_is_shown_and_returned(self) -> None:
        suggestion = FileSuggestion(
            "C:/Downloads/lecture.pdf",
            "lecture.pdf",
            "lecture.pdf",
            "학업/운영체제/강의자료",
            "",
        )
        dialog = PreviewDialog(
            [suggestion], Path("C:/Desktop"), Path("C:/Downloads"), "학생"
        )
        try:
            self.assertEqual(dialog.table.horizontalHeaderItem(3).text(), "정리 경로")
            selector = dialog.table.cellWidget(0, 3)
            self.assertIsInstance(selector, QComboBox)
            self.assertEqual(selector.currentText(), "학업/운영체제/강의자료")
            self.assertEqual(dialog._organization_path(0), "학업/운영체제/강의자료")
        finally:
            dialog.close()

    def test_organization_path_rejects_absolute_or_deep_paths(self) -> None:
        suggestion = FileSuggestion(
            "C:/Downloads/file.txt", "file.txt", "file.txt", "기타/확인필요", ""
        )
        dialog = PreviewDialog(
            [suggestion], Path("C:/Desktop"), Path("C:/Downloads"), "학생"
        )
        try:
            selector = dialog.table.cellWidget(0, 3)
            selector.setCurrentText("학업/컴퓨터공학/운영체제/강의자료")
            with self.assertRaises(ValueError):
                dialog._organization_path(0)
            selector.setCurrentText("C:/Windows")
            with self.assertRaises(ValueError):
                dialog._organization_path(0)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
