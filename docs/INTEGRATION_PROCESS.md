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
  → thread-local classifier_engine.ClassifierEngine
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

## Hierarchical classifier follow-up

The flat application category was subsequently split into a fixed Korean file-type family and a family-specific semantic topic. Worker extraction now returns reusable records; the main-thread coordinator applies an immutable profile snapshot and current-batch TF-IDF discovery without rereading files. `topic_profiles.json` stores only normalized tags and aggregated example weights.

New tray workflows manage custom folders/tags and run a separately approved flat-folder migration. Discovered topics, learn-only examples, and approved migration groups create or update profiles, but physical folders still appear only during approved moves. Full algorithm, thresholds, persistence, and migration rules are documented in `HIERARCHICAL_TOPICS.md`.

Follow-up verification covered the hierarchical JSON contract, all six fixed type routes, independent same-name profiles per family, user-profile precedence, document/image discovery minimums, preserved migration subpaths, and documentation coverage. The complete suite now passes 24 tests; compilation, dependency consistency, and Git whitespace validation also pass.

The user-assignment follow-up removed the 5-document/10-image proposal gate after it caused small and mixed batches to fall directly into `미분류`. Every unmatched record now receives a checked assignment row. Similar documents/images remain TF-IDF-grouped, and the editable selector can reuse an existing user topic or create a newly named one.

User-assignment verification brings the complete suite to 32 passing tests. An offscreen Qt smoke test also confirmed checked-by-default rows, existing-topic selection, editable new names, and successful approval.

## Full engine-wiring correction

The temporary `RuleBasedAnalyzer`, fallback implementation, `classifier.py`, and compatibility aliases were removed after an integration audit showed that the earlier adapter consumed only extracted terms in the hierarchical workflow. `classifier_engine.analyzer.ClassifierEngine` is now the sole implementation and calls `Pipeline.safe_classify()` for every file.

Contract tests now instantiate a real pipeline and SQLite decision store instead of forcing `pipeline = None`. Engine categories are retained as evidence only. Topic coverage proves that an empty profile store yields `미분류`, a user-created profile supplies the destination name, and an approved operation physically creates that user-named nested folder.

The final topic-policy correction removed seeded semantic profiles and automatic category-to-topic aliases. Version-1 built-ins are migrated out of persisted profile documents, and default coursework/purchase rules now emit evidence marks rather than terminal categories. Only user-created profiles, named/approved TF-IDF proposals, and approved migration groups can select topics.

Final correction verification: 30 automated tests passed, including the real engine running through the Qt analysis queue. Package/test/eval compilation, installed dependency consistency, callable documentation/function-map coverage, and Git whitespace validation also passed.

## Sample-first calibration implementation

The temporary per-batch unmatched proposal table was superseded by a calibration transaction. With an empty profile store, the controller samples at most three safe top-level files from each fixed family across Desktop and Downloads; one or two files still produce a calibration group. Root/extension buckets are randomized in rounds, previously unseen hashed fingerprints are preferred, and no sample is moved.

The classifier now derives discovery granularity from the sample similarity distribution. A family-scoped board lets the user reassign files, rename and tag clusters, split or merge groups, retain existing profiles during recalibration, and exclude unsuitable examples. Profiles are written only after the complete board passes validation.

Google Gemma 3 1B Q4 was selected after the user explicitly rejected Chinese models. Installation is gated by a Gemma-terms dialog; both the 806,058,240-byte GGUF and llama.cpp `b10405` Windows CPU archive have pinned SHA-256 digests. Input is limited to bounded filenames, family names, and extracted top terms. Inference runs for one request on loopback and the child process is terminated in all paths. Refusal, download failure, timeout, or invalid JSON falls back to deterministic TF-IDF labels.

Topic persistence is version 3. Positive example centroids remain compatible with earlier data, while negative centroids record files corrected away from a topic. The final score subtracts `0.65 × negative cosine`; hard tag overrides were removed so repeated corrections can defeat an overly broad tag. Feedback is committed only for files that moved successfully.

The finalized product flow is explicitly two-step. Calibration approval now creates the selected topic directories and moves all non-excluded seed files immediately, using the existing transactional organizer and history journal. Profile construction happens before movement but persistence happens afterward; a movement failure rolls back the seed batch, and a persistence failure invokes Undo before reporting failure. The original top-level roots are then rescanned, naturally excluding the nested seed files, and only remaining candidates reach the normal final review.

Seed profiles were expanded beyond a short tag list. Each file retains up to forty high-weight base terms plus up to 120 strongest unordered co-occurrence pairs, weighted by half the geometric mean of their base weights. Cluster profiles average this evidence; the visible tag editor is prepopulated with up to sixty base terms while pair features remain machine-facing context evidence.
