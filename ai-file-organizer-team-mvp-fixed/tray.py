from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class SystemTray:
    def __init__(
        self,
        on_toggle_watch: Callable[[], None],
        on_organize_desktop: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.create_default_icon())
        self.tray.setToolTip("AI File Organizer - 감시 중")

        self.menu = QMenu()

        self.organize_action = QAction("바탕화면 정리")
        self.organize_action.triggered.connect(on_organize_desktop)

        self.toggle_action = QAction("감시 중지")
        self.toggle_action.triggered.connect(on_toggle_watch)

        # 프로그램 종료는 감시 시작/중지와 완전히 별개의 메뉴
        self.quit_action = QAction("프로그램 종료")
        self.quit_action.triggered.connect(on_quit)

        self.menu.addAction(self.organize_action)
        self.menu.addSeparator()
        self.menu.addAction(self.toggle_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)

    @staticmethod
    def create_default_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#4f6bed"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "AI",
        )
        painter.end()

        return QIcon(pixmap)

    def set_watching(self, watching: bool) -> None:
        if watching:
            self.toggle_action.setText("감시 중지")
            self.tray.setToolTip("AI File Organizer - 감시 중")
        else:
            self.toggle_action.setText("감시 시작")
            self.tray.setToolTip("AI File Organizer - 감시 중지됨")

    def show_message(self, title: str, message: str) -> None:
        self.tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()
