# Architecture Decision Record

## D1 — Integration base

**Decision:** Implement directly on `architecture-srs-implementation` and import the live GitHub `app` branch behavior.

**Rationale:** The architecture branch already contains the complete local classifier engine and documentation. Moving the app shell into it has lower risk than transplanting the engine onto `app`.

**Constraint:** Preserve the existing uncommitted JSON API changes in `sort_pilot/classifier.py`.

## D2 — Source of truth for the app branch

**Decision:** Use GitHub's live `origin/app`, not the separate local checkout.

**Evidence:** The local checkout was `8b51ce1`; GitHub reported `origin/app` at `42f92c1`. The newer commit adds per-file destination-root selection.

## D3 — Engine package structure

**Decision:** Rename `sort_pilot/tidy` to `sort_pilot/classifier_engine` and retain its modular structure.

**Rationale:** The engine contains distinct extraction, scoring, storage, learning, action, and vision responsibilities. Flattening them into `classifier.py` would create unnecessary coupling. `classifier.py` remains the stable application-facing adapter.

## D4 — Public AI result contract

**Decision:** Return Python dictionaries compatible with JSON:

```python
{"filepath": "C:/absolute/path/file.pdf", "folder": "학교"}
```

Multiple files:

```python
{"results": [{"filepath": "...", "folder": "..."}]}
```

**Details:** Use the key `filepath` exactly, normalize Windows paths to forward slashes, retain input ordering, and keep `analyze() -> FileSuggestion` as the application compatibility layer.

## D5 — App workflow

**Decision:** Adopt `app` branch's manual organization workflow and remove real-time Downloads watching.

**Included behavior:** Desktop-only, Downloads-only, and combined organization; per-file destination-root selection; editable destination folder; original filename preservation; collision handling; explicit approval; Undo and empty-folder cleanup.

## D6 — Classification concurrency

**Decision:** Use a deduplicating queue and exactly two persistent workers.

**Details:** Each worker owns and reuses its classifier pipeline, RapidOCR instance, and SQLite connection. No Qt widget is touched outside the main thread.

**Rationale:** Reconstructing RapidOCR for each image caused repeated ONNX initialization and severe perceived looping. Two workers balance throughput against memory and ONNX CPU contention.

## D7 — Batch user experience

**Decision:** Show a cancellable progress dialog, then one final preview.

**Cancellation:** Stop queued work cooperatively, allow in-flight calls to return safely, discard canceled-session results, and suppress partial preview display.

## D8 — History persistence and migration

**Decision:** Adopt app's atomic JSON history and migrate the latest active batch from the legacy SQLite history on first run.

**Safety:** Leave `history.db` untouched as a backup. If `history.json` already exists, do not overwrite or repeat migration.

## D9 — Single-instance behavior

**Decision:** Enforce one running Sort Pilot instance.

**Rationale:** Two Sort Pilot Python processes were observed. Duplicate instances can double OCR work and race file moves/history writes.

## D10 — Error and fallback behavior

**Decision:** One file's analysis failure must not abort the full batch. The adapter falls back to rule-based classification when the engine is unavailable, fails, or returns no category. Errors remain separate from the required public JSON schema.
