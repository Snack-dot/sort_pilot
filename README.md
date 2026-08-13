# Sort Pilot

Sort Pilot is a Windows system-tray application that analyzes safe files on the Desktop and in Downloads, recommends hierarchical type/topic folders using a fully local classifier, and moves only the files explicitly approved by the user.

## Current workflow

```text
Tray action (Desktop / Downloads / both)
→ safe top-level candidate collection
→ deduplicated two-worker classification queue
→ fixed file type + saved topic matching
→ optional current-batch TF-IDF topic proposal
→ cancellable progress dialog
→ editable destination preview
→ explicit user approval
→ original-name file moves
→ atomic JSON history and restart-safe Undo
```

There is no real-time filesystem watcher in the integrated app. Manual organization avoids repeated background scans, and each worker reuses one local RapidOCR engine rather than initializing ONNX Runtime for every image.

## Public classifier interface

`LocalPipelineAnalyzer` returns Python dictionaries that are directly JSON-compatible.

Single file:

```python
{
    "filepath": "C:/Users/user/Downloads/운영체제과제.pdf",
    "folder": "문서/학교"
}
```

Multiple files:

```python
{
    "results": [
        {"filepath": "C:/Users/user/Downloads/운영체제과제.pdf", "folder": "문서/학교"},
        {"filepath": "C:/Users/user/Downloads/쿠팡영수증.png", "folder": "이미지/금융"}
    ]
}
```

Use `analyze_json(path)` or `analyze_many_json(paths)`. The fixed roots are `문서`, `이미지`, `압축파일`, `오디오`, `동영상`, and `기타`; unmatched topics use `미분류`. The desktop batch UI can additionally propose new TF-IDF topics, but public non-interactive calls never persist an inferred folder without approval.

## Features and safety

- Manual Desktop, Downloads, or combined organization.
- Deterministic top-level type routing with independent topic profiles per type.
- User-created topic names, tags, enable/disable state, and learn-only example files.
- Current-batch TF-IDF topic suggestions for documents (minimum 5) and images (minimum 10).
- Explicit topic naming/approval before a discovered profile is saved or applied.
- Manual previewed migration from flat folders such as `학교` to `문서/학교` or `이미지/학교`.
- Exactly two classification workers; duplicate paths are processed once per session.
- One reusable classifier pipeline, SQLite connection, and RapidOCR instance per worker thread.
- Cancellable progress with no partial preview after cancellation.
- Local document, archive, image, OCR, and optional ONNX object features.
- Editable destination root and relative folder for every file.
- Original filenames are preserved; collisions receive numeric suffixes.
- No move occurs before final approval.
- Completed move batches are stored atomically in `history.json` and can be undone after restart.
- The latest active legacy `history.db` batch is migrated once without modifying the database.
- A Qt lock prevents two Sort Pilot instances from running simultaneously.
- No cloud inference or file upload.

## Setup and verification

Python 3.11 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
python main.py
```

The app has no main window. Right-click the `SP` system-tray icon to organize files, undo the latest batch, or quit.

## Repository layout

```text
main.py                            desktop entry point
sort_pilot/app.py                  tray workflow and UI coordination
sort_pilot/analysis_queue.py       deduplicated two-worker analysis sessions
sort_pilot/classifier.py           public JSON API and app adapter
sort_pilot/classifier_engine/      local extraction, scoring, persistence, learning, vision
sort_pilot/topic_dialogs.py        topic profile and TF-IDF proposal UI
sort_pilot/migration.py            safe flat-folder hierarchy migration planning
sort_pilot/history.py              atomic JSON move history and SQLite migration
sort_pilot/preview.py              destination review and approval
sort_pilot/organizer.py            safe moves, rollback, collision handling, Undo
tests/                             app, queue, contract, and engine tests
docs/FUNCTION_MAP.md               complete function ownership and call-flow map
docs/INTEGRATION_PROCESS.md        app-branch integration record
docs/HIERARCHICAL_TOPICS.md        type/topic model, TF-IDF, profiles, and migration
```

Classifier state intentionally remains under the legacy `%APPDATA%\tidy` directory so the package rename does not orphan learned weights or decisions. Versioned topic profiles are stored atomically in `topic_profiles.json`; no example paths or raw contents are retained. Move history and the single-instance lock use Qt's Sort Pilot application-data directory.

Model binaries are not committed. An optional locally exported model belongs at `data/models/yolov8n.onnx`; provenance requirements are in `THIRD_PARTY.md`.
