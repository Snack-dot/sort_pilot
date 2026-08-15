from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QProgressDialog, QSystemTrayIcon

from .analysis_queue import BatchAnalysisController
from .classifier_engine.config import data_dir
from .classifier_engine.topics import AnalysisRecord
from .history import HistoryStore
from .instance_lock import SingleInstanceLock
from .local_tagger import LocalModelInstaller, LocalTagger
from .llm_file_classifier import ClassificationCache, LlmFileClassifier, ROLE_TEMPLATES
from .model_setup import ensure_local_model
from .models import FileSuggestion
from .organizer import build_operation, execute_batch, undo_latest
from .preview import PreviewDialog
from .scanner import collect_candidates
from .tray import TrayIcon


class AppController(QObject):
    """Coordinate tray actions, local extraction, LLM classification, moves, and Undo."""

    llm_progress = pyqtSignal(int, int)

    def __init__(self, app: QApplication) -> None:
        """Initialize application services without starting file analysis."""
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.history = HistoryStore(app_data / "history.json", app_data / "history.db")
        self.model_installer = LocalModelInstaller(data_dir() / "local_ai")
        self.local_tagger = LocalTagger(self.model_installer)
        self.llm_classifier = LlmFileClassifier(
            self.local_tagger,
            ClassificationCache(data_dir() / "classification_cache.json"),
        )
        self.downloads_folder = Path.home() / "Downloads"
        self.selected_user_type: str | None = None
        self.analysis = BatchAnalysisController(self)
        self.analysis.progress.connect(self._update_progress)
        self.analysis.completed.connect(self._analysis_completed)
        self.analysis.cancelled.connect(self._analysis_cancelled)
        self.analysis.busy_changed.connect(self._set_busy)
        self.llm_progress.connect(self._update_progress)
        self._llm_executor = ThreadPoolExecutor(max_workers=1)
        self._llm_future = None
        self._llm_cancel_event = threading.Event()
        self._cached_organization_suggestions: list[FileSuggestion] = []
        self.progress_dialog: QProgressDialog | None = None
        self.tray = TrayIcon(
            self.organize_all,
            self.organize_desktop,
            self.organize_downloads,
            self.select_user_type,
            self.undo,
            self.quit,
        )

    def start(self) -> None:
        """Show the tray icon and report a successful history migration."""
        self.tray.show()
        if self.history.migrated_legacy_batch:
            self.tray.notify("Sort Pilot", "기존 실행 취소 기록을 JSON 형식으로 이전했습니다.")

    def organize_desktop(self) -> None:
        """Analyze safe top-level files on the Desktop."""
        self._organize_existing_files([self._desktop_folder()], "바탕화면")

    def organize_downloads(self) -> None:
        """Analyze safe top-level files in Downloads."""
        self._organize_existing_files([self.downloads_folder], "다운로드 폴더")

    def organize_all(self) -> None:
        """Analyze Desktop and Downloads together in one deduplicated session."""
        self._organize_existing_files(
            [self._desktop_folder(), self.downloads_folder],
            "바탕화면과 다운로드 폴더",
        )

    @staticmethod
    def _desktop_folder() -> Path:
        """Resolve the platform Desktop folder through Qt."""
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))

    def _organize_existing_files(self, folders: list[Path], label: str) -> None:
        """Collect candidates and start extraction before role-aware LLM classification."""
        if not self._ensure_user_type():
            return
        if not ensure_local_model(None, self.model_installer):
            QMessageBox.warning(None, "Sort Pilot", "로컬 LLM이 준비되지 않아 분류를 시작하지 않았습니다.")
            return
        paths: list[Path] = []
        try:
            for folder in folders:
                paths.extend(collect_candidates(folder))
        except (OSError, NotADirectoryError) as exc:
            QMessageBox.critical(None, "폴더 읽기 실패", str(exc))
            return
        if not paths:
            QMessageBox.information(None, "Sort Pilot", f"{label}에 정리할 파일이 없습니다.")
            return
        try:
            cached, paths = self.llm_classifier.partition_cached(paths, self.selected_user_type)
        except OSError as exc:
            QMessageBox.critical(None, "캐시 확인 실패", str(exc))
            return
        self._cached_organization_suggestions = cached
        if not paths:
            self._cached_organization_suggestions = []
            self._show_preview(cached)
            return
        self._start_analysis(paths, "LLM 분류용 내용 추출")

    def _ensure_user_type(self) -> bool:
        """Require one role before classification so it can influence the LLM prompt."""
        if self.selected_user_type in ROLE_TEMPLATES:
            return True
        return self.select_user_type()

    def select_user_type(self) -> bool:
        """Let the user choose or change the role used by future classifications."""
        options = list(ROLE_TEMPLATES)
        current = options.index(self.selected_user_type) if self.selected_user_type in options else 0
        value, accepted = QInputDialog.getItem(
            None,
            "사용자 유형 선택",
            "파일을 어떤 관점으로 분류할까요?",
            options,
            current,
            False,
        )
        if not accepted:
            return False
        self.selected_user_type = str(value)
        self.tray.set_user_type(self.selected_user_type)
        self.tray.notify("Sort Pilot", f"사용자 유형을 '{self.selected_user_type}'(으)로 변경했습니다.")
        return True

    def _start_analysis(self, paths, label: str) -> None:
        """Start one extraction queue session with a progress label."""
        total = self.analysis.start(paths)
        if total:
            self._show_progress(total, label)

    def _show_progress(self, total: int, label: str) -> None:
        """Display the cancellable modal progress window for the active batch."""
        dialog = QProgressDialog(f"{label} 중입니다.", "취소", 0, total)
        dialog.setWindowTitle("Sort Pilot - AI 분석")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setProperty("task_label", label)
        dialog.canceled.connect(self.analysis.cancel)
        self.progress_dialog = dialog
        dialog.show()

    def _update_progress(self, completed: int, total: int) -> None:
        """Reflect worker completion on the Qt main thread."""
        if self.progress_dialog is not None:
            label = self.progress_dialog.property("task_label") or "AI 분석"
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(completed)
            percent = round(completed * 100 / total) if total else 100
            self.progress_dialog.setLabelText(f"{label}: {percent}% ({completed}/{total})")

    def _analysis_completed(self, results: list, errors: list[tuple[str, str]]) -> None:
        """Send completed extraction records to role-aware LLM classification."""
        self._report_analysis_errors(errors)
        records = [result for result in results if isinstance(result, AnalysisRecord)]
        self._complete_organization(records)

    def _complete_organization(self, records: list[AnalysisRecord]) -> None:
        """Let the local LLM perform final role-aware classification, then preview."""
        if not records:
            if self._cached_organization_suggestions:
                cached = self._cached_organization_suggestions
                self._cached_organization_suggestions = []
                self._close_progress()
                self._show_preview(cached)
                return
            self._close_progress()
            QMessageBox.information(None, "Sort Pilot", "분석 결과가 없습니다.")
            return
        if self.selected_user_type not in ROLE_TEMPLATES:
            self._close_progress()
            QMessageBox.warning(None, "Sort Pilot", "사용자 유형이 선택되지 않았습니다.")
            return
        if self.progress_dialog is None:
            self._show_progress(len(records), "LLM 파일 분류")
        else:
            self.progress_dialog.setRange(0, len(records))
            self.progress_dialog.setValue(0)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.setProperty("task_label", "LLM 파일 분류")
            self.progress_dialog.setLabelText("LLM 파일 분류: 0% (0/{})".format(len(records)))
        self._set_busy(True)
        self._llm_cancel_event.clear()
        user_type = self.selected_user_type
        self._llm_future = self._llm_executor.submit(
            self.llm_classifier.classify,
            records,
            user_type,
            lambda done, total: self.llm_progress.emit(done, total),
            self._llm_cancel_event.is_set,
        )
        QTimer.singleShot(100, self._poll_llm_result)

    def _poll_llm_result(self) -> None:
        """Finish background LLM classification without blocking the tray event loop."""
        future = self._llm_future
        if future is None or not future.done():
            QTimer.singleShot(100, self._poll_llm_result)
            return
        self._llm_future = None
        self._close_progress()
        self._set_busy(False)
        try:
            suggestions = self._cached_organization_suggestions + future.result()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(None, "LLM 분류 실패", str(exc))
            return
        finally:
            self._cached_organization_suggestions = []
        self._show_preview(suggestions)

    def _report_analysis_errors(self, errors: list[tuple[str, str]]) -> None:
        """Report bounded per-file extraction failures without losing successful results."""
        if not errors:
            return
        examples = "\n".join(f"- {Path(path).name}: {message}" for path, message in errors[:5])
        suffix = f"\n외 {len(errors) - 5}개" if len(errors) > 5 else ""
        QMessageBox.warning(None, "일부 분석 실패", f"{len(errors)}개 파일을 분석하지 못했습니다.\n{examples}{suffix}")

    def _analysis_cancelled(self) -> None:
        """Close progress and discard cached suggestions after cancellation."""
        self._close_progress()
        self._cached_organization_suggestions = []
        self.tray.notify("Sort Pilot", "파일 분석을 취소했습니다.")

    def _close_progress(self) -> None:
        """Detach and close the active progress dialog safely."""
        dialog = self.progress_dialog
        self.progress_dialog = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _set_busy(self, busy: bool) -> None:
        """Prevent overlapping analysis, role changes, and Undo while busy."""
        self.tray.set_busy(busy)

    def undo(self) -> None:
        """Ask for confirmation and restore the latest recorded move batch."""
        if QMessageBox.question(None, "실행 취소", "마지막 정리 작업을 원래 위치로 되돌릴까요?") != QMessageBox.StandardButton.Yes:
            return
        restored = undo_latest(self.history)
        message = f"{len(restored)}개 파일을 원래 위치로 되돌렸습니다." if restored else "실행 취소할 작업이 없습니다."
        QMessageBox.information(None, "Sort Pilot", message)

    def quit(self) -> None:
        """Confirm exit, cancel queued work, and wait for active workers."""
        if QMessageBox.question(None, "프로그램 종료", "Sort Pilot을 종료할까요?") != QMessageBox.StandardButton.Yes:
            return
        self._close_progress()
        self.analysis.shutdown(-1)
        self._llm_cancel_event.set()
        self.local_tagger.cancel_file_classification()
        self._llm_executor.shutdown(wait=True, cancel_futures=True)
        self.tray.hide()
        self.app.quit()

    def _show_preview(self, suggestions: list[FileSuggestion]) -> None:
        """Show editable destinations and execute only approved moves."""
        dialog = PreviewDialog(
            suggestions,
            self._desktop_folder(),
            self.downloads_folder,
            self.selected_user_type,
        )
        if dialog.exec() != PreviewDialog.DialogCode.Accepted:
            return
        self.selected_user_type = dialog.selected_user_type()
        changes = dialog.approved_changes()
        operations = [
            build_operation(item, self._destination_root(item.destination_root, item.suggestion.source))
            for item in changes
        ]
        try:
            completed = execute_batch(operations, self.history)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(None, "정리 실패", str(exc))
            return
        QMessageBox.information(None, "정리 완료", f"{len(completed)}개 파일을 정리했습니다.")

    def _destination_root(self, choice: str, source: Path) -> Path:
        """Resolve a preview destination identifier to an allowed root path."""
        roots = {
            "current": source.parent,
            "desktop": self._desktop_folder(),
            "downloads": self.downloads_folder,
        }
        return roots.get(choice, source.parent)

def run() -> int:
    """Run one locked tray application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sort Pilot")
    app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    instance_lock = SingleInstanceLock(app_data / "sort-pilot.lock")
    if not instance_lock.acquire():
        QMessageBox.information(None, "Sort Pilot", "Sort Pilot이 이미 실행 중입니다.")
        return 0
    try:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "Sort Pilot", "이 시스템에서는 트레이 아이콘을 사용할 수 없습니다.")
            return 1
        controller = AppController(app)
        controller.start()
        return app.exec()
    finally:
        instance_lock.release()
