# Changelog

## 2026-08-13 — Full classifier-engine wiring

- Removed `classifier.py`, its compatibility alias, and the temporary rule-based/fallback implementation.
- Made the engine-owned `ClassifierEngine` the sole implementation and import path for the queue, synchronous scanner, and JSON API.
- Routed every file through `Pipeline.safe_classify()` and retained the persisted decision ID, tier, action, category, and margin.
- Removed automatic engine-category topic mapping, built-in semantic profiles, and the seed lexicon.
- Converted default coursework/finance rules into evidence marks rather than terminal topic categories.
- Added real-pipeline tests proving fresh files remain `미분류` until a user-created profile or explicitly approved proposal names the topic.

## 2026-08-13 — Hierarchical type/topic classification

- Split flat categories into fixed Korean type roots and independent semantic topics.
- Added atomically persisted user profiles with tags, enable/disable state, and learn-only examples.
- Added dependency-free sparse TF-IDF/cosine topic matching and current-batch discovery.
- Added approval UI for discovered topics and management UI for custom folders/tags.
- Added a separate previewed migration from existing flat folders into the new hierarchy.
- Preserved the public `filepath`/`folder` JSON keys with nested folder values.

## 2026-08-13 — App and classifier-engine integration

- Integrated live `origin/app` behavior into `architecture-srs-implementation`.
- Replaced real-time watching with manual Desktop/Downloads/all organization.
- Renamed `sort_pilot/tidy` to `sort_pilot/classifier_engine` while preserving its data path.
- Added exact single/multiple JSON-object classifier contracts.
- Added a cancellable, deduplicated two-worker Qt analysis queue and per-worker OCR reuse.
- Adopted atomic JSON move history with latest-batch SQLite migration.
- Added single-instance enforcement, full callable docstrings, and `docs/FUNCTION_MAP.md`.

All notable changes to the architecture implementation branch are documented here.

## Unreleased

### Reconciled

- Based the architecture branch on the repository's `main` history.
- Restored the `main.py` plus `sort_pilot/` application layout from `main`.
- Moved the local classifier engine from `src/tidy/` to `sort_pilot/tidy/` and removed the duplicated legacy application directory.
- Preserved the baseline application tests alongside the pipeline-specific test suite.

### Added

- SRS-driven `tidy` package with configuration, feature-vector, pipeline, and deferred Tier 3 interfaces.
- SQLite-backed durable queue, seen index, decision history, review queue, and reversible journal.
- Atomic JSON Naive Bayes model storage, source-weighted scoring, normalized margin gate, and top-feature explanations.
- Korean morphology, bounded text/Office/PDF/archive extraction, screenshot/photo routing, local OCR, and image context features.
- YOLOv8n ONNX preprocessing, inference, NMS, object features, conjunction features, and derived geometry/count signals.
- Bootstrap learning, correction feedback, threshold calibration, collision-safe actions, dry-run behavior, and undo support.
- Evaluation metrics, resource CSV export, packaging metadata, dependency/license register, and automated tests.
- Compatibility adapter preserving the original `classify_file()` response keys.

### Changed

- The original filename/extension classifier now delegates to the new local pipeline when available.
- Project dependencies are pinned and isolated in a local virtual environment.

### Security

- Added ignore rules for local models, learned state, private evaluation corpora, databases, caches, and virtual environments.
- Preserved local-only inference and avoided bypassing TLS certificate validation.
