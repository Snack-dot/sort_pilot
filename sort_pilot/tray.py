from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon:
    def __init__(
        self,
        analyze_watched_folder: Callable[[], None],
        toggle_watch: Callable[[], None],
        undo: Callable[[], None],
        quit_program: Callable[[], None],
    ) -> None:
        self.tray = QSystemTrayIcon(self._icon())
        self.tray.setToolTip("Sort Pilot")
        self.menu = QMenu()
        self.analyze_action = QAction("감시 폴더 다시 분석", self.menu)
        self.analyze_action.triggered.connect(analyze_watched_folder)
        self.watch_action = QAction("감시 중지", self.menu)
        self.watch_action.triggered.connect(toggle_watch)
        self.undo_action = QAction("마지막 정리 실행 취소", self.menu)
        self.undo_action.triggered.connect(undo)
        self.quit_action = QAction("프로그램 종료", self.menu)
        self.quit_action.triggered.connect(quit_program)
        self.menu.addAction(self.analyze_action)
        self.menu.addSeparator()
        self.menu.addAction(self.watch_action)
        self.menu.addAction(self.undo_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)

    def set_watching(self, watching: bool) -> None:
        self.watch_action.setText("감시 중지" if watching else "감시 시작")

    def notify(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    @staticmethod
    def _icon() -> QIcon:
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
