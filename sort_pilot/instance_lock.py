from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QLockFile


class SingleInstanceLock:
    """Process-scoped Qt lock that prevents duplicate Sort Pilot instances."""

    def __init__(self, lock_path: Path) -> None:
        """Create a lock file wrapper at a stable application-data path."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(lock_path))
        self._lock.setStaleLockTime(30_000)
        self.acquired = False

    def acquire(self) -> bool:
        """Try to acquire the application lock without blocking another launch."""
        self.acquired = self._lock.tryLock(100)
        return self.acquired

    def release(self) -> None:
        """Release the lock when this process owns it."""
        if self.acquired:
            self._lock.unlock()
            self.acquired = False
