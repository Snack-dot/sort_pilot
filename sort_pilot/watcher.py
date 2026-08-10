from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _CreatedHandler(FileSystemEventHandler):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.callback(Path(event.src_path))


class FolderWatcher(QObject):
    file_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder
        self._observer: Observer | None = None

    @property
    def running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        handler = _CreatedHandler(self._wait_and_emit)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.folder), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        observer = self._observer
        self._observer = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=3)

    def _wait_and_emit(self, path: Path) -> None:
        try:
            previous = -1
            stable = 0
            for _ in range(30):
                if not path.exists():
                    time.sleep(0.5)
                    continue
                size = path.stat().st_size
                stable = stable + 1 if size == previous else 0
                if stable >= 2:
                    self.file_ready.emit(path)
                    return
                previous = size
                time.sleep(0.5)
            self.error.emit(f"파일 저장 완료를 확인하지 못했습니다: {path.name}")
        except OSError as exc:
            self.error.emit(str(exc))

