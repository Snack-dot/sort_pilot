from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from batch_preview import BatchPreviewDialog
from batch_scanner import scan_desktop
from popup import MoveApprovalPopup
from tray import SystemTray
from watcher import DownloadWatcher


class AppController:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.download_folder = Path.home() / "Downloads"
        self.watching = False
        self.is_quitting = False

        self.popup = MoveApprovalPopup()
        self.watcher = DownloadWatcher(self.download_folder)
        self.watcher.file_ready.connect(self.popup.show_file_suggestion)

        self.tray = SystemTray(
            on_toggle_watch=self.toggle_watch,
            on_organize_desktop=self.organize_desktop,
            on_quit=self.quit_program,
        )

        # Windows 종료나 Ctrl+C 이외의 정상 종료 경로에서도 watcher 정리
        self.app.aboutToQuit.connect(self.cleanup)

    def start(self) -> None:
        self.start_watching()
        self.tray.show()
        self.tray.show_message(
            "AI File Organizer",
            "다운로드 폴더 감시를 시작했습니다.",
        )

    def start_watching(self) -> None:
        if self.watching:
            return

        self.watcher.start_watching()
        self.watching = True
        self.tray.set_watching(True)

    def stop_watching(self) -> None:
        if not self.watching:
            return

        self.watcher.stop_watching()
        self.watching = False
        self.tray.set_watching(False)

    def toggle_watch(self) -> None:
        if self.watching:
            self.stop_watching()
            self.tray.show_message("감시 중지", "파일 감지를 중지했습니다.")
        else:
            self.start_watching()
            self.tray.show_message("감시 시작", "파일 감지를 다시 시작했습니다.")

    def organize_desktop(self) -> None:
        results = scan_desktop()

        if not results:
            QMessageBox.information(
                None,
                "바탕화면 정리",
                "정리할 수 있는 일반 파일이 없습니다.",
            )
            return

        dialog = BatchPreviewDialog(results)
        dialog.exec()

    def quit_program(self) -> None:
        if self.is_quitting:
            return

        answer = QMessageBox.question(
            None,
            "프로그램 종료",
            "AI File Organizer를 완전히 종료할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.is_quitting = True
        print("[File Organizer] 프로그램을 종료합니다.")
        self.cleanup()
        self.tray.hide()
        self.app.quit()

    def cleanup(self) -> None:
        if self.watching:
            print("[Watcher] 감시를 종료합니다.")
            self.stop_watching()
