from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import FileOperation


class HistoryStore:
    """Small JSON-backed operation history used for restart-safe Undo."""

    def __init__(self, history_path: Path) -> None:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path = history_path
        if not self.history_path.exists():
            self._write({"version": 1, "batches": []})

    def record(self, batch_id: str, operation: FileOperation) -> None:
        data = self._read()
        batch = self._batch(data, batch_id)
        batch["operations"].append(
            {"source": operation.source, "destination": operation.destination}
        )
        self._write(data)

    def record_created_directories(self, batch_id: str, directories: list[Path]) -> None:
        if not directories:
            return
        data = self._read()
        batch = self._batch(data, batch_id)
        known = set(batch["created_directories"])
        for directory in directories:
            value = str(directory)
            if value not in known:
                batch["created_directories"].append(value)
                known.add(value)
        self._write(data)

    def latest_batch(self) -> tuple[str, list[FileOperation], list[Path]] | None:
        data = self._read()
        for batch in reversed(data["batches"]):
            if not batch.get("undone", False) and batch.get("operations"):
                operations = [
                    FileOperation(item["source"], item["destination"])
                    for item in reversed(batch["operations"])
                ]
                directories = [Path(value) for value in batch.get("created_directories", [])]
                return str(batch["batch_id"]), operations, directories
        return None

    def mark_undone(self, batch_id: str) -> None:
        data = self._read()
        for batch in data["batches"]:
            if batch.get("batch_id") == batch_id:
                batch["undone"] = True
                self._write(data)
                return

    def _read(self) -> dict:
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"작업 기록을 읽을 수 없습니다: {self.history_path}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("batches"), list):
            raise RuntimeError(f"작업 기록 형식이 올바르지 않습니다: {self.history_path}")
        return data

    def _write(self, data: dict) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.history_path.parent,
            prefix=f"{self.history_path.stem}-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.history_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    @staticmethod
    def _batch(data: dict, batch_id: str) -> dict:
        for batch in data["batches"]:
            if batch.get("batch_id") == batch_id:
                return batch
        batch = {
            "batch_id": batch_id,
            "operations": [],
            "created_directories": [],
            "undone": False,
        }
        data["batches"].append(batch)
        return batch
