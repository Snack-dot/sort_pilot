# Function and Ownership Map

This map covers every class and function under `sort_pilot/`. Source docstrings are the canonical function-level documentation; this file explains placement, ownership, and call relationships.

## Primary application flow

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `run` | `sort_pilot/app.py` | Creates Qt, acquires the single-instance lock, validates the tray, and enters the event loop; called by `main.py`. |
| `AppController.__init__` | `sort_pilot/app.py` | Wires history, student/profile stores, queue signals, paths, and tray actions. |
| `start`, `_start_initial_workflow`, `_require_student_profile` | `sort_pilot/app.py` | Show the tray and require persisted student onboarding before every relevant classification or organization flow. |
| `manage_student_profile` | `sort_pilot/app.py` | Edit the atomic fixed-choice student settings. |
| `organize_desktop`, `organize_downloads`, `organize_all` | `sort_pilot/app.py` | Tray callbacks selecting one or both source roots. |
| `manage_topics`, `migrate_folders` | `sort_pilot/app.py` | Open profile management or start the separately previewed flat-folder migration. |
| `_desktop_folder` | `sort_pilot/app.py` | Resolves Desktop through `QStandardPaths`. |
| `_organize_existing_files` | `sort_pilot/app.py` | Collects safe paths and starts one queue session. |
| `_start_analysis` | `sort_pilot/app.py` | Records the organize/profile/migration mode and starts a shared queue session. |
| `_show_progress`, `_update_progress`, `_close_progress` | `sort_pilot/app.py` | Own the cancellable analysis progress dialog. |
| `_analysis_completed`, `_analysis_cancelled` | `sort_pilot/app.py` | Consume final queue signals; errors are reported and only complete successful sessions reach preview. |
| `_complete_organization` | `sort_pilot/app.py` | Require the current student profile, classify subject/template, show the educational preview, execute frozen paths, and store corrections or roll moves back. |
| `_educational_input`, `_classify_educational_records` | `sort_pilot/app.py` | Convert transient extraction records and run cancellable, cache-only E5 plus constrained Gemma work off the Qt main thread. |
| `calibrate_topics`, `_complete_calibration`, `_complete_profile_learning`, `_complete_migration` | `sort_pilot/app.py` | Retained older workflow helpers that are no longer exposed by the student tray. |
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
| `execute_organization_plans` | `sort_pilot/organizer.py` | Converts exact approved educational paths directly into the transactional move executor without reclassification. |
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
| `TrayIcon.__init__`, `set_busy` | `sort_pilot/tray.py` | Construct organization/student-settings actions and gate conflicting actions during analysis. |
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
| `collocations` | `classifier_engine/extract.py` | Extract adjacent bigrams/trigrams whose pointwise mutual information exceeds chance, as additional body terms. |
| `_read_text`, `_docx`, `_odt`, `_archive`, `_pdf`, `_pptx`, `_xlsx` | `classifier_engine/extract.py` | Bounded local text extraction by file type. |
| `_image_features` | `classifier_engine/extract.py` | Route photo/screenshot/ambiguous images and create metadata features. |
| `_ocr_engine`, `_layout_aware_ocr`, `_ocr`, `_ocr_evidence` | `classifier_engine/extract.py` | Lazily create one RapidOCR instance per worker thread, order detected lines by page columns, and retain bounded tokens plus transient subject/template OCR text and layout evidence. |
| `extract` | `classifier_engine/extract.py` | Orchestrate filename, text, image metadata, and layout-aware OCR into `FeatureVector`; the active educational flow does not invoke rejected YOLO/LVIS evidence. |
| `is_processable`, `is_stable` | `classifier_engine/extract.py` | Engine-level exclusions and file-settle checks. |
| `_iou`, `postprocess`, `derived`, `infer` | `classifier_engine/vision.py` | ONNX object inference, NMS, and derived object/count/pair features. |
| `load_vocab`, `doc_vectors`, `semantic_similarity`, `_resolve` | `classifier_engine/embeddings.py` | Lazily load the bundled pretrained word-vector vocabulary, expand YOLO object labels into plain words, and greedily match each document's most distinctive words against their closest counterpart instead of averaging them. |

## Hierarchy, profiles, and TF-IDF

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `route_type`, `hierarchical_folder` | `classifier_engine/hierarchy.py` | Map extension/MIME to one fixed Korean root and build the reserved two-level fallback path. |
| `utc_now`, `normalize_tag`, `validate_topic_name`, `tag_tokens`, `humanize_term` | `classifier_engine/topics.py` | Normalize profile metadata, reject unsafe/reserved topic names, and convert a raw feature token into a human-readable name component. |
| `TopicProfile`, `pseudo_terms`, `negative_terms` | `classifier_engine/topics.py` | Persist one family-specific topic and expose boosted positive/tag and negative correction evidence. |
| `AnalysisRecord.source`, `folder` | `classifier_engine/topics.py` | Represent reusable extracted terms, persisted engine decision metadata, and current hierarchical assignment. |
| `TopicProposal` | `classifier_engine/topics.py` | Carry an automatic sample cluster, evidence, membership, and aggregate weights into calibration and local label generation. |
| `vector_terms`, `contextual_terms` | `classifier_engine/topics.py` | Retain body/OCR/object terms only and create canonical bounded weighted co-occurrence pairs. |
| `TopicProfileStore.__init__`, `load`, `save` | `classifier_engine/topics.py` | Initialize built-ins and atomically read/write the versioned profile document. |
| `upsert`, `delete`, `new_profile`, `_validate_profiles` | `classifier_engine/topics.py` | Maintain validated independent user profiles; loading migrates legacy built-ins out of version-1 documents. |
| `TopicClassifier.assign_existing` | `classifier_engine/topics.py` | Match only user-created or explicitly user-approved profiles under family-specific thresholds. |
| `discover`, `aggregate_terms` | `classifier_engine/topics.py` | Propose content-backed unmatched records, TF-IDF-group related samples, and calculate persistent example centroids. |
| `_best_profile`, `_tag_matches`, `TopicClassifier._semantic_match` | `classifier_engine/topics.py` | Enforce content-only tag matching, signed evidence, threshold gating, and a pretrained-embedding rescue when lexical matching finds nothing. |
| `_idf`, `_tfidf`, `_cosine`, `_centroid`, `_adaptive_threshold`, `_stable_clusters` | `classifier_engine/topics.py` | Provide sparse TF-IDF math, conservative small-batch thresholds, and deterministic similarity-connected groups. |

## Topic and migration UI

### Calibration workflow

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `CalibrationCluster`, `CalibrationDraft`, `CalibrationDraft.surfaced_records` | `sort_pilot/calibration.py` | Hold editable sample membership and the unpersisted calibration transaction, and expose only the records referenced by a surfaced cluster. |
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
| `ensure_semantic_vectors` | `sort_pilot/calibration_dialog.py` | Obtain consent and run cancellable, progress-reported semantic-vocabulary installation. |

### Local tag generation

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `DownloadArtifact`, `InstallCancelled` | `sort_pilot/local_tagger.py` | Describe a pinned artifact and distinguish a user cancellation from installation failure. |
| `LocalModelInstaller.__init__`, `ready`, `has_consent` | `sort_pilot/local_tagger.py` | Resolve versioned paths and report exact-model consent/installation readiness. |
| `LocalModelInstaller.record_consent`, `install`, `_download`, `_extract_runtime` | `sort_pilot/local_tagger.py` | Persist consent, stream checksummed artifacts, reject ZIP traversal, and atomically stage llama.cpp. |
| `LocalTagger.__init__`, `propose` | `sort_pilot/local_tagger.py` | Start one loopback-only CPU server, request all cluster labels once, and always terminate it. |
| `LocalTagger._wait_until_ready`, `_post_json`, `_request_payload` | `sort_pilot/local_tagger.py` | Bound server startup, send local JSON, and treat filenames/terms as untrusted prompt data. |
| `LocalTagger._validate_response`, `cluster_id`, `_free_port` | `sort_pilot/local_tagger.py` | Enforce complete strict output, correlate opaque cluster IDs, and allocate a temporary loopback port. |
| `FastTextSource`, `InstallCancelled` (embeddings) | `sort_pilot/embeddings_installer.py` | Describe one official fastText source and distinguish a user cancellation from installation failure. |
| `EmbeddingsInstaller.__init__`, `ready`, `has_consent`, `record_consent` | `sort_pilot/embeddings_installer.py` | Resolve the target vector path and consent record, and report installation readiness. |
| `EmbeddingsInstaller.install`, `_stream_top_words`, `_build`, `reference_digest` | `sort_pilot/embeddings_installer.py` | Stream only the top-frequency words per language from official sources without downloading the full release, then atomically build and structurally verify the local vector bundle. |

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

## Educational hybrid foundation

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `StudentOnboardingDialog`, `StudentOnboardingDialog.__init__` | `onboarding.py` | Present only fixed occupation, student-type, grade, semester, and catalog metadata choices. |
| `_selected_profile`, `_update_subjects`, `_accept` | `onboarding.py` | Validate fixed selections, show exact catalog candidates, and return a profile for atomic persistence. |
| `StudentType`, `SubjectCatalog`, `SubjectCatalog.__post_init__`, `subjects_for` | `curriculum/catalog.py` | Define the two student types and validate the exact per-type subject constraints loaded from JSON. |
| `load_subject_catalog` | `curriculum/catalog.py` | Load and cache the packaged `KR_STUDENT_2026_MVP_V1` catalog. |
| `Semester`, `StudentProfile`, `StudentProfile.__post_init__`, `allowed_subjects`, `to_dict`, `from_dict` | `curriculum/profiles.py` | Validate and serialize the fixed student occupation, type, grade, semester, and catalog version without migration semantics. |
| `StudentProfileStore.__init__`, `load`, `save` | `curriculum/profiles.py` | Atomically persist the active onboarding profile and report corrupt or stale-catalog state. |
| `default_profile` | `curriculum/profiles.py` | Build a catalog-bounded profile for one student type, grade, and semester. |
| `DecisionSource`, `Template` | `classification/result.py` | Define observable classifier authority and the five fixed user-facing template folders. |
| `CandidateScore`, `CandidateScore.__post_init__` | `classification/result.py` | Carry and validate an inspectable raw candidate score without claiming calibrated probability. |
| `EvidenceContribution`, `EvidenceContribution.__post_init__` | `classification/result.py` | Retain one named, finite structured contribution to an axis decision. |
| `AxisDecision`, `AxisDecision.__post_init__`, `AxisDecision.to_dict` | `classification/result.py` | Represent, validate, and serialize one independently resolved subject/template decision or nullable abstention. |
| `EducationalClassificationResult`, `EducationalClassificationResult.__post_init__` | `classification/result.py` | Combine catalog-bounded axes while keeping rich classification state separate from folder layout. |
| `EducationalClassificationResult.needs_review`, `folder`, `to_dict` | `classification/result.py` | Expose review state, block unresolved folder rendering, render the six-component hierarchy, and serialize complete provenance. |
| `OrganizationPlan`, `OrganizationPlan.__post_init__`, `OrganizationPlan._valid_destination_name`, `OrganizationPlan.from_classification` | `classification/result.py` | Freeze exact source/destination paths only after both bounded axes resolve, accepting only the original filename or its collision suffix. |
| `SubjectProfile`, `SubjectProfile.__post_init__` | `classification/subject.py` | Define and validate one versioned natural-language subject profile. |
| `SubjectEvidence`, `SubjectEvidence.__post_init__`, `SubjectEvidence.embedding_text` | `classification/subject.py` | Keep filename/body text valid and expose natural E5 input without serializing separate lexical evidence. |
| `SubjectClassifier.classify` | `classification/subject.py` | Require local subject implementations to return an observable catalog-bounded axis decision. |
| `eligible_subject_profiles` | `classification/subject.py` | Filter global profiles into the selected student type's JSON-catalog order before scoring. |
| `load_subject_profiles` | `classification/subject.py` | Strictly load natural-language profiles for every exact subject in the packaged catalog. |
| `SubjectTextEncoder`, `SubjectTextEncoder.encode` | `classification/e5.py` | Define the minimal 384-dimensional encoder boundary used by subject ranking and injected tests. |
| `_embedding_matrix` | `classification/e5.py` | Validate and normalize finite nonzero 384-dimensional embedding rows. |
| `FastEmbedE5Encoder`, `FastEmbedE5Encoder.__init__`, `FastEmbedE5Encoder.encode` | `classification/e5.py` | Register and run exact multilingual E5-small through CPU-only FastEmbed, local-cache-only unless download is explicitly allowed. |
| `E5SubjectClassifier`, `E5SubjectClassifier.__init__`, `E5SubjectClassifier._profile_embeddings`, `E5SubjectClassifier._lexical_scores`, `E5SubjectClassifier.classify` | `classification/e5.py` | Cache averaged profile vectors, score bounded Kiwi terms separately against inspectable natural profiles, rank only catalog subjects, and retain each contribution plus top-two margin. |
| `TemplateEvidenceWeights`, `TemplateEvidenceWeights.__post_init__`, `TemplateEvidenceWeights.total`, `TemplateEvidenceWeights.to_dict` | `classification/template.py` | Validate and expose one template profile's separate semantic, filename, lexical, PMI-collocation, OCR/layout, visual, and personal-example weights. |
| `TemplateProfile`, `TemplateProfile.__post_init__` | `classification/template.py` | Keep natural prototypes, structured indicators, evidence weights, fixed label, and version together for one of the five templates. |
| `TemplateEvidence`, `TemplateEvidence.__post_init__`, `TemplateEvidence.embedding_text` | `classification/template.py` | Validate natural and structured template evidence while exposing only natural filename/body text to E5. |
| `TemplateTextEncoder`, `TemplateTextEncoder.encode` | `classification/template.py` | Define the exact 384-dimensional multilingual E5 boundary used by template ranking. |
| `_indicator_score` | `classification/template.py` | Score structured values against one template profile without converting engineered evidence into natural text. |
| `ordered_template_profiles` | `classification/template.py` | Require exactly one profile for each fixed template and restore the fixed template order. |
| `load_template_profiles` | `classification/template.py` | Strictly load the five separate profiles and their complete evidence weights from packaged JSON. |
| `TemplateClassifier`, `TemplateClassifier.__init__`, `TemplateClassifier._profile_embeddings`, `TemplateClassifier._channel_scores`, `TemplateClassifier.classify` | `classification/template.py` | Cache template prototype embeddings, combine seven separately weighted evidence sources, rank exactly five candidates, and retain raw score, margin, and contributions. |
| `CalibrationTargets`, `CalibrationTargets.__post_init__`, `CalibrationTargets.to_dict` | `classification/calibrated_policy.py` | Preserve and validate the user-approved 90% local-precision and 50% Gemma-escalation accuracy targets. |
| `HeldOutAxisResult`, `HeldOutAxisResult.__post_init__` | `classification/calibrated_policy.py` | Hold one finite held-out raw score, margin, correctness label, and explicit-abstention state. |
| `AxisCalibrationReport`, `AxisCalibrationReport.local_precision`, `AxisCalibrationReport.gemma_accuracy`, `AxisCalibrationReport.to_dict` | `classification/calibrated_policy.py` | Retain one axis's thresholds, routing counts, and achieved held-out rates. |
| `CalibratedPolicy`, `CalibratedPolicy.__post_init__`, `CalibratedPolicy.thresholds_for`, `CalibratedPolicy.to_dict` | `classification/calibrated_policy.py` | Centralize independently calibrated subject/template thresholds, approved targets, and policy version without corpus contents. |
| `PolicyCalibrationReport`, `PolicyCalibrationReport.to_dict` | `classification/calibrated_policy.py` | Combine the central policy and aggregate subject/template calibration reports. |
| `_rate`, `_measure_thresholds` (calibrated policy) | `classification/calibrated_policy.py` | Calculate empirical target rates and measure all three routes for one candidate threshold set. |
| `calibrate_axis`, `calibrate_policy` | `classification/calibrated_policy.py` | Exhaustively select the broadest per-axis local and escalation regions satisfying both approved targets. |
| `load_calibrated_policy` | `classification/calibrated_policy.py` | Strictly load the packaged Phase 5 targets and independent subject/template thresholds. |
| `PolicyRoute`, `RoutingThresholds`, `RoutingThresholds.__post_init__` | `classification/policy.py` | Define explicit per-axis authority routes and validate calibrated raw-score/margin gates. |
| `AxisRoutingDecision` | `classification/policy.py` | Preserve the local decision, routing reason, and policy version passed to the next stage. |
| `route_axis` | `classification/policy.py` | Accept decisive local evidence, escalate only plausible ambiguity to Gemma, and abstain on weak evidence. |
| `ClassificationAxis`, `GemmaFallbackCancelled` | `classification/gemma_fallback.py` | Define the exact subject/template fallback axes and explicit cancellation outcome. |
| `BoundedExtractedEvidence`, `BoundedExtractedEvidence.__post_init__`, `BoundedExtractedEvidence.to_prompt_dict` | `classification/gemma_fallback.py` | Reject paths and cap filename, natural text, and structured evidence before local inference. |
| `GemmaFallbackRequest`, `GemmaFallbackRequest.__post_init__`, `GemmaFallbackRequest.supplied_candidates` | `classification/gemma_fallback.py` | Require the saved student profile, admit only Phase 5 Gemma routes, bound subjects to that profile's catalog, and enforce exactly the five fixed templates for the template axis. |
| `GemmaFallbackCache.__init__`, `GemmaFallbackCache.load`, `GemmaFallbackCache.save` | `classification/gemma_fallback.py` | Strictly load and atomically persist local input hashes and validated selections without paths or extracted evidence. |
| `ConstrainedGemmaFallback.__init__`, `ConstrainedGemmaFallback.resolve_many`, `ConstrainedGemmaFallback.cancel` | `classification/gemma_fallback.py` | Resolve ordered ambiguous axes through one cancellable loopback server run with cache hits, bounded batches, per-item progress, and safe Needs Review outcomes. |
| `ConstrainedGemmaFallback.cache_key`, `_request_payload`, `_parse_batch_response`, `_validate_selection` | `classification/gemma_fallback.py` | Hash every model-visible input/version, constrain each numeric position to its supplied labels or Needs Review, and reject invented output. |
| `ConstrainedGemmaFallback._decision`, `_review_decision`, `_finish_as_review` | `classification/gemma_fallback.py` | Preserve ranked local evidence while recording Gemma/cache authority or unresolved review state in the complete axis representation. |
| `ConstrainedGemmaFallback._start_process`, `_wait_until_ready`, `_post_json`, `_raise_if_cancelled`, `_stop_process`, `_free_port` | `classification/gemma_fallback.py` | Run CPU-only Gemma on a temporary loopback port, check cancellation at work boundaries, and always terminate or kill the server. |

## Phase 7 preview, immutable plan, and corrections

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `PersonalExampleVersions`, `OriginalPrediction` | `classification/personal_examples.py` | Validate the relevant catalog/model/profile/policy versions and the two nullable original predictions retained for one correction. |
| `_normalized_embedding`, `PersonalExample` | `classification/personal_examples.py` | Validate a finite normalized E5 vector and one path-free correction containing only the plan-required fields. |
| `AxisPersonalExamplePolicy`, `PersonalExamplePolicy`, `load_personal_example_policy` | `classification/personal_examples.py` | Validate and strictly load the independently calibrated per-axis weight and minimum similarity. |
| `PersonalExampleScores` | `classification/personal_examples.py` | Carry nearest eligible subject and template scores separately. |
| `PersonalExampleStore`, `PersonalExampleStore.__init__`, `PersonalExampleStore.load`, `PersonalExampleStore.save`, `PersonalExampleStore.add` | `classification/personal_examples.py` | Strictly and atomically keep local corrections keyed by fingerprint without storing paths or raw text. |
| `PersonalExampleStore.nearest_scores` | `classification/personal_examples.py` | Return maximum eligible cosine similarity for each approved subject and template label. |
| `PersonalCalibrationCase` | `classification/personal_calibration.py` | Hold one made-up held-out ranking, nearest-example scores, correct label, and channel contribution scale. |
| `PersonalAxisCalibrationReport`, `PersonalExampleCalibrationReport` | `classification/personal_calibration.py` | Report per-axis and combined correction, regression, routing, and approved-target measurements. |
| `_measure_personal_policy`, `calibrate_personal_axis`, `calibrate_personal_examples` | `classification/personal_calibration.py` | Derive conservative independent influence from made-up held-out data while preserving Phase 5 thresholds and approved targets. |
| `EducationalClassificationInput`, `EducationalClassificationOutput` | `classification/service.py` | Bound one source-separated transient evidence input and retain its complete two-axis result plus normalized embedding for preview. |
| `_routed_local_decision` | `classification/service.py` | Finalize authoritative local results or explicit review state while preserving routing provenance. |
| `EducationalClassificationService`, `EducationalClassificationService.classify_many`, `EducationalClassificationService._raise_if_cancelled` | `classification/service.py` | Run E5, nearest personal evidence, independent routing, and constrained Gemma for an ordered educational batch. |
| `ApprovedEducationalPlan`, `ApprovedEducationalPlan.subject_corrected`, `ApprovedEducationalPlan.template_corrected`, `ApprovedEducationalPlan.personal_example` | `educational_preview.py` | Keep the frozen plan with its original result and produce a personal example only for a changed or newly resolved axis. |
| `_user_decision`, `apply_preview_selection` | `educational_preview.py` | Apply exact catalog/five-template user selections while preserving earlier evidence and marking user authority. |
| `_available_destination`, `freeze_organization_plan`, `_confirmation_message` | `educational_preview.py` | Resolve existing and within-batch collisions once, return the immutable approved plan, and show its exact paths in final confirmation. |
| `EducationalPreviewDialog`, `EducationalPreviewDialog.__init__`, `EducationalPreviewDialog._set_read_only`, `EducationalPreviewDialog._axis_selector` | `educational_preview.py` | Build the fixed-choice two-axis review with explicit unresolved state and allowed destination roots. |
| `EducationalPreviewDialog.approved_plans`, `EducationalPreviewDialog._refresh_destinations`, `EducationalPreviewDialog._confirm`, `EducationalPreviewDialog.frozen_plans` | `educational_preview.py` | Require both axes, show the resulting hierarchy, obtain final approval, and expose only paths frozen by that approval. |

## Phase 8 optional evidence and low-end optimization

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `Phase8OptionalEvidence`, `Phase8OptionalEvidence.__post_init__`, `load_phase8_optional_evidence` | `classification/optional_evidence.py` | Strictly load the measured OCR-layout, Kiwi, and PMI selection plus explicit YOLO/LVIS and session-scheduling rejections. |
| `Phase8Case`, `Phase8Case.__post_init__`, `load_phase8_corpus` | `evaluation/phase8.py` | Strictly load one ordered direct made-up Phase 8 corpus with catalog subjects, the five fixed templates, and separate optional evidence channels. |
| `_exact_mcnemar_p_value`, `paired_accuracy` | `evaluation/phase8.py` | Calculate the exact two-sided paired probability and the agreed accuracy-gain/significance decision. |
| `PairedAccuracy`, `PairedAccuracy.baseline_accuracy`, `PairedAccuracy.candidate_accuracy`, `PairedAccuracy.gain`, `PairedAccuracy.passes`, `PairedAccuracy.to_dict` | `evaluation/phase8.py` | Retain paired correctness counts, rates, gain, regressions, exact probability, and gate outcome. |
| `ResourceMeasurement`, `ResourceMeasurement.__post_init__`, `ResourceMeasurement.to_dict` | `evaluation/phase8.py` | Validate and serialize measured P95 latency and peak process memory. |
| `Phase8GateReport`, `Phase8GateReport.latency_ratio`, `Phase8GateReport.passes`, `Phase8GateReport.to_dict` | `evaluation/phase8.py` | Require all three paired accuracy gates plus the agreed latency and memory limits for the complete selected configuration. |

## Student evaluation framework

| Symbol | Location | Responsibility / caller |
| --- | --- | --- |
| `_require_fields`, `_required_text`, `_optional_label`, `_read_document` | `evaluation/corpus.py` | Enforce exact JSON fields and strict text, nullable-label, and ordered-document loading. |
| `CorpusCase`, `CorpusCase.__post_init__`, `CorpusCase.from_dict`, `CorpusCase.to_dict` | `evaluation/corpus.py` | Validate and serialize one made-up corpus case with a catalog-bounded subject and fixed template. |
| `Prediction`, `Prediction.__post_init__`, `Prediction.from_dict`, `Prediction.to_dict` | `evaluation/corpus.py` | Validate and serialize one ordered subject/template prediction, routing sources, corrections, latency, and memory. |
| `load_corpus`, `load_predictions` | `evaluation/corpus.py` | Load nonempty strict corpus and prediction documents without invented join identifiers. |
| `_rate`, `_percentile`, `_measurement` | `evaluation/metrics.py` | Calculate stable aggregate rates, percentiles, and readable resource measurements. |
| `EvaluationReport`, `EvaluationReport.to_dict` | `evaluation/metrics.py` | Hold and serialize only the required Phase 2 measures and total case count. |
| `evaluate_predictions` | `evaluation/metrics.py` | Compare ordered predictions with corpus labels, count unresolved axes as incorrect, and aggregate every required Phase 2 measure. |

## Maintenance rule

Any new or renamed callable under `sort_pilot/` must include a source docstring and be added to the relevant table above. The test/documentation audit should fail review if either layer is missing.
