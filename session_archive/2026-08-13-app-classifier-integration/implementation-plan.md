# Approved Implementation Plan

## Summary

Integrate the live GitHub `app` branch (`42f92c1` when verified) directly into `architecture-srs-implementation`, while preserving the current classifier JSON API work. The application will use manual Desktop/Downloads organization, a responsive two-worker classification queue, and the local classifier engine renamed from `tidy` to `classifier_engine`.

## Implementation changes

1. **Import the live app architecture**
   - Fetch `origin/app` and use it as the source of truth.
   - Port its tray actions, Desktop/Downloads selection, editable destination folders, original-name preservation, collision handling, JSON history, Undo behavior, and empty-directory cleanup.
   - Remove real-time `watcher.py` usage and the unused `watchdog` dependency.

2. **Rename and integrate the classifier engine**
   - Rename `sort_pilot/tidy` to `sort_pilot/classifier_engine`.
   - Update application, evaluation, test, and documentation imports.
   - Keep `classifier.py` as the app-facing adapter.
   - Preserve the existing `%APPDATA%\tidy` data location so models and decision history survive the package rename.

3. **Lock the public AI interface**
   - Single-file classification returns `{"filepath": "C:/...", "folder": "..."}`.
   - Multi-file classification returns `{"results": [...]}`.
   - Return dictionaries rather than serialized strings and preserve input ordering.
   - Keep `analyze()` as the adapter to `FileSuggestion` and retain rule-based fallback behavior.

4. **Add asynchronous classification**
   - Collect safe candidate paths before expensive analysis.
   - Use a dedicated Qt thread pool limited to two persistent workers.
   - Deduplicate normalized paths within each session.
   - Create and reuse one classifier pipeline and RapidOCR instance per worker.
   - Give each worker a compatible SQLite connection with concurrent-write handling.
   - Show cancellable progress, disable overlapping organization actions, and display one preview after successful completion.
   - Treat cancellation and per-file failures safely and shut workers down cleanly.

5. **History and process safety**
   - Adopt atomic `history.json` persistence.
   - Migrate the latest active legacy SQLite batch on first run and retain the database as backup.
   - Enforce a single running application instance with a Qt lock file and notify on duplicate launch.

## Test plan

- Validate exact single/multiple JSON shapes, forward-slash paths, Unicode folders, fallback behavior, and stable ordering.
- Validate two-worker concurrency, path deduplication, per-worker OCR reuse, cancellation, and partial file failures.
- Validate Desktop/Downloads/all actions, destination selection, folder editing, filename preservation, collisions, rollback, restart-safe Undo, and empty-folder cleanup.
- Validate legacy history migration and single-instance behavior.
- Run the complete automated suite and a manual tray smoke test with representative Korean/English documents and images.

## Defaults and assumptions

- Work remains uncommitted on `architecture-srs-implementation` unless a commit is separately requested.
- Manual organization replaces real-time watching.
- Worker count remains fixed at two for the first implementation.
- No cloud APIs or file uploads are introduced.
