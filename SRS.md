# Sort Pilot Software Requirements

## Product scope

Sort Pilot manually organizes safe top-level files from a Windows Desktop and Downloads directory. Classification is performed locally with bounded extraction and a role-aware Gemma model. The user reviews every proposed path before a move.

## Functional requirements

| ID | Requirement |
| --- | --- |
| FR-001 | Provide tray actions for Desktop, Downloads, both folders, user-type selection, Undo, and quit. |
| FR-002 | Support teacher, student, and office-worker role templates and allow changing the role while idle. |
| FR-003 | Reject unsafe, executable, temporary, unsupported, `.zip`, and `.winmd` candidates before extraction. |
| FR-004 | Partition valid cached files before content extraction and LLM startup. |
| FR-005 | Extract bounded text from supported documents and Markdown/code sources from IPYNB without notebook outputs. |
| FR-006 | Extract bounded image OCR and optional local object evidence. |
| FR-007 | Mark failed or empty supported-content extraction as `기타/확인필요` without invoking or caching the LLM result. |
| FR-008 | Send no more than five files per local LLM request and retry missing results up to two times. |
| FR-009 | Save each validated LLM result to cache immediately rather than waiting for the full batch. |
| FR-010 | Accept only safe relative organization paths with two or three components and an allowed role root. |
| FR-011 | Reject full filenames, filename stems with extensions, generic topics, and ungrounded topic output. |
| FR-012 | Present one editable organization-path column and require explicit final approval. |
| FR-013 | Preserve original filenames and resolve destination collisions with numeric suffixes. |
| FR-014 | Roll back completed moves if a later move in the same batch fails. |
| FR-015 | Persist move history atomically and restore the newest active batch through Undo. |
| FR-016 | Stop extraction workers and the local model process during application shutdown. |
| FR-017 | Before first LLM classification, obtain explicit Gemma-terms consent and install the pinned model and llama.cpp runtime with progress and cancellation. |
| FR-018 | Verify downloaded model/runtime artifacts by exact size and SHA-256 before use. |

## Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-001 | File contents and model prompts must remain on the local device. |
| NFR-002 | The model server must bind only to `127.0.0.1`. |
| NFR-003 | Model/runtime installation must verify artifacts against pinned sizes and SHA-256 digests. |
| NFR-004 | A failed file must not abort other files in the session. |
| NFR-005 | Cancellation must not expose a partial move preview. |
| NFR-006 | Persistent cache/history writes must use atomic replacement. |
| NFR-007 | The UI event loop must remain responsive during extraction and LLM inference. |
| NFR-008 | Only one application instance may run at a time. |
| NFR-009 | After first-use installation, classification must run without network access and keep all model prompts local. |

## Excluded legacy scope

The current product does not include deterministic Tier-1 destination rules, Naive Bayes scoring or training, SQLite decision/review storage, background watching, topic-profile management, sample calibration, pretrained word-vector matching, or flat-folder hierarchy migration.

## Acceptance checks

- An invalid PDF yields `기타/확인필요` without a cache entry.
- An IPYNB contributes cell source text and never output text.
- `.winmd` and `.zip` files never enter extraction.
- Cached files do not start another extraction or LLM request.
- Six uncached files produce one five-file request and one one-file request.
- Missing items are retried and unresolved items fall back safely.
- A folder equal to the complete filename or containing the filename extension is rejected.
- Approved moves preserve the original name and can be undone after restart.
- A first classification without a local model presents terms consent and cancellable installation progress.
- Refused, cancelled, corrupt, or failed installation does not start file classification.
