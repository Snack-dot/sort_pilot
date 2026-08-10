from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .history import HistoryStore
from .models import FileOperation, FileSuggestion


def build_operation(suggestion: FileSuggestion, root: Path) -> FileOperation:
    source = suggestion.source.resolve()
    folder = _safe_folder(suggestion.folder)
    name = _safe_name(suggestion.suggested_name, source.suffix)
    destination = _available_path((root.resolve() / folder / name))
    return FileOperation(str(source), str(destination))


def execute_batch(operations: list[FileOperation], history: HistoryStore) -> list[FileOperation]:
    batch_id = uuid.uuid4().hex
    completed: list[FileOperation] = []
    try:
        for operation in operations:
            source = operation.source_path
            destination = operation.destination_path
            if not source.is_file():
                raise FileNotFoundError(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            history.record(batch_id, operation)
            completed.append(operation)
    except Exception:
        for operation in reversed(completed):
            if operation.destination_path.exists() and not operation.source_path.exists():
                operation.source_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(operation.destination_path), str(operation.source_path))
        history.mark_undone(batch_id)
        raise
    return completed


def undo_latest(history: HistoryStore) -> list[FileOperation]:
    latest = history.latest_batch()
    if latest is None:
        return []
    batch_id, operations = latest
    restored: list[FileOperation] = []
    for operation in operations:
        if operation.destination_path.exists() and not operation.source_path.exists():
            operation.source_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(operation.destination_path), str(operation.source_path))
            restored.append(operation)
    history.mark_undone(batch_id)
    return restored


def _safe_folder(folder: str) -> Path:
    parts = [part for part in Path(folder).parts if part not in {"", ".", "..", "/", "\\"}]
    if not parts or Path(folder).is_absolute():
        return Path("기타")
    return Path(*parts)


def _safe_name(name: str, original_suffix: str) -> str:
    candidate = Path(name).name.strip()
    if not candidate:
        candidate = f"정리된_파일{original_suffix}"
    if Path(candidate).suffix.casefold() != original_suffix.casefold():
        candidate = f"{Path(candidate).stem}{original_suffix}"
    return candidate


def _available_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1

