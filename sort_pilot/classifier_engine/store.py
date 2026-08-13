from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue(id INTEGER PRIMARY KEY,path TEXT NOT NULL UNIQUE,enqueued_at TEXT NOT NULL,attempts INTEGER DEFAULT 0,state TEXT DEFAULT 'pending',not_before TEXT);
CREATE TABLE IF NOT EXISTS seen(path TEXT PRIMARY KEY,mtime REAL NOT NULL,size INTEGER NOT NULL,file_id TEXT,seen_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY,file_id TEXT NOT NULL,path TEXT NOT NULL,tier TEXT NOT NULL,predicted TEXT,margin REAL,n_eff REAL,action TEXT NOT NULL,features TEXT NOT NULL,explanation TEXT,extractor_ms TEXT,peak_rss_mb REAL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY,decision_id INTEGER,op TEXT NOT NULL,src TEXT,dst TEXT,model_deltas TEXT,reversible INTEGER DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS review_queue(decision_id INTEGER PRIMARY KEY,resolved_at TEXT,resolution TEXT);
CREATE INDEX IF NOT EXISTS idx_queue_state ON queue(state,not_before);
CREATE INDEX IF NOT EXISTS idx_journal_time ON journal(created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_file ON decisions(file_id);
"""


def now() -> str:
    """Return a timezone-aware UTC timestamp for persisted records."""
    return datetime.now(timezone.utc).isoformat()


class Store:
    """SQLite persistence for classifier decisions, queues, and journals."""

    def __init__(self, path: Path):
        """Open a thread-owned WAL connection with a bounded busy wait."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.db.close()

    def enqueue(self, path: Path) -> None:
        """Insert a path into the persistent engine queue if absent."""
        self.db.execute("INSERT OR IGNORE INTO queue(path,enqueued_at) VALUES (?,?)", (str(path), now()))
        self.db.commit()

    def pending(self) -> list[Path]:
        """Return pending paths whose retry delay has elapsed."""
        rows = self.db.execute("SELECT path FROM queue WHERE state='pending' AND (not_before IS NULL OR not_before<=?) ORDER BY id", (now(),))
        return [Path(row[0]) for row in rows]

    def mark(self, path: Path, state: str) -> None:
        """Update one persistent queue item's processing state."""
        self.db.execute("UPDATE queue SET state=? WHERE path=?", (state, str(path)))
        self.db.commit()

    def record_decision(self, vector, decision) -> int:
        """Persist a feature vector and decision, queuing uncertain reviews."""
        cur = self.db.execute("""INSERT INTO decisions(file_id,path,tier,predicted,margin,n_eff,action,features,explanation,extractor_ms,peak_rss_mb,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (vector.file_id, vector.path, decision.tier, decision.category,
            decision.margin, decision.n_eff, decision.action, json.dumps(vector.to_dict(), ensure_ascii=False),
            json.dumps(decision.explanation, ensure_ascii=False), json.dumps(vector.extractor_ms), vector.peak_rss_mb, now()))
        decision_id = int(cur.lastrowid)
        if decision.action in {"suggest", "unsorted"}:
            self.db.execute("INSERT INTO review_queue(decision_id) VALUES (?)", (decision_id,))
        self.db.commit()
        return decision_id

    def journal(self, op: str, src: Path | None, dst: Path | None, decision_id: int | None = None, deltas=None) -> int:
        """Append a reversible engine operation journal entry."""
        cur = self.db.execute("INSERT INTO journal(decision_id,op,src,dst,model_deltas,created_at) VALUES (?,?,?,?,?,?)",
            (decision_id, op, str(src) if src else None, str(dst) if dst else None, json.dumps(deltas or []), now()))
        self.db.commit()
        return int(cur.lastrowid)
