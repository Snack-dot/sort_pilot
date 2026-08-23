from __future__ import annotations

import threading
import time
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer

from sort_pilot.analysis_queue import BatchAnalysisController
from sort_pilot.classifier_engine import ClassifierEngine
from sort_pilot.classifier_engine.config import Config
from sort_pilot.classifier_engine.pipeline import Pipeline
from sort_pilot.classifier_engine.topics import AnalysisRecord, TopicProfileStore
from sort_pilot.models import FileSuggestion


class _SharedAnalyzer:
    """Test analyzer that measures queue concurrency across worker instances."""

    lock = threading.Lock()
    active = 0
    maximum = 0
    analyzed: list[str] = []

    def analyze(self, path: Path) -> FileSuggestion:
        with self.lock:
            type(self).active += 1
            type(self).maximum = max(type(self).maximum, type(self).active)
            type(self).analyzed.append(path.name)
        time.sleep(0.04)
        with self.lock:
            type(self).active -= 1
        return FileSuggestion(str(path), path.name, path.name, "테스트", "queue")


class AnalysisQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self) -> None:
        _SharedAnalyzer.active = 0
        _SharedAnalyzer.maximum = 0
        _SharedAnalyzer.analyzed = []

    def test_queue_deduplicates_preserves_order_and_uses_two_workers(self) -> None:
        controller = BatchAnalysisController(analyzer_factory=_SharedAnalyzer, worker_count=2)
        loop = QEventLoop()
        received: list = []
        controller.completed.connect(lambda results, errors: (received.append((results, errors)), loop.quit()))
        paths = [Path("a.txt"), Path("b.txt"), Path("a.txt"), Path("c.txt")]

        self.assertEqual(controller.start(paths), 3)
        QTimer.singleShot(5_000, loop.quit)
        loop.exec()

        self.assertEqual(len(received), 1)
        results, errors = received[0]
        self.assertEqual([item.file_name for item in results], ["a.txt", "b.txt", "c.txt"])
        self.assertEqual(errors, [])
        self.assertLessEqual(_SharedAnalyzer.maximum, 2)
        controller.shutdown()

    def test_cancel_suppresses_partial_preview_results(self) -> None:
        controller = BatchAnalysisController(analyzer_factory=_SharedAnalyzer, worker_count=2)
        loop = QEventLoop()
        completed: list = []
        controller.completed.connect(lambda results, errors: completed.append(results))
        controller.cancelled.connect(loop.quit)

        controller.start(Path(f"{index}.txt") for index in range(20))
        QTimer.singleShot(5, controller.cancel)
        QTimer.singleShot(5_000, loop.quit)
        loop.exec()

        self.assertEqual(completed, [])
        self.assertFalse(controller.busy)
        controller.shutdown()

    def test_default_queue_contract_accepts_real_engine_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "운영체제과제.pdf"
            path.write_bytes(b"not-a-real-pdf")
            analyzer = ClassifierEngine(
                Pipeline(Config(destination_root=str(root / "sorted")), root / "engine"),
                TopicProfileStore(root / "profiles.json"),
            )
            factory = lambda: analyzer
            controller = BatchAnalysisController(analyzer_factory=factory, worker_count=1)
            loop = QEventLoop()
            received: list = []
            controller.completed.connect(
                lambda results, errors: (received.append((results, errors)), loop.quit())
            )
            try:
                self.assertEqual(controller.start([path]), 1)
                QTimer.singleShot(5_000, loop.quit)
                loop.exec()
                self.assertEqual(len(received), 1)
                results, errors = received[0]
                self.assertEqual(errors, [])
                self.assertIsInstance(results[0], AnalysisRecord)
                self.assertIsNotNone(results[0].decision_id)
                self.assertEqual(results[0].engine_tier, "t2a")
                self.assertEqual(results[0].folder, "문서/미분류")
            finally:
                controller.shutdown()
                analyzer.close()


if __name__ == "__main__":
    unittest.main()
