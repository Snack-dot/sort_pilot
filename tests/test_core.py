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
            change = ApprovedFileMove(suggestion, "current", "학교", True)
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
            source = root / "incoming" / "original.txt"
            source.parent.mkdir()
            source.write_text("move", encoding="utf-8")
            suggestion = FileSuggestion(str(source), source.name, "renamed.txt", "학교", "test")
            change = ApprovedFileMove(suggestion, "current", "학교", True)
            operation = build_operation(change, destination_root)
            self.assertEqual(
                operation.destination_path.resolve(),
                (destination_root / "학교" / "original.txt").resolve(),
            )

    def test_json_history_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "receipt.txt"
            source.parent.mkdir()
            source.write_text("receipt", encoding="utf-8")
            history_path = root / "history.json"
            destination_root = root / "organized"
            destination_root.mkdir()
            suggestion = FileSuggestion(str(source), source.name, source.name, "금융", "test")
            change = ApprovedFileMove(suggestion, "current", "금융", True)

            execute_batch([build_operation(change, destination_root)], HistoryStore(history_path))
            restored = undo_latest(HistoryStore(history_path))

            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse((destination_root / "금융").exists())

    def test_legacy_sqlite_history_migrates_latest_active_batch(self) -> None:
        import sqlite3
        from contextlib import closing

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "history.db"
            with closing(sqlite3.connect(database)) as connection:
                with connection:
                    connection.execute(
                        "CREATE TABLE operations (id INTEGER PRIMARY KEY, batch_id TEXT, "
                        "source TEXT, destination TEXT, undone INTEGER DEFAULT 0)"
                    )
                    connection.execute(
                        "INSERT INTO operations(batch_id, source, destination, undone) VALUES (?, ?, ?, 0)",
                        ("legacy", "C:/source.txt", "C:/destination.txt"),
                    )
            store = HistoryStore(root / "history.json", database)
            latest = store.latest_batch()
            self.assertTrue(store.migrated_legacy_batch)
            self.assertIsNotNone(latest)
            self.assertEqual(latest[0], "legacy")
            self.assertTrue(database.exists())


if __name__ == "__main__":
    unittest.main()

