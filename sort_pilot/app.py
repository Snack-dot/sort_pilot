from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .classifier import RuleBasedAnalyzer
from .filters import is_safe_candidate
from .history import HistoryStore
from .organizer import build_operation, execute_batch, undo_latest
from .preview import PreviewDialog
from .scanner import scan_folder
from .tray import TrayIcon
from .watcher import FolderWatcher


class AppController:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        self.analyzer = RuleBasedAnalyzer()
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.history = HistoryStore(app_data / "history.db")
        self.watch_folder = Path.home() / "Downloads"
        self.watcher = FolderWatcher(self.watch_folder)
        self.watcher.file_ready.connect(self._new_file)
        self.watcher.error.connect(lambda message: self.tray.notify("감시 오류", message))
        self.tray = TrayIcon(self.analyze_watched_folder, self.toggle_watch, self.undo, self.quit)

    def start(self) -> None:
        self.tray.show()
        self.watcher.start()
        self.tray.set_watching(True)
        self.tray.notify("Sort Pilot", "다운로드 폴더 감시를 시작했습니다.")

    def analyze_watched_folder(self) -> None:
        """Manually analyze existing files that were not caught as new downloads."""
        suggestions = scan_folder(self.watch_folder, self.analyzer)
        if not suggestions:
            QMessageBox.information(None, "Sort Pilot", "분석할 파일이 없습니다.")
            return
        self._show_preview(suggestions, self.watch_folder)

    def toggle_watch(self) -> None:
        if self.watcher.running:
            self.watcher.stop()
        else:
            self.watcher.start()
        self.tray.set_watching(self.watcher.running)

    def undo(self) -> None:
        if QMessageBox.question(None, "실행 취소", "마지막 정리 작업을 원래 위치로 되돌릴까요?") != QMessageBox.StandardButton.Yes:
            return
        restored = undo_latest(self.history)
        message = f"{len(restored)}개 파일을 원래 위치로 되돌렸습니다." if restored else "실행 취소할 작업이 없습니다."
        QMessageBox.information(None, "Sort Pilot", message)

    def quit(self) -> None:
        if QMessageBox.question(None, "프로그램 종료", "Sort Pilot을 종료할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.watcher.stop()
        self.tray.hide()
        self.app.quit()

    def _new_file(self, path: Path) -> None:
        if is_safe_candidate(path):
            suggestion = self.analyzer.analyze(path)
            self._show_preview([suggestion], self.watch_folder)

    def _show_preview(self, suggestions, destination_root: Path) -> None:
        dialog = PreviewDialog(suggestions, destination_root)
        if dialog.exec() != PreviewDialog.DialogCode.Accepted:
            return
        operations = [build_operation(item, destination_root) for item in dialog.selected_suggestions()]
        try:
            completed = execute_batch(operations, self.history)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(None, "정리 실패", str(exc))
            return
        QMessageBox.information(None, "정리 완료", f"{len(completed)}개 파일을 정리했습니다.")


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Sort Pilot")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Sort Pilot", "이 시스템에서는 트레이 아이콘을 사용할 수 없습니다.")
        return 1
    controller = AppController(app)
    controller.start()
    return app.exec()
