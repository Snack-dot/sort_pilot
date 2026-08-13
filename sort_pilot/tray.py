from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon:
    """Own the system-tray icon and all top-level application actions."""

    def __init__(
        self,
        organize_all: Callable[[], None],
        organize_desktop: Callable[[], None],
        organize_downloads: Callable[[], None],
        calibrate_topics: Callable[[], None],
        manage_topics: Callable[[], None],
        migrate_folders: Callable[[], None],
        undo: Callable[[], None],
        quit_program: Callable[[], None],
    ) -> None:
        """Build the tray menu and connect its user actions."""
        self.tray = QSystemTrayIcon(self._icon())
        self.tray.setToolTip("Sort Pilot")
        self.menu = QMenu()
        self.batch_action = QAction("일괄 정리", self.menu)
        self.batch_action.triggered.connect(organize_all)
        self.desktop_action = QAction("바탕화면 정리", self.menu)
        self.desktop_action.triggered.connect(organize_desktop)
        self.downloads_action = QAction("다운로드 폴더 정리", self.menu)
        self.downloads_action.triggered.connect(organize_downloads)
        self.calibrate_action = QAction("주제 다시 보정", self.menu)
        self.calibrate_action.triggered.connect(calibrate_topics)
        self.topics_action = QAction("폴더/태그 관리", self.menu)
        self.topics_action.triggered.connect(manage_topics)
        self.migration_action = QAction("기존 폴더 계층화", self.menu)
        self.migration_action.triggered.connect(migrate_folders)
        self.undo_action = QAction("마지막 정리 실행 취소", self.menu)
        self.undo_action.triggered.connect(undo)
        self.quit_action = QAction("프로그램 종료", self.menu)
        self.quit_action.triggered.connect(quit_program)
        self.menu.addAction(self.batch_action)
        self.menu.addAction(self.desktop_action)
        self.menu.addAction(self.downloads_action)
        self.menu.addSeparator()
        self.menu.addAction(self.calibrate_action)
        self.menu.addAction(self.topics_action)
        self.menu.addAction(self.migration_action)
        self.menu.addSeparator()
        self.menu.addAction(self.undo_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)

    def set_busy(self, busy: bool) -> None:
        """Disable conflicting organization actions while analysis is active."""
        for action in (
            self.batch_action,
            self.desktop_action,
            self.downloads_action,
            self.calibrate_action,
            self.topics_action,
            self.migration_action,
            self.undo_action,
        ):
            action.setEnabled(not busy)

    def notify(self, title: str, message: str) -> None:
        """Show a short informational system notification."""
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def show(self) -> None:
        """Display the system-tray icon."""
        self.tray.show()

    def hide(self) -> None:
        """Remove the system-tray icon."""
        self.tray.hide()

    @staticmethod
    def _icon() -> QIcon:
        """Create the generated SP tray icon without external assets."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#2563eb"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(24)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), 0x84, "SP")
        painter.end()
        return QIcon(pixmap)
