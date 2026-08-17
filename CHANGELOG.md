# Changelog

## 2026-08-17 — Student-hybrid classifier remediation: filename evidence and margin safety

No new phase; this remediates defects found in the shipped Phase 0-8 classifier by a real-data test (62, later 100, real exam-prep files, manually reviewed, screenshotted and separately downloaded for local-only validation — never committed).

- Added a catalog-bounded filename-alias evidence channel to the subject axis (previously template-only), resolving via longest-alias-match so `통합사회`/`통합과학` correctly out-rank the shorter `사회`/`과학` when both appear in the same filename. Reuses the previously-declared-but-unused `SubjectProfile.keywords` field; bumps the subject profile schema to v2.
- Added missing template filename indicators: `문제`/`문제지` → 과제; `정답`/`듣기대본`/`수능특강`/`수능완성` → 학습자료 (해설 was already present).
- Fixed the held-out calibration procedure to stop silently preferring the smallest workable accept/margin threshold: flipped the tie-break to prefer larger margins among tied outcomes, then added a hard `minimum_margin` floor (0.02) after discovering the tie-break alone wasn't sufficient — coverage-maximization could still force a near-zero margin. Template margin moved from ~0.000118 to ~0.141 (local precision 95.5% → 100%); subject margin from ~0.0044 to ~0.038 (precision 92.9% → 96.2%). Both axes still clear the approved 90%/50% held-out targets.
- Fixed both calibration scripts (`eval/run_policy_calibration.py`, `eval/run_personal_example_calibration.py`) silently calibrating with the wrong evidence weights (defaulting to 0.0 instead of production's real Kiwi-lexical and new filename weights) — found independently while wiring the new channel through, not in the original report.
- Expanded the invented held-out corpus (50 → 68 cases) to exercise the new evidence channels and near-miss template pairs; regenerated and re-verified both `calibrated_policy.json` and `personal_example_policy.json` against it.
- Separately validated the fix against the real dataset behind the original report (100 real files, made available locally, never committed): 50/50 subject and 57/57 template predictions correct on a conservatively-labeled subset; the already-recalibrated thresholds generalized to the real data without adjustment; confident auto-route rate across all 100 real files rose from the originally reported 16.1% to 46.0% using filename evidence alone, with no body text.
- See `session_archive/2026-08-17-student-hybrid-margin-and-filename-remediation/` for the full investigation, decisions, and evidence.

## 2026-08-17 — Student-hybrid Phase 7 preview, immutable plan, and corrections

- Wired the active Desktop/Downloads organization flow to independent subject and template classification and removed the older topic-calibration, topic-management, and folder-migration controls from the tray.
- Added a fixed-choice educational preview that exposes unresolved axes, accepts only the selected student's catalog subjects and exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`, and requires both axes before approval.
- Froze exact source and collision-resolved destination paths at final approval, executed those `OrganizationPlan` values without reclassification, and preserved transactional rollback plus persistent Undo.
- Added strict atomic local personal examples containing fingerprint, normalized embedding, approved subject/template, original prediction, bounded lexical evidence, and relevant versions, with no path or raw extracted text.
- Added independently calibrated nearest-example influence using only made-up corpora. The reproducible rule retained Phase 5 thresholds, met the approved 90% local-precision and 50% Gemma top-label targets on both axes, and produced zero held-out regressions.
- Kept extracted natural text transient, added end-to-end educational service routing and cancellation, and retained unavailable or invalid fallback results as Needs Review.

## 2026-08-17 — Student-hybrid Phase 6 constrained Gemma fallback

- Added a per-axis local Gemma fallback that accepts only Phase 5 `gemma_fallback` routes and therefore cannot reconsider an authoritative local result or a local abstention.
- Restricted each prompt and response contract to ranked supplied subject candidates or exactly the five fixed templates, bounded extracted evidence, and the exact `Needs Review` output; invented labels, paths, and additional output fields are rejected.
- Ported the reliable `fix`-branch loopback server lifetime, five-item batching, two retries for unresolved axes, explicit cancellation, progress, and forced process cleanup without porting its obsolete role/area/document-type behavior.
- Added an atomic local cache keyed by model-visible inputs and all relevant versions. The cache stores only hashes, axis names, and validated selections—not paths or raw extracted evidence—and writes each valid result immediately.
- Kept unavailable, invalid, and retry-exhausted results as Needs Review, so they cannot produce a move plan. No Phase 7 production integration was started.

## 2026-08-17 — Student-hybrid Phase 5 calibrated policy

- Added user-approved operating targets of 90% held-out precision for authoritative local decisions and 50% held-out top-label accuracy for Gemma escalation.
- Added a new 50-case made-up held-out corpus, separate from profile-writing examples, covering all 18 catalog subjects and all five templates.
- Added exhaustive per-axis threshold selection that maximizes local handling first and Gemma escalation second while requiring both approved targets; explicit abstention remains Needs Review.
- Added a centralized strict policy with independently calibrated subject and template raw-score, margin, and Gemma-escalation thresholds.
- Added a cache-only calibration runner that reproduces the policy from the held-out corpus, prints aggregate results, writes nothing, and can verify the packaged policy exactly.
- Held-out results were 7/7 authoritative subject decisions and 46/49 authoritative template decisions; the subject escalation region was 16/32 and the template escalation region was 1/1. These measurements define this policy and are not general production-accuracy claims.

## 2026-08-17 — Student-hybrid Phase 4 five-template classifier

- Added strict separate profiles for exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Added explicit per-template weights for semantic intent, filename, lexical, PMI-collocation, OCR/layout, optional visual, and personal-example evidence; all start at the same neutral value and remain distinct from Phase 5 routing-threshold calibration.
- Kept natural filename/body text in E5 input while scoring every engineered evidence source separately instead of converting it into a sentence.
- Added five-candidate weighted ranking with raw score, top-two margin, every named evidence contribution, model/profile/policy versions, and no calibrated-confidence claim.
- Added focused tests and a real cache-only model check against the tracked made-up corpus; this verifies classifier mechanics and is not a calibration or production-accuracy claim.

## 2026-08-17 — Student-hybrid Phase 3 subject profiles and E5 prototype

- Added strict natural-language profiles for every exact subject in the middle/high student catalog.
- Added the pinned `fastembed==0.8.0` CPU adapter for `intfloat/multilingual-e5-small`, with explicit custom-model registration and local-cache-only loading by default.
- Added 384-dimensional finite/nonzero vector validation, E5 query/passage prefixes, normalized profile-vector averaging, and NumPy cosine ranking.
- Restricted ranked candidates to the selected student type's catalog and retained raw similarity plus top-two margin without treating either as calibrated confidence.
- Added focused tests with an injected deterministic encoder and completed a real local-model check against the made-up corpus; this remains a prototype and is not wired into the active production classifier.

## 2026-08-17 — Student-hybrid Phase 2 evaluation

- Added a labeled synthetic student corpus with only made-up filenames, text, subjects, and the five fixed templates.
- Added strict ordered corpus and prediction loading without invented case IDs or repeated per-case catalog metadata.
- Added aggregate subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory reporting; unresolved axes count as incorrect.
- Reserved the Git-ignored `eval/local/` directory for any evaluation involving real local files or labels; such material must never be committed or uploaded to GitHub.
- Added a supreme-plan hierarchy under `plans/`, preserved older educational plans as references only, and moved architecture, SRS, and third-party documentation under `docs/`.

## 2026-08-17 — Student-hybrid Phase 1 onboarding

- Added a first-run fixed-choice student setup for `중학생|고등학생`, grades 1–3, and semesters 1–2.
- Persisted only occupation, student type, grade, semester, and `KR_STUDENT_2026_MVP_V1` catalog version in an atomic local profile.
- Added a tray action for editing student settings and made saved settings bypass the first-run prompt on later launches.
- Kept school, institution, timetable, academic-year migration, and production-classifier integration out of this phase.

## 2026-08-17 — Student-hybrid Phase 0 remediation

- Replaced exploratory Python subject constants with the packaged `KR_STUDENT_2026_MVP_V1` JSON catalog for `중학생` and `고등학생`.
- Restricted onboarding contracts to grades 1–3 and semesters 1–2, with no curriculum-revision migration, institution, timetable, or fallback-subject model.
- Fixed the template contract to exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Made unresolved subject/template labels nullable review state and prohibited destination rendering until both axes contain valid configured values.
- Kept the active production classifier and application workflow unchanged during this foundation remediation.

## 2026-08-16 — Final student-hybrid MVP plan

- Finalized one student-only hierarchy using `중학생`/`고등학생`, grades 1–3, semesters 1–2, a constrained 2026 MVP subject catalog, and exactly five templates: `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Clarified that curriculum material is a practical subject-list reference, not a legal, institutional, timetable, or year-by-year revision engine.
- Defined `Needs Review` as non-folder workflow state and prohibited artificial fallback subjects or a sixth template.
- Preserved superseded prompts and the exploratory ADR under `plans/superseded/`, added the authoritative plan under `plans/`, and archived the complete planning session.
- Recorded mandatory Phase 0 remediation for exploratory contracts that still contain superseded assumptions; the active application remains unchanged.

## 2026-08-16 — Educational hybrid foundation

- Recorded the decision to evolve the existing statistical classifier into a curriculum-constrained middle/high-school hybrid, with local decisions authoritative at high confidence and Gemma restricted to ambiguous per-axis fallback.
- Added versioned onboarding contracts for student type, grade, semester, and JSON-catalog subject candidates.
- Added atomic onboarding-profile persistence with explicit corruption and stale-catalog rejection.
- Defined the subject-profile, bounded evidence, catalog filtering, and local subject-classifier interfaces required by the later E5 implementation.
- Added an explicit per-axis policy contract that routes decisive local evidence to acceptance, plausible ambiguity to Gemma, and weak or abstained evidence to review.
- Added an observable multidimensional result contract that keeps subject and template decisions, scores, margins, evidence, provenance, and nullable review state separate from the rendered folder hierarchy.
- Added the `학생/<학생 유형>/<학년>/<학기>/<과목>/<템플릿>` renderer and contract tests without changing the active classifier or UI workflow.

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

## 2026-08-17 — Student-hybrid Phase 8 optional evidence and low-end optimization

- Added strict paired made-up development and held-out evaluation for subject accuracy, template accuracy, combined-path accuracy, exact statistical significance, P95 latency, and peak process memory; unresolved results remain incorrect.
- Added layout-aware OCR ordering while retaining the original OCR order transiently for template semantic intent; neither text form is serialized in the engine record.
- Added a separate inspectable Kiwi lexical contribution to subject ranking and selected weight `0.05` from development data without changing the Phase 5 routing thresholds.
- Final held-out gains were +40.0 points for subject, +56.7 points for template, and +43.3 points for combined path, with exact paired p-values below `0.05` for all three. Authoritative-local subject precision was `14/14`.
- Final P95 latency reproduction was about `11.7 ms` versus the Phase 7 baseline's `371.8 ms`, and peak process memory was about `905.4 MB`, below the agreed 2 GB limit.
- Retained PMI after significant development contribution and verified the complete frozen selection on separate made-up held-out cases. Rejected YOLO/LVIS visual evidence and new model-session scheduling; the active educational extractor no longer runs YOLO.
- Used only made-up tracked cases; no real filename, extracted text, label, prediction, or correction was added.

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
