from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sort_pilot.classifier import RuleBasedAnalyzer
from sort_pilot.filters import is_safe_candidate
from sort_pilot.history import HistoryStore
from sort_pilot.models import FileSuggestion
from sort_pilot.organizer import build_operation, execute_batch, undo_latest


class CoreTests(unittest.TestCase):
    def test_rule_analyzer_keeps_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "운영체제 과제.PDF"
            path.write_text("test", encoding="utf-8")
            result = RuleBasedAnalyzer().analyze(path)
            self.assertEqual(result.folder, "학교")
            self.assertEqual(result.suggested_name, "운영체제_과제.pdf")
            self.assertEqual(
                set(result.to_dict()),
                {"file_path", "file_name", "suggested_name", "folder", "reason"},
            )

    def test_filter_blocks_shortcuts_and_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shortcut = root / "Chrome.lnk"
            partial = root / "download.crdownload"
            document = root / "notes.txt"
            for path in (shortcut, partial, document):
                path.touch()
            self.assertFalse(is_safe_candidate(shortcut))
            self.assertFalse(is_safe_candidate(partial))
            self.assertTrue(is_safe_candidate(document))

    def test_execute_and_undo_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "document(4).pdf"
            source.parent.mkdir()
            source.write_bytes(b"pdf")
            history = HistoryStore(root / "history.db")
            suggestion = FileSuggestion(str(source), source.name, "과제안내서.pdf", "학교", "test")
            operation = build_operation(suggestion, root / "organized")
            execute_batch([operation], history)
            self.assertFalse(source.exists())
            self.assertTrue(operation.destination_path.exists())

            restored = undo_latest(history)
            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse(operation.destination_path.exists())


if __name__ == "__main__":
    unittest.main()

