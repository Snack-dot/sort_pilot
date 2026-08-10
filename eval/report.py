from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path


def export(db_path: Path, output: Path) -> None:
    db = sqlite3.connect(db_path); db.row_factory = sqlite3.Row
    rows = db.execute("SELECT tier,extractor_ms,peak_rss_mb,margin,n_eff,action,created_at FROM decisions").fetchall()
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream); writer.writerow(rows[0].keys() if rows else ["tier", "extractor_ms", "peak_rss_mb", "margin", "n_eff", "action", "created_at"])
        writer.writerows(tuple(row) for row in rows)


if __name__ == "__main__": export(Path(sys.argv[1]), Path(sys.argv[2]))

