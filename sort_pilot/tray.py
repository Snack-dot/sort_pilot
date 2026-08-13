from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon:
    def __init__(
        self,
        organize_all: Callable[[], None],
        organize_desktop: Callable[[], None],
        organize_downloads: Callable[[], None],
        undo: Callable[[], None],
        quit_program: Callable[[], None],
    ) -> None:
        self.tray = QSystemTrayIcon(self._icon())
        self.tray.setToolTip("Sort Pilot")
        self.menu = QMenu()
        self.batch_action = QAction("일괄 정리", self.menu)
        self.batch_action.triggered.connect(organize_all)
        self.desktop_action = QAction("바탕화면 정리", self.menu)
        self.desktop_action.triggered.connect(organize_desktop)
        self.downloads_action = QAction("다운로드 폴더 정리", self.menu)
        self.downloads_action.triggered.connect(organize_downloads)
        self.undo_action = QAction("마지막 정리 실행 취소", self.menu)
        self.undo_action.triggered.connect(undo)
        self.quit_action = QAction("프로그램 종료", self.menu)
        self.quit_action.triggered.connect(quit_program)
        self.menu.addAction(self.batch_action)
        self.menu.addAction(self.desktop_action)
        self.menu.addAction(self.downloads_action)
        self.menu.addSeparator()
        self.menu.addAction(self.undo_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)

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
