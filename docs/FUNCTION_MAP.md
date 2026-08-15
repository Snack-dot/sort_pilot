# Function and Ownership Map

This map covers every class and function under `sort_pilot/`. Source docstrings are the function-level contract.

## Application workflow

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `run` | `app.py` | Start Qt with a single-instance lock. |
| `AppController.__init__`, `start` | `app.py` | Wire active services and show the tray. |
| `organize_desktop`, `organize_downloads`, `organize_all` | `app.py` | Select the source roots for a manual organization session. |
| `_desktop_folder`, `_organize_existing_files` | `app.py` | Resolve Desktop, collect safe files, partition cache, and start extraction. |
| `_ensure_user_type`, `select_user_type` | `app.py` | Require or change teacher/student/office-worker policy. |
| `_start_analysis`, `_show_progress`, `_update_progress` | `app.py` | Start extraction and maintain the modal progress display. |
| `_analysis_completed`, `_complete_organization`, `_poll_llm_result` | `app.py` | Transfer extracted records to the background local LLM and show complete results. |
| `_report_analysis_errors`, `_analysis_cancelled`, `_close_progress`, `_set_busy` | `app.py` | Contain failures, cancellation, dialogs, and conflicting tray actions. |
| `_show_preview`, `_destination_root` | `app.py` | Validate approved rows, execute moves, and resolve the allowed destination root. |
| `undo`, `quit` | `app.py` | Restore the newest batch or terminate workers/model/Qt safely. |

## Extraction queue

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `_WorkerSignals` | `analysis_queue.py` | Carry result/error/finished events to the Qt main thread. |
| `_AnalysisJob.__init__`, `run`, `_thread_analyzer` | `analysis_queue.py` | Run one extraction with a reusable thread-local analyzer. |
| `BatchAnalysisController.__init__`, `busy`, `start` | `analysis_queue.py` | Own the two-worker pool, deduplicate paths, and enqueue indexed jobs. |
| `cancel`, `shutdown` | `analysis_queue.py` | Invalidate a session, clear queued work, and wait during shutdown. |
| `_unique_paths`, `_on_result`, `_on_error`, `_on_finished` | `analysis_queue.py` | Normalize paths and collect only events belonging to the active session. |

## Extraction adapter and contracts

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `FileAnalyzer.analyze_record` | `classifier_engine/analyzer.py` | Protocol required by background jobs. |
| `ClassifierEngine.__init__`, `analyze_record`, `_safe_extract` | `classifier_engine/analyzer.py` | Load extraction settings, create bounded records, and isolate per-file failures. |
| `analyze`, `_suggestion` | `classifier_engine/analyzer.py` | Preserve the compatibility `FileSuggestion` interface. |
| `analyze_json`, `analyze_many_json`, `close` | `classifier_engine/analyzer.py` | Preserve the public JSON interface and former close lifecycle. |
| `Config`, `Config.load`, `Config.save`, `data_dir` | `classifier_engine/config.py` | Store extraction limits/weights and resolve private local state. |
| `Feature`, `FeatureVector` | `classifier_engine/types.py` | Represent extracted weighted evidence and its partial state. |
| `route_type`, `hierarchical_folder` | `classifier_engine/hierarchy.py` | Map a file to a fixed family and build the compatibility fallback. |
| `AnalysisRecord`, `source`, `folder` | `classifier_engine/topics.py` | Carry content terms into LLM classification and expose path/fallback helpers. |
| `normalize_tag`, `validate_topic_name` | `classifier_engine/topics.py` | Normalize extracted terms and validate folder-path components. |
| `humanize_term`, `vector_terms` | `classifier_engine/topics.py` | Convert bounded body/OCR/object evidence into human-readable LLM input. |

## Content and media extraction

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `supports_content_analysis`, `is_processable` | `classifier_engine/extract.py` | Identify supported semantic formats and reject incomplete/excluded files. |
| `tokenize`, `collocations` | `classifier_engine/extract.py` | Create Korean/Latin terms and bounded PMI n-grams. |
| `_read_text`, `_ipynb`, `_docx`, `_odt`, `_pdf`, `_pptx`, `_xlsx` | `classifier_engine/extract.py` | Extract bounded local text; notebooks omit outputs. |
| `_image_route`, `_ocr_engine`, `_ocr` | `classifier_engine/extract.py` | Choose image OCR routing and reuse thread-local RapidOCR. |
| `extract` | `classifier_engine/extract.py` | Assemble the complete local `FeatureVector`. |
| `_iou`, `postprocess`, `derived`, `infer` | `classifier_engine/vision.py` | Perform optional ONNX object inference, NMS, and object/pair feature derivation. |

## Local model setup and inference

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `ensure_local_model` | `model_setup.py` | Obtain Gemma-terms consent and run cancellable, progress-reported installation. |
| `DownloadArtifact`, `InstallCancelled` | `local_tagger.py` | Describe pinned artifacts and distinguish user cancellation. |
| `LocalModelInstaller.__init__`, `ready`, `has_consent` | `local_tagger.py` | Resolve private paths and report exact-model consent/readiness. |
| `record_consent`, `install`, `_download`, `_extract_runtime` | `local_tagger.py` | Persist consent, verify downloads, reject ZIP traversal, and install atomically. |
| `LocalTagger.__init__`, `classify_files` | `local_tagger.py` | Run one loopback Gemma session and classify files in batches of five. |
| `cancel_file_classification` | `local_tagger.py` | Terminate active inference during shutdown. |
| `_file_request_payload`, `_file_batch_result_schema`, `_parse_file_batch_response` | `local_tagger.py` | Build schema-constrained prompts and map results back to request IDs. |
| `_document_area_map`, `_validated_topic` | `local_tagger.py` | Apply trusted role taxonomy and reject unsafe/ungrounded topics. |
| `_wait_until_ready`, `_post_json`, `_free_port` | `local_tagger.py` | Bound server startup, exchange loopback JSON, and allocate a port. |

## LLM policy and cache

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `ClassificationCache.__init__`, `load`, `save` | `llm_file_classifier.py` | Atomically persist successful content/policy-keyed folders. |
| `LlmFileClassifier.__init__`, `classify` | `llm_file_classifier.py` | Handle extraction fallbacks, invoke the backend, retry, and return ordered suggestions. |
| `partition_cached`, `cache_key` | `llm_file_classifier.py` | Skip expensive analysis for unchanged content under the same policy. |
| `validate_folder`, `_request`, `_suggestion` | `llm_file_classifier.py` | Bound untrusted paths, construct model input, and adapt accepted output. |

## Candidate, preview, and moves

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `is_safe_candidate` | `filters.py` | Reject hidden, temporary, executable, unsupported, ZIP, and WINMD candidates. |
| `collect_candidates` | `scanner.py` | Return safe top-level files without expensive analysis. |
| `PreviewDialog.__init__`, `_checked_item` | `preview.py` | Render role, destination, full organization path, and move approval controls. |
| `approved_changes`, `_organization_path`, `selected_user_type` | `preview.py` | Translate checked rows into validated move requests. |
| `_apply_bulk_location`, `_confirm` | `preview.py` | Apply a destination root to all rows and require final approval. |
| `build_operation`, `execute_batch`, `undo_latest` | `organizer.py` | Create safe operations, execute with rollback, and restore a batch. |
| `_safe_folder`, `_available_path` | `organizer.py` | Reject unsafe paths and choose collision-free destinations. |
| `_missing_directories`, `_remove_empty_directories` | `organizer.py` | Track and remove only empty directories created by a batch. |

## Models, history, tray, and lock

| Symbol | Location | Responsibility |
| --- | --- | --- |
| `FileSuggestion`, `source`, `to_dict` | `models.py` | Hold one suggestion and preserve the stable serialized result keys. |
| `ApprovedFileMove` | `models.py` | Hold one explicit preview approval. |
| `FileOperation`, `source_path`, `destination_path` | `models.py` | Hold one concrete reversible move. |
| `HistoryStore.__init__`, `record`, `record_created_directories` | `history.py` | Initialize history and atomically append operations/directories. |
| `latest_batch`, `mark_undone` | `history.py` | Read and deactivate the latest reversible batch. |
| `_legacy_data`, `_read`, `_write`, `_batch` | `history.py` | Migrate old move history and maintain validated JSON state. |
| `TrayIcon.__init__`, `set_busy`, `set_user_type` | `tray.py` | Create tray actions, gate them during work, and show the role. |
| `notify`, `show`, `hide`, `_icon` | `tray.py` | Present notifications and the generated tray icon. |
| `SingleInstanceLock.__init__`, `acquire`, `release` | `instance_lock.py` | Prevent simultaneous application instances. |

## Maintenance rule

Every new or renamed callable under `sort_pilot/` must have a source docstring and appear in this map. `tests/test_documentation.py` enforces both requirements.
