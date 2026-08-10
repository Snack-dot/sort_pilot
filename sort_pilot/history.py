from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .models import FileOperation


class HistoryStore:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS operations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        batch_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        undone INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )"""
                )

    def record(self, batch_id: str, operation: FileOperation) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO operations(batch_id, source, destination) VALUES (?, ?, ?)",
                    (batch_id, operation.source, operation.destination),
                )

    def latest_batch(self) -> tuple[str, list[FileOperation]] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT batch_id FROM operations WHERE undone = 0 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            batch_id = str(row[0])
            rows = connection.execute(
                "SELECT source, destination FROM operations WHERE batch_id = ? AND undone = 0 ORDER BY id DESC",
                (batch_id,),
            ).fetchall()
        return batch_id, [FileOperation(source, destination) for source, destination in rows]

    def mark_undone(self, batch_id: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("UPDATE operations SET undone = 1 WHERE batch_id = ?", (batch_id,))
