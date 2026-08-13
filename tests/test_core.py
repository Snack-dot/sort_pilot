from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sort_pilot.classifier import RuleBasedAnalyzer
from sort_pilot.filters import is_safe_candidate
from sort_pilot.history import HistoryStore
from sort_pilot.models import ApprovedFileMove, FileSuggestion
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
            history = HistoryStore(root / "history.json")
            destination_root = root / "organized"
            destination_root.mkdir()
            suggestion = FileSuggestion(str(source), source.name, "과제안내서.pdf", "학교", "test")
            change = ApprovedFileMove(suggestion, "학교", True)
            operation = build_operation(change, destination_root)
            execute_batch([operation], history)
            self.assertFalse(source.exists())
            self.assertTrue(operation.destination_path.exists())

            restored = undo_latest(history)
            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse(operation.destination_path.exists())
            self.assertFalse(destination_root.joinpath("학교").exists())
            self.assertTrue(destination_root.exists())

    def test_move_keeps_original_file_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination_root = root / "organized"
            destination_root.mkdir()
            move_source = root / "move" / "original.txt"
            move_source.parent.mkdir()
            move_source.write_text("move", encoding="utf-8")
            move_suggestion = FileSuggestion(
                str(move_source), move_source.name, "suggested.txt", "학교", "test"
            )
            move_change = ApprovedFileMove(move_suggestion, "학교", True)
            move_operation = build_operation(move_change, destination_root)
            self.assertEqual(move_operation.destination_path, destination_root / "학교" / "original.txt")

    def test_undo_keeps_preexisting_destination_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "assignment.txt"
            source.parent.mkdir()
            source.write_text("assignment", encoding="utf-8")
            destination_root = root / "organized"
            school_folder = destination_root / "학교"
            school_folder.mkdir(parents=True)
            history = HistoryStore(root / "history.json")
            suggestion = FileSuggestion(
                str(source), source.name, source.name, "학교", "test"
            )
            change = ApprovedFileMove(suggestion, "학교", True)

            execute_batch([build_operation(change, destination_root)], history)
            undo_latest(history)

            self.assertTrue(source.exists())
            self.assertTrue(school_folder.exists())

    def test_json_history_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "receipt.txt"
            source.parent.mkdir()
            source.write_text("receipt", encoding="utf-8")
            history_path = root / "history.json"
            destination_root = root / "organized"
            destination_root.mkdir()
            suggestion = FileSuggestion(
                str(source), source.name, "ignored-name.txt", "금융", "test"
            )
            change = ApprovedFileMove(suggestion, "금융", True)

            execute_batch([build_operation(change, destination_root)], HistoryStore(history_path))
            restored = undo_latest(HistoryStore(history_path))

            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse((destination_root / "금융").exists())
            self.assertIn('"batches"', history_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
