from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QProgressDialog,
    QSystemTrayIcon,
)

from .analysis_queue import BatchAnalysisController
from .history import HistoryStore
from .instance_lock import SingleInstanceLock
from .organizer import build_operation, execute_batch, undo_latest
from .preview import PreviewDialog
from .scanner import collect_candidates
from .tray import TrayIcon


class AppController(QObject):
    """Coordinate tray actions, background analysis, preview, moves, and Undo."""

    def __init__(self, app: QApplication) -> None:
        """Initialize application services without starting file analysis."""
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.history = HistoryStore(app_data / "history.json", app_data / "history.db")
        self.downloads_folder = Path.home() / "Downloads"
        self.analysis = BatchAnalysisController(self)
        self.analysis.progress.connect(self._update_progress)
        self.analysis.completed.connect(self._analysis_completed)
        self.analysis.cancelled.connect(self._analysis_cancelled)
        self.analysis.busy_changed.connect(self._set_busy)
        self.progress_dialog: QProgressDialog | None = None
        self.tray = TrayIcon(
            self.organize_all,
            self.organize_desktop,
            self.organize_downloads,
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
        """Collect candidates quickly and start a background classification batch."""
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
        total = self.analysis.start(paths)
        self._show_progress(total)

    def _show_progress(self, total: int) -> None:
        """Display the cancellable modal progress window for the active batch."""
        dialog = QProgressDialog("AI가 파일을 분석하고 있습니다.", "취소", 0, total)
        dialog.setWindowTitle("Sort Pilot - AI 분석")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(self.analysis.cancel)
        self.progress_dialog = dialog
        dialog.show()

    def _update_progress(self, completed: int, total: int) -> None:
        """Reflect worker completion on the Qt main thread."""
        if self.progress_dialog is not None:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(completed)
            self.progress_dialog.setLabelText(f"AI 분석 중: {completed}/{total}")

    def _analysis_completed(
        self,
        suggestions: list,
        errors: list[tuple[str, str]],
    ) -> None:
        """Close progress, report failures, and present successful suggestions."""
        self._close_progress()
        if errors:
            examples = "\n".join(f"- {Path(path).name}: {message}" for path, message in errors[:5])
            suffix = f"\n외 {len(errors) - 5}개" if len(errors) > 5 else ""
            QMessageBox.warning(
                None,
                "일부 분석 실패",
                f"{len(errors)}개 파일을 분석하지 못했습니다.\n{examples}{suffix}",
            )
        if suggestions:
            self._show_preview(suggestions)
        elif not errors:
            QMessageBox.information(None, "Sort Pilot", "분석 결과가 없습니다.")

    def _analysis_cancelled(self) -> None:
        """Close progress without displaying partial results after cancellation."""
        self._close_progress()
        self.tray.notify("Sort Pilot", "파일 분석을 취소했습니다.")

    def _close_progress(self) -> None:
        """Detach and close the active progress dialog safely."""
        dialog = self.progress_dialog
        self.progress_dialog = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _set_busy(self, busy: bool) -> None:
        """Prevent overlapping analysis and Undo operations."""
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
        self.tray.hide()
        self.app.quit()

    def _show_preview(self, suggestions: list) -> None:
        """Show editable destinations and execute only explicitly approved moves."""
        dialog = PreviewDialog(suggestions, self._desktop_folder(), self.downloads_folder)
        if dialog.exec() != PreviewDialog.DialogCode.Accepted:
            return
        operations = [
            build_operation(item, self._destination_root(item.destination_root, item.suggestion.source))
            for item in dialog.approved_changes()
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
    """Start one tray application instance and release its lock on exit."""
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
