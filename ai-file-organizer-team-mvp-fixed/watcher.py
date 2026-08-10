import threading
import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from classifier import classify_file
from filters import is_temporary_file


class NewFileHandler(FileSystemEventHandler):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def on_created(self, event) -> None:
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if is_temporary_file(file_path):
            return

        threading.Thread(
            target=self.callback,
            args=(file_path,),
            daemon=True,
        ).start()


class DownloadWatcher(QObject):
    file_ready = pyqtSignal(dict)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder
        self.observer: Observer | None = None

    def start_watching(self) -> None:
        if self.observer is not None and self.observer.is_alive():
            return

        self.folder.mkdir(parents=True, exist_ok=True)
        handler = NewFileHandler(self.process_file)

        self.observer = Observer()
        self.observer.schedule(handler, str(self.folder), recursive=False)
        self.observer.start()

    def stop_watching(self) -> None:
        if self.observer is None:
            return

        self.observer.stop()
        self.observer.join(timeout=5)
        self.observer = None

    def process_file(self, file_path: Path) -> None:
        if not wait_until_complete(file_path):
            return

        self.file_ready.emit(classify_file(file_path))


def wait_until_complete(
    file_path: Path,
    attempts: int = 20,
    interval: float = 0.5,
) -> bool:
    previous_size = -1
    stable_count = 0

    for _ in range(attempts):
        if not file_path.exists() or not file_path.is_file():
            return False

        try:
            current_size = file_path.stat().st_size
        except OSError:
            return False

        if current_size == previous_size:
            stable_count += 1
        else:
            stable_count = 0

        if stable_count >= 3:
            return True

        previous_size = current_size
        time.sleep(interval)

    return False
