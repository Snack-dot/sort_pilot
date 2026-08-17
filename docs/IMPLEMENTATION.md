# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. The supreme implementation authority is `../plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`; `SRS.md` and `ARCHITECTURE.md` are historical references only.

## Implemented layers

`sort_pilot/classifier_engine/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers the application, queue, public JSON contract, migration, and classifier pipeline.

The root launcher and `sort_pilot/` application package use the manual Desktop/Downloads workflow from `app`. The retained `ClassifierEngine` supplies bounded extraction records to the queue. Its historical type/topic output does not select an educational destination; the active classification authority is `EducationalClassificationService`, with exactly the subject and template axes.

The manual app uses a two-thread Qt pool. Each pool thread retains its own analyzer, engine pipeline, SQLite connection, and RapidOCR instance. Progress and results cross back to the Qt main thread through signals. See `FUNCTION_MAP.md` for complete ownership and `INTEGRATION_PROCESS.md` for the branch integration record.

## Authoritative student-classifier upgrade

`../plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme for the student classifier; the legacy architecture and SRS remain references only. Phases 0–7 provide the two subject/template axes, fixed student onboarding and catalog, made-up evaluation corpus, E5 subject ranking, the separate five-template classifier, calibrated per-axis routing, constrained local Gemma fallback, fixed-choice preview, immutable approved paths, and local correction examples.

The Phase 6 fallback accepts only an axis that the calibrated policy routed to `gemma_fallback`. It sends ranked supplied candidates and bounded extracted evidence to one CPU-only loopback Gemma server, accepts only one exact supplied candidate or Needs Review, retries only unresolved axes, supports cancellation, and always shuts the server down. Its caller-selected local cache stores input hashes and validated selections only; it does not persist paths or raw extracted evidence. Invalid, unavailable, or retry-exhausted output remains Needs Review and cannot produce a move plan.

Phase 7 passes transient extracted natural text and bounded structured evidence into the two classifiers without adding raw text to persisted engine records. The subject and template routes remain independent. Needs Review stays non-folder state until the user makes an exact catalog/template selection. Final approval freezes collision-resolved source and destination paths in `OrganizationPlan`; execution consumes those paths directly and keeps the existing transactional rollback and persistent Undo behavior.

Only a changed or newly resolved preview decision becomes a separate personal example. The local document contains the fingerprint, normalized embedding, approved subject/template, original prediction, bounded lexical evidence, and relevant versions, but no source path or raw extracted text. Future nearest-example evidence is independently weighted for each axis. The weights and minimum similarities reproduce from made-up held-out data without changing the Phase 5 thresholds; no E5/Gemma fine-tuning or global profile mutation occurs.

## Local model setup

The YOLO ONNX model is generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17 and is committed at `data/models/yolov8n.onnx` (~13MB, under GitHub's 100MB limit) — no setup needed. The semantic-rescue word vectors are pretrained fastText vectors (Korean + English), quantized to float16 and built locally at `data/models/word_vectors.npz` (~112MB, over GitHub's limit) by `embeddings_installer.py` after a consent prompt in the calibration flow, streaming only the most frequent words from Meta's official releases rather than downloading them whole. The classifier discovers both automatically and degrades gracefully (no object detection, no semantic rescue) when either is absent.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Accuracy and resource targets still require the private labelled corpus and reference Windows hardware described in the SRS. Do not claim those acceptance thresholds based solely on unit tests.
