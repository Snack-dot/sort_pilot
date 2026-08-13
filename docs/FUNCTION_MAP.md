# Function and Ownership Map

This map covers every class and function under `sort_pilot/`. Source docstrings are the canonical function-level documentation; this file explains placement, ownership, and call relationships.

## Primary application flow

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `run` | `sort_pilot/app.py` | Creates Qt, acquires the single-instance lock, validates the tray, and enters the event loop; called by `main.py`. |
| `AppController.__init__` | `sort_pilot/app.py` | Wires history, queue signals, paths, and tray actions. |
| `start`, `calibrate_topics` | `sort_pilot/app.py` | Shows the tray, triggers first-run calibration, and starts manual recalibration from a bounded sample. |
| `organize_desktop`, `organize_downloads`, `organize_all` | `sort_pilot/app.py` | Tray callbacks selecting one or both source roots. |
| `manage_topics`, `migrate_folders` | `sort_pilot/app.py` | Open profile management or start the separately previewed flat-folder migration. |
| `_desktop_folder` | `sort_pilot/app.py` | Resolves Desktop through `QStandardPaths`. |
| `_organize_existing_files` | `sort_pilot/app.py` | Collects safe paths and starts one queue session. |
| `_start_analysis` | `sort_pilot/app.py` | Records the organize/profile/migration mode and starts a shared queue session. |
| `_show_progress`, `_update_progress`, `_close_progress` | `sort_pilot/app.py` | Own the cancellable analysis progress dialog. |
| `_analysis_completed`, `_analysis_cancelled` | `sort_pilot/app.py` | Consume final queue signals; errors are reported and only complete successful sessions reach preview. |
| `_complete_organization`, `_complete_calibration`, `_complete_profile_learning`, `_complete_migration` | `sort_pilot/app.py` | Dispatch extracted records into full review, calibration, learn-only example updates, or prescribed migration previews. |
| `_report_analysis_errors` | `sort_pilot/app.py` | Reports bounded per-file errors without discarding successful records. |
| `_set_busy` | `sort_pilot/app.py` | Disables conflicting tray actions during analysis. |
| `_show_preview`, `_destination_root` | `sort_pilot/app.py` | Convert approved UI rows into allowed-root move operations. |
| `_learn_approved_moves`, `_merge_examples` | `sort_pilot/app.py` | Apply signed profile feedback only after successful moves and merge explicit examples. |
| `_record_suggestion`, `_path_key` | `sort_pilot/app.py` | Adapt hierarchical records and normalize Windows lookup paths. |
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
| `FileAnalyzer.analyze` | `classifier_engine/analyzer.py` | Structural protocol boundary used by scanner, queue, and test analyzers. |
| `ClassifierEngine.__init__` | `classifier_engine/analyzer.py` | Owns the real pipeline, profile store, and topic resolver. |
| `analyze_record` | `classifier_engine/analyzer.py` | Calls `Pipeline.safe_classify`, retains persisted decision metadata as evidence, and deliberately leaves the topic unset. |
| `analyze`, `_suggestion` | `classifier_engine/analyzer.py` | Resolve only user-owned profiles and adapt a record into `FileSuggestion`. |
| `analyze_json`, `analyze_many_json` | `classifier_engine/analyzer.py` | Public single/batch JSON-object contracts backed by real engine decisions. |
| `_decision_reason`, `close` | `classifier_engine/analyzer.py` | Explain recorded engine evidence without naming a topic and release its SQLite connection. |

## Candidate, preview, and move layer

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `is_safe_candidate` | `sort_pilot/filters.py` | Rejects folders, temporary files, shortcuts, executables, and scripts. |
| `collect_candidates` | `sort_pilot/scanner.py` | Fast top-level path collection used by the app before background analysis. |
| `scan_folder` | `sort_pilot/scanner.py` | Compatibility synchronous analyzer used by scripts/tests. |
| `PreviewDialog.__init__` | `sort_pilot/preview.py` | Builds current/root/folder/move controls for completed suggestions. |
| `_checked_item`, `approved_changes`, `_hierarchical_folder`, `_confirm` | `sort_pilot/preview.py` | Keep the type root immutable, translate editable topic paths to `ApprovedFileMove`, and require confirmation. |
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
| `Pipeline.__init__` | `classifier_engine/pipeline.py` | Loads persisted config and creates the model, worker-local store, and Tier 3 extension point. |
| `categories`, `extract_vector`, `classify`, `safe_classify`, `close` | `classifier_engine/pipeline.py` | Enumerate candidates, extract features, persist real Tier-1/Naive Bayes decisions, contain file failures, and release storage. |
| `Store.__init__`, `close` | `classifier_engine/store.py` | Own a WAL/busy-timeout SQLite connection per pipeline worker. |
| `now`, `enqueue`, `pending`, `mark` | `classifier_engine/store.py` | Timestamp and persistent queue utilities retained for engine tooling. |
| `record_decision`, `journal` | `classifier_engine/store.py` | Persist decisions/review state and engine action journals. |
| `Config.load`, `Config.save`, `data_dir` | `classifier_engine/config.py` | Manage engine settings and legacy-compatible `%APPDATA%\tidy` storage. |
| `load_rules`, `evaluate` | `classifier_engine/tier1.py` | Load/evaluate ordered deterministic filename and extension rules. |

## Extraction and local media functions

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `supports_content_analysis` | `classifier_engine/extract.py` | Gate calibration candidates to formats with a bundled semantic-content extractor. |
| `normalize_filename`, `tokenize` | `classifier_engine/extract.py` | Normalize names and produce Korean/Latin lexical features. |
| `_read_text`, `_docx`, `_odt`, `_archive`, `_pdf`, `_pptx`, `_xlsx` | `classifier_engine/extract.py` | Bounded local text extraction by file type. |
| `_image_features` | `classifier_engine/extract.py` | Route photo/screenshot/ambiguous images and create metadata features. |
| `_ocr_engine`, `_ocr` | `classifier_engine/extract.py` | Lazily create one RapidOCR instance per worker thread and extract bounded tokens. |
| `extract` | `classifier_engine/extract.py` | Orchestrate filename, text, image, OCR, and optional object features into `FeatureVector`. |
| `is_processable`, `is_stable` | `classifier_engine/extract.py` | Engine-level exclusions and file-settle checks. |
| `_iou`, `postprocess`, `derived`, `infer` | `classifier_engine/vision.py` | ONNX object inference, NMS, and derived object/count/pair features. |

## Hierarchy, profiles, and TF-IDF

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `route_type`, `hierarchical_folder` | `classifier_engine/hierarchy.py` | Map extension/MIME to one fixed Korean root and build the reserved two-level fallback path. |
| `utc_now`, `normalize_tag`, `validate_topic_name`, `tag_tokens` | `classifier_engine/topics.py` | Normalize profile metadata and reject unsafe/reserved topic names. |
| `TopicProfile`, `pseudo_terms`, `negative_terms` | `classifier_engine/topics.py` | Persist one family-specific topic and expose boosted positive/tag and negative correction evidence. |
| `AnalysisRecord.source`, `folder` | `classifier_engine/topics.py` | Represent reusable extracted terms, persisted engine decision metadata, and current hierarchical assignment. |
| `TopicProposal` | `classifier_engine/topics.py` | Carry an automatic sample cluster, evidence, membership, and aggregate weights into calibration and local label generation. |
| `vector_terms`, `contextual_terms` | `classifier_engine/topics.py` | Retain body/OCR/object terms only and create canonical bounded weighted co-occurrence pairs. |
| `TopicProfileStore.__init__`, `load`, `save` | `classifier_engine/topics.py` | Initialize built-ins and atomically read/write the versioned profile document. |
| `upsert`, `delete`, `new_profile`, `_validate_profiles` | `classifier_engine/topics.py` | Maintain validated independent user profiles; loading migrates legacy built-ins out of version-1 documents. |
| `TopicClassifier.assign_existing` | `classifier_engine/topics.py` | Match only user-created or explicitly user-approved profiles under family-specific thresholds. |
| `discover`, `aggregate_terms` | `classifier_engine/topics.py` | Propose content-backed unmatched records, TF-IDF-group related samples, and calculate persistent example centroids. |
| `_best_profile`, `_tag_matches` | `classifier_engine/topics.py` | Enforce content-only tag matching, signed evidence, and threshold gating. |
| `_idf`, `_tfidf`, `_cosine`, `_centroid`, `_adaptive_threshold`, `_stable_clusters` | `classifier_engine/topics.py` | Provide sparse TF-IDF math, conservative small-batch thresholds, and deterministic similarity-connected groups. |

## Topic and migration UI

### Calibration workflow

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `CalibrationCluster`, `CalibrationDraft` | `sort_pilot/calibration.py` | Hold editable sample membership and the unpersisted calibration transaction. |
| `CalibrationSampler.__init__`, `select`, `remember`, `remember_fingerprints` | `sort_pilot/calibration.py` | Configure the per-family limit, choose source/extension-diverse samples, and atomically remember fingerprints captured before seed moves. |
| `CalibrationSampler._stratified`, `_load_seen`, `fingerprint` | `sort_pilot/calibration.py` | Round-robin randomized buckets, tolerate corrupt state, and hash path metadata without storing readable paths. |
| `CalibrationService.__init__`, `build_draft`, `save_draft`, `profiles_from_draft` | `sort_pilot/calibration.py` | Convert proposals into an editable draft, build rich profiles without side effects, and persist confirmed groups. |
| `CalibrationService.seed_changes` | `sort_pilot/calibration.py` | Convert approved seed membership into immediate same-root hierarchical moves. |
| `CalibrationService.cluster_id`, `fallback_topic` | `sort_pilot/calibration.py` | Share stable opaque IDs with model I/O and provide deterministic top-term names when the LLM is unavailable. |
| `merge_profile_evidence`, `learn_correction` | `sort_pilot/calibration.py` | Merge positive/negative centroids and apply confirmation or A→B correction feedback. |
| `CalibrationFileList` | `sort_pilot/calibration_dialog.py` | Move sample records between cards while retaining record-index identity. |
| `CalibrationFileList.__init__` | `sort_pilot/calibration_dialog.py` | Enables extended selection and cross-card move drag/drop. |
| `ClusterCard.__init__`, `indexes`, `tag_values` | `sort_pilot/calibration_dialog.py` | Render one editable topic and export its current file membership and normalized tags. |
| `FamilyCalibrationPage.__init__`, `_add_card`, `new_group` | `sort_pilot/calibration_dialog.py` | Seed proposed/existing cards and add new topics within one immutable family tab. |
| `FamilyCalibrationPage.split_selected`, `merge_selected`, `export` | `sort_pilot/calibration_dialog.py` | Split or merge user-selected groups and validate nonempty cards for persistence. |
| `CalibrationDialog.__init__`, `_confirm` | `sort_pilot/calibration_dialog.py` | Build family tabs and require every sample to be assigned or explicitly excluded. |
| `ensure_local_model` | `sort_pilot/calibration_dialog.py` | Obtain Gemma-terms consent and run cancellable, progress-reported local installation. |

### Local tag generation

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `DownloadArtifact`, `InstallCancelled` | `sort_pilot/local_tagger.py` | Describe a pinned artifact and distinguish a user cancellation from installation failure. |
| `LocalModelInstaller.__init__`, `ready`, `has_consent` | `sort_pilot/local_tagger.py` | Resolve versioned paths and report exact-model consent/installation readiness. |
| `LocalModelInstaller.record_consent`, `install`, `_download`, `_extract_runtime` | `sort_pilot/local_tagger.py` | Persist consent, stream checksummed artifacts, reject ZIP traversal, and atomically stage llama.cpp. |
| `LocalTagger.__init__`, `propose` | `sort_pilot/local_tagger.py` | Start one loopback-only CPU server, request all cluster labels once, and always terminate it. |
| `LocalTagger._wait_until_ready`, `_post_json`, `_request_payload` | `sort_pilot/local_tagger.py` | Bound server startup, send local JSON, and treat filenames/terms as untrusted prompt data. |
| `LocalTagger._validate_response`, `cluster_id`, `_free_port` | `sort_pilot/local_tagger.py` | Enforce complete strict output, correlate opaque cluster IDs, and allocate a temporary loopback port. |

### Existing topic and migration UI

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `ProfileEditRequest` | `sort_pilot/topic_dialogs.py` | Return one validated profile edit plus learn-only example paths to the app. |
| `ExampleDropList.__init__`, `dragEnterEvent`, `dragMoveEvent`, `dropEvent` | `sort_pilot/topic_dialogs.py` | Accept safe local file drops without moving them. |
| `add_paths`, `paths` | `sort_pilot/topic_dialogs.py` | Deduplicate examples and expose their pending paths. |
| `TopicManagerDialog.__init__`, `_refresh_profiles`, `_load_selected`, `_new_profile` | `sort_pilot/topic_dialogs.py` | Browse independent family profiles and populate new/edit state. |
| `_choose_examples`, `_remove_examples`, `_delete_selected`, `_prepare_save` | `sort_pilot/topic_dialogs.py` | Maintain learn-only examples and validate/save/delete profile configuration. |
| `MigrationCandidate` | `sort_pilot/migration.py` | Describe one safe source, root, family/topic, and preserved relative destination. |
| `collect_migration_candidates` | `sort_pilot/migration.py` | Plan flat-folder hierarchy moves while skipping already hierarchical files. |

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
