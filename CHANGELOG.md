# Changelog

## 2026-08-16 — Final student-hybrid MVP plan

- Finalized one student-only hierarchy using `중학생`/`고등학생`, grades 1–3, semesters 1–2, a constrained 2026 MVP subject catalog, and exactly five templates: `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Clarified that curriculum material is a practical subject-list reference, not a legal, institutional, timetable, or year-by-year revision engine.
- Defined `Needs Review` as non-folder workflow state and prohibited artificial fallback subjects or a sixth template.
- Preserved superseded prompts and the exploratory ADR under `plans/superseded/`, added the authoritative plan under `plans/`, and archived the complete planning session.
- Recorded mandatory Phase 0 remediation for exploratory contracts that still contain superseded assumptions; the active application remains unchanged.

## 2026-08-16 — Educational hybrid foundation

- Recorded the decision to evolve the existing statistical classifier into a curriculum-constrained middle/high-school hybrid, with local decisions authoritative at high confidence and Gemma restricted to ambiguous per-axis fallback.
- Added versioned onboarding contracts for school level, grade, semester, editable subject candidates, and explicit extracurricular/common/unknown fallbacks.
- Added atomic onboarding-profile persistence with explicit corruption and curriculum-migration reporting.
- Defined the subject-profile, bounded evidence, curriculum filtering, and local subject-classifier interfaces required by the later E5 implementation.
- Added an explicit per-axis policy contract that routes decisive local evidence to acceptance, plausible ambiguity to Gemma, and weak or abstained evidence to review.
- Added an observable multidimensional result contract that keeps subject and activity decisions, scores, margins, evidence, provenance, and review state separate from the rendered folder hierarchy.
- Added the initial `학생/<학교급>/<학년>/<학기>/<과목>/<활동>` renderer and contract tests without changing the active classifier or UI workflow yet.

## 2026-08-16 — Full real-world validation run and reversal

No code changes this session; recorded here so the next reviewer has the full picture of what was actually run against real user data before this branch's fixes were pushed.

- Pushed the 10 commits from the 2026-08-14 recall/precision session to `origin/architecture-srs-implementation` after independent verification (fresh clone, fresh install, integration check).
- Ran the full pipeline end-to-end against a real, non-synthetic `~/Downloads` folder (760 files, previously used only for read-only dry runs) via an ad hoc script driving the same `ClassifierEngine` / `CalibrationService` / `organizer.execute_batch` path the app uses, with the destination review already confirmed by the folder owner beforehand (26 files in a weak/generic cluster excluded and left in place; the remaining 223 unmatched files included).
- Result: 734/734 planned moves succeeded, 26 correctly excluded, 101 topic profiles saved, 107 destination folders created — matching the previously-reviewed dry-run plan exactly.
- Getting to that clean run took three aborted attempts, each caught before any file was touched by a pre-move safety check that reproduces the confirmed exclusion set and hard-aborts (`RuntimeError`) on any mismatch: a diagnostic counting bug (accumulator overwritten instead of summed across multiple same-named clusters), a macOS NFC/NFD Unicode filename-normalization mismatch (real filenames on disk were NFD-decomposed, the confirmed list was NFC), and one borderline file whose cluster assignment wasn't stable run-to-run. The exclusion mechanism was rewritten to match confirmed filenames directly, independent of clustering output, to make the last case a non-issue going forward.
- The folder owner then asked for a full reversal. `organizer.undo_latest` against the batch's `HistoryStore` restored all 734 files to their original paths; the folders it created were removed once empty. `~/Downloads` was confirmed back to its original layout, files-only diff, before and after.
- Operational finding worth carrying forward: `HistoryStore`'s location comes from `QStandardPaths.AppDataLocation`, which is keyed off `QApplication`'s application name (`sort_pilot/app.py` sets `"Sort Pilot"`). A script that constructs `QApplication` without calling `setApplicationName` gets a different AppData folder (named after the script file), so its move history is invisible to the packaged app's own Undo action. Anything that drives `organizer.execute_batch` outside `app.py`'s entry point should set the same application name first, or Undo silently splits across two history files.

## 2026-08-14 — Real-data recall/precision correction and semantic rescue

- Fixed near-zero real-world topic coverage: rebalanced co-occurrence pair weight against base-word weight (`PAIR_WEIGHT_SCALE`) and scaled the small-batch discovery threshold to what real seed vocabulary actually achieves (`SMALL_BATCH_FLOOR_SCALE`), verified against real document pairs with the fix reverted and reapplied.
- Fixed YOLO object detection being structurally unreachable for `.png` files without camera EXIF (the dominant real-world case); YOLO now runs whenever the model exists, and its confidence-weighted `pair:` co-occurrence features now reach topic matching.
- Widened first-run calibration sampling from 3 to 20 files per family and added `min_cluster_size` filtering so only genuinely-connected clusters are surfaced for review; unmatched files stay unmarked and retry in a later round instead of forcing per-file review.
- Replaced the four-word hardcoded stopword list with the `stop-words` package (BSD-3, static data, fully offline) after real English documents were found matching purely on function-word overlap.
- Added a local semantic rescue layer (`classifier_engine/embeddings.py`) using pretrained fastText word vectors (Korean + English, ~112 MB, downloaded and bundled like the YOLO model): only fires when exact lexical/co-occurrence matching finds nothing. Uses greedy best-match word-vector pairing (a lightweight relaxed Word Mover's Distance) rather than averaging, after averaging was shown to blur "same topic" into "same broad domain."
- Added bigram/trigram collocation extraction (`extract.py`) using pointwise mutual information over each document's own token stream, filtering incidental word adjacency from genuine fixed phrases; flows through the existing content-matching pipeline as additional `body`-source terms.
- Fixed a clustering scaling defect found only at full real-corpus size (~760 files): single-linkage clustering chained unrelated files transitively into two mega-clusters (412 and 89 files). Replaced with complete-linkage clustering (every cross-pair must independently clear the threshold); confirmed max cluster size dropped to 31/24 with cluster count rising from 11 to 112 on an identical re-run.
- Fixed calibration fallback topic names leaking raw internal feature-token syntax (e.g. `obj_person pair_dining_table+person`); added `humanize_term()` to prefer collocation phrases and humanize object labels.
- Rewrote the optional local Gemma naming assistant (`local_tagger.py`) after end-to-end testing found it reliably failed in its original form (batched multi-cluster requests under a loose JSON hint produced malformed output and wrong topic names). Now issues one grammar-constrained (`json_schema`) request per cluster with humanized terms, and tolerates individual cluster failures instead of discarding the whole batch; verified 0/11 → 11/11 valid names against real cluster data.

## 2026-08-13 — Sample-first topic calibration

- Added first-run and tray-triggered calibration using up to 3 randomized, extension-diverse files per type without moving samples; one- and two-file families remain eligible.
- Added adaptive TF-IDF clustering and an editable family board with reassignment, split, merge, tags, and explicit sample exclusion.
- Added consent-gated Google Gemma 3 1B Q4 and llama.cpp CPU installation with pinned size/SHA-256 verification, safe extraction, localhost-only inference, and TF-IDF fallback.
- Upgraded topic profiles to version 3 with positive and negative evidence; successful confirmations reinforce the chosen topic and corrections demote the rejected topic.
- Replaced the temporary unmatched-proposal step with one full-batch topic review and success-gated learning.
- Added calibration, signed-feedback, model-response, download-integrity, and archive-safety tests.
- Changed calibration into step one of a two-step move: approval immediately creates topic folders and transactionally moves seeds; only remaining top-level files reach the final review.
- Expanded profiles with up to 40 base terms and 120 weighted word co-occurrence pairs per file, plus up to 60 visible vocabulary tags per seed cluster.
- Increased readable document vocabulary retention from 30 to 160 terms, added ODT body extraction, and added real-file tests proving body words reach tags and contextual profile evidence.

## 2026-08-13 — Full classifier-engine wiring

- Removed `classifier.py`, its compatibility alias, and the temporary rule-based/fallback implementation.
- Made the engine-owned `ClassifierEngine` the sole implementation and import path for the queue, synchronous scanner, and JSON API.
- Routed every file through `Pipeline.safe_classify()` and retained the persisted decision ID, tier, action, category, and margin.
- Removed automatic engine-category topic mapping, built-in semantic profiles, and the seed lexicon.
- Converted default coursework/finance rules into evidence marks rather than terminal topic categories.
- Added real-pipeline tests proving fresh files remain `미분류` until a user-created profile or explicitly approved proposal names the topic.
- Removed the small-batch proposal minimum so every unmatched file reaches a checked user-assignment row.
- Added editable existing/new topic selectors and merged learning when several rows use the same user topic.

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
