# Sort Pilot Architecture

## Active design

Sort Pilot has one production classification path. Cheap local extraction prepares bounded evidence, and the local Gemma model makes the final role-aware folder decision.

```text
Tray
  → candidate filter
  → content cache partition
  → extraction queue
      → document text / IPYNB cells / image OCR / optional YOLO
      → AnalysisRecord
  → local Gemma batch classification
  → output validation and per-file cache save
  → editable preview
  → approved move + JSON Undo history
```

The application intentionally has no Tier-1 rules, Naive Bayes scorer, classifier decision database, review queue, profile calibration, semantic-vector installer, or filesystem watcher.

## Boundaries

### Candidate collection

`scanner.collect_candidates()` enumerates top-level files only. `filters.is_safe_candidate()` rejects executable, temporary, unsupported, archive, shortcut, hidden, and incomplete candidates before content analysis.

### Extraction

`BatchAnalysisController` owns an isolated Qt thread pool. Each worker reuses its analyzer and thread-local RapidOCR instance. `ClassifierEngine.analyze_record()` calls only the bounded extractor; it does not perform another classification or write decision state.

The LLM receives the filename separately. `vector_terms()` retains only body, OCR, object, and object-pair extraction evidence. A supported format with failed or empty extraction is marked `content_extraction_failed`.

### Role-aware classification

`LlmFileClassifier` partitions cached content before extraction, converts uncached records into bounded requests, and calls `LocalTagger.classify_files()`. `LocalModelInstaller` performs the consent-gated, checksum-verified first-use installation of Gemma and llama.cpp under the private application data directory. The backend launches Gemma through `llama-server` on loopback only. Requests are batched in groups of five and incomplete output is retried.

Each output must be a relative path of at most three components. Its first component must be allowed by the selected teacher, student, or office-worker template. Topics equal to a full filename/stem, contain an extension, are generic, or are unsupported by extracted evidence are discarded.

### Preview and moves

`PreviewDialog` presents one editable `정리 경로` column. `organizer` validates paths again, preserves original names, handles collisions, rolls back a partially failed batch, and records completed moves in atomic JSON history. Undo uses only this move history.

## Local state

Current state under `%APPDATA%\tidy`:

- `config.json`: extraction limits and evidence weights.
- `classification_cache.json`: successful content/policy keyed LLM results.
- `local_ai/models/`: consent-gated, pinned Gemma GGUF.
- `local_ai/runtimes/`: checksum-verified llama.cpp CPU runtime.
- `local_ai/model_consent.json`: acceptance for the exact configured model terms.

Qt application data stores `history.json` and the single-instance lock. Legacy classifier databases and topic-profile files may remain from old installations but are not opened by current code.

## Failure isolation

- Candidate errors are reported per file without aborting the batch.
- Extractor errors become a partial record and `기타/확인필요`; they are not cached.
- Invalid or missing LLM output becomes `기타/확인필요`.
- Missing AI files trigger the consent/install flow before classification starts.
- LLM cancellation terminates the active server and suppresses partial preview output.
- Move failure rolls back operations already completed in that batch.
