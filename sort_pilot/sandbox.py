from __future__ import annotations

from pathlib import Path


class SandboxViolationError(PermissionError):
    """Raised when a user-file operation escapes the configured sandbox."""


def default_sandbox_root() -> Path:
    """Return the only user-file root used by the desktop application."""
    return Path.home() / "Downloads" / "sandbox"


def require_in_sandbox(path: Path, sandbox_root: Path, *, label: str = "path") -> Path:
    """Resolve and return a path only when it stays inside the sandbox root."""
    root = Path(sandbox_root).expanduser().resolve()
    candidate = Path(path).expanduser().resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise SandboxViolationError(
            f"{label} is outside the sandbox: {candidate} (sandbox: {root})"
        )
    return candidate


def require_sandbox_file(path: Path, sandbox_root: Path) -> Path:
    """Return one existing regular file inside the sandbox."""
    candidate = require_in_sandbox(path, sandbox_root, label="source file")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate
