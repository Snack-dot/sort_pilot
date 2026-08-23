from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .history import HistoryStore
from .models import ApprovedFileMove, FileOperation
from .classification import OrganizationPlan
from .sandbox import require_in_sandbox, require_sandbox_file


def build_operation(
    change: ApprovedFileMove,
    root: Path,
    sandbox_root: Path,
) -> FileOperation:
    """Build a collision-free move while preserving the original filename."""
    source = require_sandbox_file(change.suggestion.source, sandbox_root)
    safe_root = require_in_sandbox(root, sandbox_root, label="destination root")
    parent = safe_root / _safe_folder(change.folder) if change.move_approved else source.parent
    destination = _available_path(parent / change.suggestion.file_name, source)
    safe_destination = require_in_sandbox(destination, sandbox_root, label="destination")
    return FileOperation(str(source), str(safe_destination))


def execute_batch(
    operations: list[FileOperation],
    history: HistoryStore,
    sandbox_root: Path,
) -> list[FileOperation]:
    """Execute moves transactionally and roll back completed moves on failure."""
    safe_operations = _validated_operations(operations, sandbox_root)
    batch_id = uuid.uuid4().hex
    completed: list[FileOperation] = []
    created_directories: list[Path] = []
    try:
        for operation in safe_operations:
            source = operation.source_path
            destination = operation.destination_path
            if not source.is_file():
                raise FileNotFoundError(source)
            if source == destination:
                continue
            missing = _missing_directories(destination.parent)
            destination.parent.mkdir(parents=True, exist_ok=True)
            history.record_created_directories(batch_id, missing)
            created_directories.extend(missing)
            shutil.move(str(source), str(destination))
            completed.append(operation)
            history.record(batch_id, operation)
    except Exception:
        for operation in reversed(completed):
            if operation.destination_path.exists() and not operation.source_path.exists():
                operation.source_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(operation.destination_path), str(operation.source_path))
        _remove_empty_directories(created_directories, sandbox_root)
        history.mark_undone(batch_id)
        raise
    return completed


def execute_organization_plans(
    plans: list[OrganizationPlan],
    history: HistoryStore,
    sandbox_root: Path,
) -> list[FileOperation]:
    """Execute exact approved educational paths without recomputing classification."""
    if not all(isinstance(plan, OrganizationPlan) for plan in plans):
        raise ValueError("교육 조직 계획 목록이 올바르지 않습니다.")
    operations = [
        FileOperation(str(plan.source.resolve()), str(plan.destination.resolve()))
        for plan in plans
    ]
    return execute_batch(operations, history, sandbox_root)


def undo_latest(history: HistoryStore, sandbox_root: Path) -> list[FileOperation]:
    """Restore the newest active batch and remove folders it created if empty."""
    latest = history.latest_batch()
    if latest is None:
        return []
    batch_id, operations, created_directories = latest
    safe_operations = _validated_operations(operations, sandbox_root)
    safe_directories = [
        require_in_sandbox(path, sandbox_root, label="recorded directory")
        for path in created_directories
    ]
    restored: list[FileOperation] = []
    for operation in safe_operations:
        if operation.destination_path.exists() and not operation.source_path.exists():
            operation.source_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(operation.destination_path), str(operation.source_path))
            restored.append(operation)
    _remove_empty_directories(safe_directories, sandbox_root)
    history.mark_undone(batch_id)
    return restored


def _safe_folder(folder: str) -> Path:
    """Convert an untrusted relative folder recommendation into a safe path."""
    parts = [part for part in Path(folder).parts if part not in {"", ".", "..", "/", "\\"}]
    if not parts or Path(folder).is_absolute():
        return Path("기타")
    return Path(*parts)


def _available_path(path: Path, source: Path) -> Path:
    """Return the source itself or the first unused suffixed destination."""
    if path.resolve() == source.resolve():
        return source
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _missing_directories(directory: Path) -> list[Path]:
    """List absent ancestors that a move will create, nearest first."""
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    return missing


def _validated_operations(
    operations: list[FileOperation],
    sandbox_root: Path,
) -> list[FileOperation]:
    """Validate a complete batch before any user file is changed."""
    validated: list[FileOperation] = []
    for operation in operations:
        source = require_in_sandbox(
            operation.source_path,
            sandbox_root,
            label="operation source",
        )
        destination = require_in_sandbox(
            operation.destination_path,
            sandbox_root,
            label="operation destination",
        )
        validated.append(FileOperation(str(source), str(destination)))
    return validated


def _remove_empty_directories(directories: list[Path], sandbox_root: Path) -> None:
    """Remove recorded directories deepest-first, ignoring non-empty paths."""
    for directory in sorted(set(directories), key=lambda path: len(path.parts), reverse=True):
        safe_directory = require_in_sandbox(
            directory,
            sandbox_root,
            label="directory cleanup",
        )
        try:
            safe_directory.rmdir()
        except (FileNotFoundError, OSError):
            continue

