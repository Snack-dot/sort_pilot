from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from .classifier import FileAnalyzer, LocalPipelineAnalyzer
from .models import FileSuggestion

_WORKER_LOCAL = threading.local()


class _WorkerSignals(QObject):
    """Cross-thread signals shared by all jobs in an analysis controller."""

    result = pyqtSignal(object, int, object)
    error = pyqtSignal(object, int, str, str)
    finished = pyqtSignal(object, int)


class _AnalysisJob(QRunnable):
    """Classify one path on a reusable Qt thread-pool thread."""

    def __init__(
        self,
        token: object,
        index: int,
        path: Path,
        cancelled: threading.Event,
        signals: _WorkerSignals,
        analyzer_factory: Callable[[], FileAnalyzer],
    ) -> None:
        """Capture immutable job state and its session cancellation token."""
        super().__init__()
        self.token = token
        self.index = index
        self.path = path
        self.cancelled = cancelled
        self.signals = signals
        self.analyzer_factory = analyzer_factory

    def run(self) -> None:
        """Run classification unless canceled and always signal job completion."""
        try:
            if self.cancelled.is_set():
                return
            analyzer = self._thread_analyzer()
            analyze_record = getattr(analyzer, "analyze_record", None)
            suggestion = analyze_record(self.path) if analyze_record else analyzer.analyze(self.path)
            if not self.cancelled.is_set():
                self.signals.result.emit(self.token, self.index, suggestion)
        except Exception as exc:  # A failed file must not abort the batch.
            if not self.cancelled.is_set():
                self.signals.error.emit(self.token, self.index, str(self.path), str(exc))
        finally:
            self.signals.finished.emit(self.token, self.index)

    def _thread_analyzer(self) -> FileAnalyzer:
        """Create one analyzer per pool thread and reuse it for later jobs."""
        analyzers = getattr(_WORKER_LOCAL, "analyzers", None)
        if analyzers is None:
            analyzers = {}
            _WORKER_LOCAL.analyzers = analyzers
        key = id(self.analyzer_factory)
        analyzer = analyzers.get(key)
        if analyzer is None:
            analyzer = self.analyzer_factory()
            analyzers[key] = analyzer
        return analyzer


class BatchAnalysisController(QObject):
    """Deduplicate and coordinate one cancellable two-worker analysis session."""

    progress = pyqtSignal(int, int)
    completed = pyqtSignal(object, object)
    cancelled = pyqtSignal()
    busy_changed = pyqtSignal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        analyzer_factory: Callable[[], FileAnalyzer] = LocalPipelineAnalyzer,
        worker_count: int = 2,
    ) -> None:
        """Create an isolated pool with a fixed worker count and shared signals."""
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(worker_count)
        self.pool.setExpiryTimeout(-1)
        self.analyzer_factory = analyzer_factory
        self._signals = _WorkerSignals(self)
        self._signals.result.connect(self._on_result)
        self._signals.error.connect(self._on_error)
        self._signals.finished.connect(self._on_finished)
        self._token: object | None = None
        self._cancel_event: threading.Event | None = None
        self._total = 0
        self._finished = 0
        self._results: dict[int, FileSuggestion] = {}
        self._errors: list[tuple[str, str]] = []

    @property
    def busy(self) -> bool:
        """Return whether a non-canceled analysis session is active."""
        return self._token is not None

    def start(self, paths: Iterable[Path]) -> int:
        """Deduplicate paths, enqueue jobs in input order, and return job count."""
        if self.busy:
            raise RuntimeError("An analysis session is already running")
        unique_paths = self._unique_paths(paths)
        if not unique_paths:
            return 0
        self._token = object()
        self._cancel_event = threading.Event()
        self._total = len(unique_paths)
        self._finished = 0
        self._results = {}
        self._errors = []
        self.busy_changed.emit(True)
        self.progress.emit(0, self._total)
        for index, path in enumerate(unique_paths):
            self.pool.start(
                _AnalysisJob(
                    self._token,
                    index,
                    path,
                    self._cancel_event,
                    self._signals,
                    self.analyzer_factory,
                )
            )
        return self._total

    def cancel(self) -> None:
        """Cancel queued work and invalidate all results from the active session."""
        if not self.busy:
            return
        if self._cancel_event is not None:
            self._cancel_event.set()
        self.pool.clear()
        self._token = None
        self.busy_changed.emit(False)
        self.cancelled.emit()

    def shutdown(self, timeout_ms: int = 10_000) -> bool:
        """Reject outstanding work and wait briefly for in-flight jobs to return."""
        self.cancel()
        self.pool.clear()
        return self.pool.waitForDone(timeout_ms)

    @staticmethod
    def _unique_paths(paths: Iterable[Path]) -> list[Path]:
        """Resolve and deduplicate paths using platform path-case semantics."""
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            resolved = path.resolve()
            key = os.path.normcase(str(resolved))
            if key not in seen:
                seen.add(key)
                unique.append(resolved)
        return unique

    def _on_result(self, token: object, index: int, suggestion: FileSuggestion) -> None:
        """Collect a result only when it belongs to the active session."""
        if token is self._token:
            self._results[index] = suggestion

    def _on_error(self, token: object, index: int, path: str, message: str) -> None:
        """Collect a per-file failure without aborting other jobs."""
        if token is self._token:
            self._errors.append((path, message))

    def _on_finished(self, token: object, index: int) -> None:
        """Advance progress and emit ordered results when all jobs have returned."""
        if token is not self._token:
            return
        self._finished += 1
        self.progress.emit(self._finished, self._total)
        if self._finished != self._total:
            return
        results = [self._results[index] for index in sorted(self._results)]
        errors = list(self._errors)
        self._token = None
        self._cancel_event = None
        self.busy_changed.emit(False)
        self.completed.emit(results, errors)
