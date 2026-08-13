from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .classifier import RuleBasedAnalyzer
from .history import HistoryStore
from .organizer import build_operation, execute_batch, undo_latest
from .preview import PreviewDialog
from .scanner import scan_folder
from .tray import TrayIcon


class AppController:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        self.analyzer = RuleBasedAnalyzer()
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.history = HistoryStore(app_data / "history.json")
        self.downloads_folder = Path.home() / "Downloads"
        self.tray = TrayIcon(
            self.organize_all,
            self.organize_desktop,
            self.organize_downloads,
            self.undo,
            self.quit,
        )

    def start(self) -> None:
        self.tray.show()

    def organize_desktop(self) -> None:
        self._organize_existing_files(self._desktop_folder(), "바탕화면")

    def organize_downloads(self) -> None:
        self._organize_existing_files(self.downloads_folder, "다운로드 폴더")

    def organize_all(self) -> None:
        suggestions = scan_folder(self._desktop_folder(), self.analyzer)
        suggestions.extend(scan_folder(self.downloads_folder, self.analyzer))
        if not suggestions:
            QMessageBox.information(None, "Sort Pilot", "바탕화면과 다운로드 폴더에 정리할 파일이 없습니다.")
            return
        self._show_preview(suggestions)

    @staticmethod
    def _desktop_folder() -> Path:
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))

    def _organize_existing_files(self, folder: Path, label: str) -> None:
        suggestions = scan_folder(folder, self.analyzer)
        if not suggestions:
            QMessageBox.information(None, "Sort Pilot", f"{label}에 정리할 파일이 없습니다.")
            return
        self._show_preview(suggestions)

    def undo(self) -> None:
        if QMessageBox.question(None, "실행 취소", "마지막 정리 작업을 원래 위치로 되돌릴까요?") != QMessageBox.StandardButton.Yes:
            return
        restored = undo_latest(self.history)
        message = f"{len(restored)}개 파일을 원래 위치로 되돌렸습니다." if restored else "실행 취소할 작업이 없습니다."
        QMessageBox.information(None, "Sort Pilot", message)

    def quit(self) -> None:
        if QMessageBox.question(None, "프로그램 종료", "Sort Pilot을 종료할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.tray.hide()
        self.app.quit()

    def _show_preview(self, suggestions) -> None:
        dialog = PreviewDialog(suggestions, self._desktop_folder(), self.downloads_folder)
        if dialog.exec() != PreviewDialog.DialogCode.Accepted:
            return
        operations = [
            build_operation(item, self._destination_root(item.destination_root, item.suggestion.source))
            for item in dialog.approved_changes()
        ]
        try:
            completed = execute_batch(operations, self.history)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(None, "정리 실패", str(exc))
            return
        QMessageBox.information(None, "정리 완료", f"{len(completed)}개 파일을 정리했습니다.")

    def _destination_root(self, choice: str, source: Path) -> Path:
        roots = {
            "current": source.parent,
            "desktop": self._desktop_folder(),
            "downloads": self.downloads_folder,
        }
        return roots.get(choice, source.parent)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Sort Pilot")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Sort Pilot", "이 시스템에서는 트레이 아이콘을 사용할 수 없습니다.")
        return 1
    controller = AppController(app)
    controller.start()
    return app.exec()
