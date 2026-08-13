# Function and Ownership Map

This map covers every class and function under `sort_pilot/`. Source docstrings are the canonical function-level documentation; this file explains placement, ownership, and call relationships.

## Primary application flow

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `run` | `sort_pilot/app.py` | Creates Qt, acquires the single-instance lock, validates the tray, and enters the event loop; called by `main.py`. |
| `AppController.__init__` | `sort_pilot/app.py` | Wires history, queue signals, paths, and tray actions. |
| `start` | `sort_pilot/app.py` | Shows the tray and reports successful history migration. |
| `organize_desktop`, `organize_downloads`, `organize_all` | `sort_pilot/app.py` | Tray callbacks selecting one or both source roots. |
| `_desktop_folder` | `sort_pilot/app.py` | Resolves Desktop through `QStandardPaths`. |
| `_organize_existing_files` | `sort_pilot/app.py` | Collects safe paths and starts one queue session. |
| `_show_progress`, `_update_progress`, `_close_progress` | `sort_pilot/app.py` | Own the cancellable analysis progress dialog. |
| `_analysis_completed`, `_analysis_cancelled` | `sort_pilot/app.py` | Consume final queue signals; errors are reported and only complete successful sessions reach preview. |
| `_set_busy` | `sort_pilot/app.py` | Disables conflicting tray actions during analysis. |
| `_show_preview`, `_destination_root` | `sort_pilot/app.py` | Convert approved UI rows into allowed-root move operations. |
| `undo`, `quit` | `sort_pilot/app.py` | Restore the latest batch or shut down workers and Qt safely. |

## Queue and worker ownership

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `_WorkerSignals` | `sort_pilot/analysis_queue.py` | Typed cross-thread result/error/finished signal carrier. |
| `_AnalysisJob.__init__` | `sort_pilot/analysis_queue.py` | Captures one immutable indexed path job and its session token. |
| `_AnalysisJob.run` | `sort_pilot/analysis_queue.py` | Runs one classification, contains per-file failure, and always signals completion; invoked by Qt. |
| `_AnalysisJob._thread_analyzer` | `sort_pilot/analysis_queue.py` | Creates/reuses one analyzer per pool thread and analyzer factory. |
| `BatchAnalysisController.__init__` | `sort_pilot/analysis_queue.py` | Creates a private `QThreadPool`, default maximum two threads, and signal wiring. |
| `busy` | `sort_pilot/analysis_queue.py` | Exposes whether a valid session token exists. |
| `start` | `sort_pilot/analysis_queue.py` | Deduplicates paths, indexes them, and enqueues jobs while preserving input order. |
| `cancel` | `sort_pilot/analysis_queue.py` | Invalidates the token and clears queued jobs so partial output cannot escape. |
| `shutdown` | `sort_pilot/analysis_queue.py` | Cancels and waits for in-flight QRunnables during app exit. |
| `_unique_paths` | `sort_pilot/analysis_queue.py` | Resolves and case-normalizes platform paths for session deduplication. |
| `_on_result`, `_on_error`, `_on_finished` | `sort_pilot/analysis_queue.py` | Main-thread collectors that ignore stale tokens, update progress, and emit ordered final output. |

## Classifier adapter and public API

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `FileAnalyzer.analyze` | `sort_pilot/classifier.py` | Protocol boundary used by scanner/queue and test analyzers. |
| `RuleBasedAnalyzer.analyze` | `sort_pilot/classifier.py` | Safe filename/extension fallback producing `FileSuggestion`. |
| `RuleBasedAnalyzer._clean_name` | `sort_pilot/classifier.py` | Normalizes the compatibility-only suggested filename. |
| `LocalPipelineAnalyzer.__init__` | `sort_pilot/classifier.py` | Creates a worker-local `Pipeline`, or retains fallback only if unavailable. |
| `LocalPipelineAnalyzer.analyze` | `sort_pilot/classifier.py` | Converts engine decisions to the app's stable model. |
| `analyze_json` | `sort_pilot/classifier.py` | Public single-file `{filepath, folder}` dictionary contract. |
| `analyze_many_json` | `sort_pilot/classifier.py` | Public ordered `{"results": [...]}` dictionary contract. |
| `LocalPipelineAnalyzer.close` | `sort_pilot/classifier.py` | Releases the pipeline's worker-owned store connection. |

## Candidate, preview, and move layer

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `is_safe_candidate` | `sort_pilot/filters.py` | Rejects folders, temporary files, shortcuts, executables, and scripts. |
| `collect_candidates` | `sort_pilot/scanner.py` | Fast top-level path collection used by the app before background analysis. |
| `scan_folder` | `sort_pilot/scanner.py` | Compatibility synchronous analyzer used by scripts/tests. |
| `PreviewDialog.__init__` | `sort_pilot/preview.py` | Builds current/root/folder/move controls for completed suggestions. |
| `_checked_item`, `approved_changes`, `_confirm` | `sort_pilot/preview.py` | Create approval controls, translate rows to `ApprovedFileMove`, and require final confirmation. |
| `build_operation` | `sort_pilot/organizer.py` | Preserves original filename, validates folder, and selects collision-free destination. |
| `execute_batch` | `sort_pilot/organizer.py` | Moves atomically at batch level; reverses completed moves on failure. |
| `undo_latest` | `sort_pilot/organizer.py` | Restores newest active batch and removes only recorded empty directories. |
| `_safe_folder`, `_available_path` | `sort_pilot/organizer.py` | Sanitize untrusted folder text and choose a safe destination. |
| `_missing_directories`, `_remove_empty_directories` | `sort_pilot/organizer.py` | Track and safely clean directories created by a batch. |

## Models, history, tray, and process lock

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `FileSuggestion.source`, `to_dict` | `sort_pilot/models.py` | Path and serialization helpers for the classifier result model. |
| `ApprovedFileMove` | `sort_pilot/models.py` | Immutable user-approved root/folder selection. |
| `FileOperation.source_path`, `destination_path` | `sort_pilot/models.py` | Path helpers for reversible concrete moves. |
| `HistoryStore.__init__` | `sort_pilot/history.py` | Opens/creates JSON history and runs one-time legacy migration. |
| `record`, `record_created_directories` | `sort_pilot/history.py` | Persist completed operations and batch-created folders. |
| `latest_batch`, `mark_undone` | `sort_pilot/history.py` | Supply Undo data and deactivate restored/rolled-back batches. |
| `_legacy_data` | `sort_pilot/history.py` | Reads, closes, and converts the latest active SQLite batch without modifying it. |
| `_read`, `_write`, `_batch` | `sort_pilot/history.py` | Validate, atomically persist, and create/find JSON batch records. |
| `TrayIcon.__init__`, `set_busy` | `sort_pilot/tray.py` | Construct actions and gate conflicting actions during analysis. |
| `notify`, `show`, `hide`, `_icon` | `sort_pilot/tray.py` | Tray presentation and generated icon helpers. |
| `SingleInstanceLock.__init__`, `acquire`, `release` | `sort_pilot/instance_lock.py` | Own the process-level Qt lock used by `run`. |

## Engine orchestration and persistence

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `Pipeline.__init__` | `classifier_engine/pipeline.py` | Creates config, model, worker-local store, and Tier 3 extension point. |
| `categories`, `classify`, `safe_classify`, `close` | `classifier_engine/pipeline.py` | Discover categories, run/persist tiered classification, contain errors, and release storage. |
| `Store.__init__`, `close` | `classifier_engine/store.py` | Own a WAL/busy-timeout SQLite connection per pipeline worker. |
| `now`, `enqueue`, `pending`, `mark` | `classifier_engine/store.py` | Timestamp and persistent queue utilities retained for engine tooling. |
| `record_decision`, `journal` | `classifier_engine/store.py` | Persist decisions/review state and engine action journals. |
| `Config.load`, `Config.save`, `data_dir` | `classifier_engine/config.py` | Manage engine settings and legacy-compatible `%APPDATA%\tidy` storage. |
| `load_rules`, `evaluate` | `classifier_engine/tier1.py` | Load/evaluate ordered deterministic filename and extension rules. |

## Extraction and local media functions

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `normalize_filename`, `tokenize` | `classifier_engine/extract.py` | Normalize names and produce Korean/Latin lexical features. |
| `_read_text`, `_docx`, `_archive`, `_pdf`, `_pptx`, `_xlsx` | `classifier_engine/extract.py` | Bounded local text extraction by file type. |
| `_image_features` | `classifier_engine/extract.py` | Route photo/screenshot/ambiguous images and create metadata features. |
| `_ocr_engine`, `_ocr` | `classifier_engine/extract.py` | Lazily create one RapidOCR instance per worker thread and extract bounded tokens. |
| `extract` | `classifier_engine/extract.py` | Orchestrate filename, text, image, OCR, and optional object features into `FeatureVector`. |
| `is_processable`, `is_stable` | `classifier_engine/extract.py` | Engine-level exclusions and file-settle checks. |
| `_iou`, `postprocess`, `derived`, `infer` | `classifier_engine/vision.py` | ONNX object inference, NMS, and derived object/count/pair features. |

## Model, learning, and auxiliary engine actions

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `NaiveBayesModel.__init__`, `load`, `save` | `classifier_engine/model.py` | Own and atomically persist local category/token weights. |
| `apply`, `score` | `classifier_engine/model.py` | Apply feedback deltas and produce explained, margin-gated decisions. |
| `feedback`, `bootstrap`, `calibrate` | `classifier_engine/learning.py` | Update weights, seed from organized folders, and select empirical thresholds. |
| `collision_free`, `_hash` | `classifier_engine/actions.py` | Engine-tool collision and cross-volume integrity helpers. |
| `Executor.__init__`, `execute`, `undo` | `classifier_engine/actions.py` | Dry-run-safe engine action execution and journal reversal; separate from app approval moves. |
| `reconcile` | `classifier_engine/watch.py` | Optional tooling reconciliation into the persistent engine queue; not used by the manual app. |

## Engine data contracts

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `Feature` | `classifier_engine/types.py` | Weighted token plus extraction source. |
| `FeatureVector.to_dict` | `classifier_engine/types.py` | Serialize bounded file features for storage/evaluation. |
| `Decision` | `classifier_engine/types.py` | Category, scores, action gate, tier, and explanation. |
| `Classifier.classify` | `classifier_engine/types.py` | Protocol for optional higher-tier local classifiers. |
| `Tier3Stub.classify` | `classifier_engine/types.py` | Current no-op Tier 3 extension point. |
| `path_id` | `classifier_engine/types.py` | Derives versioned SHA-1 identity from resolved path metadata. |

## Maintenance rule

Any new or renamed callable under `sort_pilot/` must include a source docstring and be added to the relevant table above. The test/documentation audit should fail review if either layer is missing.
