from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sort_pilot.classifier_engine import ClassifierEngine
from sort_pilot.classifier_engine.config import Config
from sort_pilot.classifier_engine.extract import _ipynb, supports_content_analysis
from sort_pilot.classifier_engine.pipeline import Pipeline
from sort_pilot.classifier_engine.topics import TopicProfileStore
from sort_pilot.filters import is_safe_candidate
from sort_pilot.history import HistoryStore
from sort_pilot.models import ApprovedFileMove, FileSuggestion
from sort_pilot.organizer import build_operation, execute_batch, undo_latest


class CoreTests(unittest.TestCase):
    def test_real_engine_result_creates_named_hierarchical_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "incoming" / "불투명한 이름.txt"
            path.parent.mkdir()
            path.write_text("운영체제 과제 보고서", encoding="utf-8")
            analyzer = ClassifierEngine(
                Pipeline(Config(destination_root=str(root / "organized")), root / "engine"),
                TopicProfileStore(root / "profiles.json"),
            )
            try:
                analyzer.profile_store.upsert(
                    analyzer.profile_store.new_profile("문서", "과제모음", ["과제"])
                )
                result = analyzer.analyze(path)
                self.assertEqual(result.folder, "문서/과제모음")
                self.assertEqual(
                    set(result.to_dict()),
                    {"file_path", "file_name", "suggested_name", "folder", "reason"},
                )
                change = ApprovedFileMove(result, "current", result.folder, True)
                operation = build_operation(change, root / "organized")
                execute_batch([operation], HistoryStore(root / "history.json"))
                self.assertTrue((root / "organized" / "문서" / "과제모음" / path.name).is_file())
                self.assertFalse(path.exists())
            finally:
                analyzer.close()

    def test_filter_blocks_shortcuts_and_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shortcut = root / "Chrome.lnk"
            partial = root / "download.crdownload"
            hwp = root / "legacy.hwp"
            hwpx = root / "legacy.hwpx"
            archive = root / "backup.zip"
            winmd = root / "Microsoft.Services.Store.winmd"
            document = root / "notes.txt"
            for path in (shortcut, partial, hwp, hwpx, archive, winmd, document):
                path.touch()
            self.assertFalse(is_safe_candidate(shortcut))
            self.assertFalse(is_safe_candidate(partial))
            self.assertFalse(is_safe_candidate(hwp))
            self.assertFalse(is_safe_candidate(hwpx))
            self.assertFalse(is_safe_candidate(archive))
            self.assertFalse(is_safe_candidate(winmd))
            self.assertTrue(is_safe_candidate(document))

    def test_ipynb_extracts_cells_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            notebook = Path(directory) / "analysis.ipynb"
            notebook.write_text(
                json.dumps(
                    {
                        "cells": [
                            {"cell_type": "markdown", "source": ["데이터 분석 보고서"]},
                            {
                                "cell_type": "code",
                                "source": ["sales_dataframe.groupby('region')"],
                                "outputs": [{"text": ["민감한 출력"]}],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            extracted = _ipynb(notebook, 20_000)
            self.assertTrue(supports_content_analysis(notebook))
            self.assertIn("데이터 분석 보고서", extracted)
            self.assertIn("sales_dataframe", extracted)
            self.assertNotIn("민감한 출력", extracted)

    def test_execute_and_undo_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "document(4).pdf"
            source.parent.mkdir()
            source.write_bytes(b"pdf")
            history = HistoryStore(root / "history.json")
            destination_root = root / "organized"
            destination_root.mkdir()
            suggestion = FileSuggestion(str(source), source.name, "과제안내서.pdf", "프로젝트", "test")
            change = ApprovedFileMove(suggestion, "current", "프로젝트", True)
            operation = build_operation(change, destination_root)
            execute_batch([operation], history)
            self.assertFalse(source.exists())
            self.assertTrue(operation.destination_path.exists())

            restored = undo_latest(history)
            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse(operation.destination_path.exists())
            self.assertFalse(destination_root.joinpath("프로젝트").exists())
            self.assertTrue(destination_root.exists())

    def test_move_keeps_original_file_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination_root = root / "organized"
            destination_root.mkdir()
            source = root / "incoming" / "original.txt"
            source.parent.mkdir()
            source.write_text("move", encoding="utf-8")
            suggestion = FileSuggestion(str(source), source.name, "renamed.txt", "프로젝트", "test")
            change = ApprovedFileMove(suggestion, "current", "프로젝트", True)
            operation = build_operation(change, destination_root)
            self.assertEqual(
                operation.destination_path.resolve(),
                (destination_root / "프로젝트" / "original.txt").resolve(),
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
            suggestion = FileSuggestion(str(source), source.name, source.name, "구매기록", "test")
            change = ApprovedFileMove(suggestion, "current", "구매기록", True)

            execute_batch([build_operation(change, destination_root)], HistoryStore(history_path))
            restored = undo_latest(HistoryStore(history_path))

            self.assertEqual(len(restored), 1)
            self.assertTrue(source.exists())
            self.assertFalse((destination_root / "구매기록").exists())

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

