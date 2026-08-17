# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. The supreme implementation authority is `../plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`; `SRS.md` and `ARCHITECTURE.md` are historical references only.

## Implemented layers

`sort_pilot/classifier_engine/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers the application, queue, public JSON contract, migration, and classifier pipeline.

The root launcher and `sort_pilot/` application package use the manual Desktop/Downloads workflow from `app`. The retained `ClassifierEngine` supplies bounded extraction records to the queue. Its historical type/topic output does not select an educational destination; the active classification authority is `EducationalClassificationService`, with exactly the subject and template axes.

The manual app uses a two-thread Qt pool. Each pool thread retains its own analyzer, engine pipeline, SQLite connection, and RapidOCR instance. Progress and results cross back to the Qt main thread through signals. See `FUNCTION_MAP.md` for complete ownership and `INTEGRATION_PROCESS.md` for the branch integration record.

## Authoritative student-classifier upgrade

`../plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme for the student classifier; the legacy architecture and SRS remain references only. Phases 0–8 provide the two subject/template axes, fixed student onboarding and catalog, made-up evaluation corpus, E5 subject ranking, the separate five-template classifier, calibrated per-axis routing, constrained local Gemma fallback, fixed-choice preview, immutable approved paths, local correction examples, and measured OCR-layout evidence.

The Phase 6 fallback accepts only an axis that the calibrated policy routed to `gemma_fallback`. It sends ranked supplied candidates and bounded extracted evidence to one CPU-only loopback Gemma server, accepts only one exact supplied candidate or Needs Review, retries only unresolved axes, supports cancellation, and always shuts the server down. Its caller-selected local cache stores input hashes and validated selections only; it does not persist paths or raw extracted evidence. Invalid, unavailable, or retry-exhausted output remains Needs Review and cannot produce a move plan.

Phase 7 passes transient extracted natural text and bounded structured evidence into the two classifiers without adding raw text to persisted engine records. The subject and template routes remain independent. Needs Review stays non-folder state until the user makes an exact catalog/template selection. Final approval freezes collision-resolved source and destination paths in `OrganizationPlan`; execution consumes those paths directly and keeps the existing transactional rollback and persistent Undo behavior.

Only a changed or newly resolved preview decision becomes a separate personal example. The local document contains the fingerprint, normalized embedding, approved subject/template, original prediction, bounded lexical evidence, and relevant versions, but no source path or raw extracted text. Future nearest-example evidence is independently weighted for each axis. The weights and minimum similarities reproduce from made-up held-out data without changing the Phase 5 thresholds; no E5/Gemma fine-tuning or global profile mutation occurs.

Phase 8 orders detected OCR lines by page columns for subject natural text, retains the original detected order transiently for template semantic intent, and passes bounded layout indicators separately. A structured Kiwi lexical contribution with weight `0.05` supplements E5 subject similarity without converting tokens into a sentence. Development ablation retained PMI and rejected visual evidence; the final paired made-up evaluation verifies that frozen selection and clears the agreed subject, template, combined-path, latency, and memory gates. YOLO/LVIS visual evidence and new model-session scheduling remain disabled.

## Local model setup

The retained YOLO ONNX model was generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17 and remains at `data/models/yolov8n.onnx` (~13MB), but the active educational extraction flow no longer invokes it after the Phase 8 ablation. The semantic-rescue word vectors are pretrained fastText vectors (Korean + English), quantized to float16 and built locally at `data/models/word_vectors.npz` (~112MB, over GitHub's limit) by `embeddings_installer.py` after a consent prompt in the historical calibration flow.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Phase 8 aggregate reproduction uses only the tracked made-up development and held-out corpora described in `../eval/README.md`. Real labels remain local-only under Git-ignored `eval/local/`.
