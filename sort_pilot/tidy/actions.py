from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .store import Store


def collision_free(path: Path) -> Path:
    if not path.exists(): return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists(): return candidate
        index += 1


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


class Executor:
    def __init__(self, store: Store, dry_run=True, allow_cloud=False):
        self.store, self.dry_run, self.allow_cloud = store, dry_run, allow_cloud

    def execute(self, source: Path, root: Path, category: str, decision_id=None) -> Path:
        if not self.allow_cloud and any(x in {p.lower() for p in source.parts} for x in ("onedrive", "dropbox", "google drive")):
            raise PermissionError("Cloud-sync moves are disabled")
        destination = collision_free(root / category / source.name)
        if self.dry_run:
            self.store.journal("dryrun", source, destination, decision_id); return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.drive.lower() == destination.drive.lower(): os.replace(source, destination)
        else:
            shutil.copy2(source, destination)
            if _hash(source) != _hash(destination): raise OSError("Cross-volume verification failed")
            source.unlink()
        self.store.journal("move", source, destination, decision_id); return destination

    def undo(self, journal_id: int) -> Path:
        row = self.store.db.execute("SELECT * FROM journal WHERE id=? AND reversible=1", (journal_id,)).fetchone()
        if not row or row["op"] != "move": raise ValueError("Journal entry is not reversible")
        src, dst = collision_free(Path(row["src"])), Path(row["dst"])
        src.parent.mkdir(parents=True, exist_ok=True); os.replace(dst, src)
        self.store.db.execute("UPDATE journal SET reversible=0 WHERE id=?", (journal_id,)); self.store.journal("undo", dst, src)
        return src

