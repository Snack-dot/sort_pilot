import sys
from PyQt6.QtWidgets import QApplication
from app_controller import AppController


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("AI File Organizer")

    controller = AppController(app)
    controller.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
