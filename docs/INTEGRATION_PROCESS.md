# App Branch and Classifier Engine Integration Record

## Baseline and source

- Target branch: `architecture-srs-implementation` at `f91b43b` before integration.
- Application source: live `origin/app` at `42f92c1` (`정리 위치 선택 기능 구현`).
- Common ancestor/application baseline: `1899611`.
- Local `sort_pilot-app` checkout was not copied because it was stale at `8b51ce1`.
- Pre-existing uncommitted `classifier.py` JSON-object API work was retained.

The integration was performed behavior-by-behavior rather than with a blind merge because both branches changed application contracts around `AppController`, `FileSuggestion`, history, preview, and organization.

## Changes performed

1. Ported `app` branch's manual Desktop/Downloads/all tray actions, per-file destination-root selection, editable relative folder, original filename preservation, collision handling, JSON history, Undo, and created-folder cleanup.
2. Removed the real-time `watcher.py` path and `watchdog` runtime dependency.
3. Renamed `sort_pilot/tidy` to `sort_pilot/classifier_engine` and updated evaluation/tests/imports. The `%APPDATA%\tidy` storage path remains intentionally unchanged for state compatibility.
4. Retained `classifier.py` as the stable adapter and formalized exact single/multiple JSON-object contracts.
5. Added `analysis_queue.py`: a deduplicating, cancellable `QThreadPool` controller capped at two workers. Results retain input order and cross to Qt only through signals.
6. Changed OCR lifecycle from one `RapidOCR()` per image to one lazy thread-local engine per worker.
7. Configured worker-owned classifier SQLite connections for WAL mode, a 30-second busy timeout, and clean pipeline closure support.
8. Added atomic one-time migration of the latest active `history.db` batch into `history.json`, leaving the legacy database untouched.
9. Added a Qt lock-file guard so a second Sort Pilot launch displays a notice and exits.
10. Added docstrings to every class and function in `sort_pilot/`, plus the complete ownership map in `FUNCTION_MAP.md`.

## Runtime flow

```text
Tray action
  → AppController._organize_existing_files
  → scanner.collect_candidates
  → BatchAnalysisController.start
  → two _AnalysisJob workers
  → thread-local LocalPipelineAnalyzer
  → classifier_engine.Pipeline.safe_classify
  → extract (thread-local RapidOCR when required)
  → ordered FileSuggestion results
  → PreviewDialog
  → organizer.build_operation / execute_batch
  → HistoryStore JSON journal
```

Cancellation invalidates the active session token, removes queued jobs, lets already-running library calls return safely, and discards their results. A canceled session never opens a partial preview.

## Compatibility and data decisions

- Public JSON uses `filepath`, not the internal dataclass key `file_path`.
- Public methods return dictionaries, not serialized JSON text.
- `analyze()` remains compatible with existing UI consumers expecting `FileSuggestion`.
- App move history changes to `history.json`; only the latest active legacy SQLite batch is migrated.
- Classifier decision/model state remains in the existing `tidy` application-data directory.
- Historical watcher sections in `SRS.md` and `ARCHITECTURE.md` are retained with supersession notes.

## Verification performed

- Python compile audit across `sort_pilot`, `tests`, and `eval`.
- Documentation regression tests and AST audit: every class/function under `sort_pilot/` has a docstring and appears in the function map.
- Full automated suite: 19 tests passed.
- `git diff --check` passed; only Git's expected Windows LF-to-CRLF notices were emitted.
- Coverage includes JSON contracts, Unicode/forward-slash paths, queue order/deduplication/two-worker cap, cancellation, OCR reuse, classifier extraction/model behavior, safe moves, collision policy, JSON restart persistence, Undo, and legacy SQLite migration.

## Operational notes

- The progress dialog is application-modal, but classification occurs outside the UI thread.
- Quit cancels queued jobs and waits for in-flight jobs so Qt does not destroy a live thread pool.
- Per-file exceptions are collected and reported without discarding successful suggestions.
- No model or dependency was downloaded during this integration.
