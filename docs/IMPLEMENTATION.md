# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. `../plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is the supreme plan for the student-hybrid upgrade. `SRS.md`, `ARCHITECTURE.md`, and the documents under `../plans/superseded/` remain historical references only and cannot override it.

## Implemented layers

`sort_pilot/classifier_engine/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers the application, queue, public JSON contract, migration, and classifier pipeline.

The root launcher and `sort_pilot/` application package use the manual Desktop/Downloads workflow from `app`. `classifier.py` and all compatibility aliases were removed; `sort_pilot.classifier_engine.ClassifierEngine` is the sole classifier used by the queue, scanner, and public JSON API. Every call runs `Pipeline.safe_classify()` and persists its Tier-1 or Naive Bayes evidence.

The manual app uses a two-thread Qt pool. Each pool thread retains its own analyzer, engine pipeline, SQLite connection, and RapidOCR instance. Progress and results cross back to the Qt main thread through signals. See `FUNCTION_MAP.md` for complete ownership and `INTEGRATION_PROCESS.md` for the branch integration record.

Hierarchical classification routes each file into a fixed Korean type family and then applies only family-specific profiles confirmed by the user. Engine categories never name destination topics, and there are no built-in topics. A bounded first-run sample (up to 20 files per family) is adaptively clustered — complete-linkage TF-IDF/co-occurrence similarity, with a pretrained-word-vector semantic rescue when exact matching finds nothing — and only genuinely multi-file clusters are reviewed in a calibration board; optional local Gemma improves names/tags one cluster at a time under a strict JSON response contract, while deterministic collocation-aware terms remain the per-cluster fallback. Approval immediately moves the surfaced seeds into the folders they create, stores broad base-word/collocation/co-occurrence evidence, then rescans only the remaining top-level files for final review. Successful corrections add positive evidence to the chosen topic and negative evidence to the rejected topic. See `HIERARCHICAL_TOPICS.md` for persistence, scoring, privacy, UI, and migration behavior.

## Student-hybrid Phases 0–2

Phase 0 establishes exactly two classification axes: subject and template. Subjects must come from the packaged `KR_STUDENT_2026_MVP_V1` catalog for the selected student type. Templates are fixed to `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. Unexpected catalog and student-profile fields are rejected. An unresolved subject or template remains `Needs Review` and cannot produce an `OrganizationPlan`.

Phase 1 adds the atomic saved student profile and fixed-choice onboarding. The stored fields are limited to occupation, student type, grade, semester, and catalog version. Relevant classification and organization entry points require a valid saved profile. The active organizer otherwise remains on the pre-existing type/topic implementation at this checkpoint; production subject/template ranking begins in later phases.

Phase 2 adds strict labeled-corpus and prediction loading, a cache-only evaluation runner, made-up tracked examples, and aggregate subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory. Unresolved results count as incorrect in all three accuracy metrics. Any evaluation involving real local filenames, text, labels, predictions, or corrections belongs only in Git-ignored `eval/local/`.

Phase 3 adds strict natural-language profiles for every exact catalog subject and a local CPU-only `intfloat/multilingual-e5-small` prototype. The adapter defaults to the Git-ignored local cache, validates finite nonzero 384-dimensional vectors, keeps natural text separate from structured lexical evidence, and ranks only the selected student's catalog subjects by NumPy cosine similarity. It retains raw similarity and margin but makes no calibrated-confidence claim. The ranker remains separate from the active organizer until later phases provide calibrated routing and production integration.

Phase 4 adds separate profiles for exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. The classifier reuses the local E5 adapter for semantic intent while keeping filename, lexical, PMI-collocation, OCR/layout, optional visual, and personal-example evidence as independent weighted inputs. Each profile starts with neutral explicit weights. Results retain exactly five candidates, weighted raw score, top-two margin, and each named contribution without claiming calibrated confidence. The classifier remains outside the active organizer and defines no acceptance, Gemma, or review thresholds.

Phase 5 adds a strict centralized routing policy calibrated independently for subject and template from a separate 50-case made-up held-out corpus. Authoritative local decisions must meet the user-approved 90% held-out precision target; the Gemma escalation region must meet the 50% held-out top-label accuracy target; lower evidence remains `Needs Review`. The cache-only runner reproduces the packaged thresholds and writes nothing. These held-out measurements define the policy only and are not general production-accuracy claims. Production integration and constrained Gemma behavior remain later phases.

Phase 6 adds a constrained local Gemma fallback for individual subject or template axes. It accepts only Phase 5 `gemma_fallback` routes, sends bounded evidence and supplied candidates, accepts only one supplied label or `Needs Review`, batches five axes, retries unresolved axes twice, supports cancellation, and always stops the loopback server. Its atomic local cache stores only input hashes, axis names, and validated selections. Invalid, unavailable, cancelled, or exhausted results stay unresolved and cannot produce a move plan. The component remains outside the active organizer until Phase 7.

## Local model setup

The YOLO ONNX model is generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17 and is committed at `data/models/yolov8n.onnx` (~13MB, under GitHub's 100MB limit) — no setup needed. The semantic-rescue word vectors are pretrained fastText vectors (Korean + English), quantized to float16 and built locally at `data/models/word_vectors.npz` (~112MB, over GitHub's limit) by `embeddings_installer.py` after a consent prompt in the calibration flow, streaming only the most frequent words from Meta's official releases rather than downloading them whole. The classifier discovers both automatically and degrades gracefully (no object detection, no semantic rescue) when either is absent.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Accuracy and resource targets still require the private labelled corpus and reference Windows hardware described in the SRS. Do not claim those acceptance thresholds based solely on unit tests.
