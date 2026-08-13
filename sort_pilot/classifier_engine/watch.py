from __future__ import annotations

from pathlib import Path

from .extract import is_processable
from .store import Store, now


def reconcile(store: Store, folders: list[Path], exclusions=()) -> int:
    """Reconcile changed files into the engine's persistent queue for tooling."""
    added = 0
    for folder in folders:
        if not folder.exists(): continue
        for path in folder.iterdir():
            if not is_processable(path, exclusions): continue
            stat = path.stat()
            seen = store.db.execute("SELECT mtime,size FROM seen WHERE path=?", (str(path),)).fetchone()
            if not seen or (seen["mtime"], seen["size"]) != (stat.st_mtime, stat.st_size):
                store.enqueue(path); added += 1
            store.db.execute("INSERT OR REPLACE INTO seen(path,mtime,size,seen_at) VALUES (?,?,?,?)", (str(path), stat.st_mtime, stat.st_size, now()))
    store.db.commit(); return added
