# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. It turns the compact tray prototype into the layered system specified by `SRS.md` and `ARCHITECTURE.md`, while retaining the original UI-facing dictionary contract.

## Implemented layers

`sort_pilot/classifier_engine/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers the application, queue, public JSON contract, migration, and classifier pipeline.

The root launcher and `sort_pilot/` application package use the manual Desktop/Downloads workflow from `app`. `classifier.py` and all compatibility aliases were removed; `sort_pilot.classifier_engine.ClassifierEngine` is the sole classifier used by the queue, scanner, and public JSON API. Every call runs `Pipeline.safe_classify()` and persists its Tier-1 or Naive Bayes evidence.

The manual app uses a two-thread Qt pool. Each pool thread retains its own analyzer, engine pipeline, SQLite connection, and RapidOCR instance. Progress and results cross back to the Qt main thread through signals. See `FUNCTION_MAP.md` for complete ownership and `INTEGRATION_PROCESS.md` for the branch integration record.

Hierarchical classification routes each file into a fixed Korean type family and then applies only family-specific profiles confirmed by the user. Engine categories never name destination topics, and there are no built-in topics. A bounded first-run sample (up to 20 files per family) is adaptively clustered — complete-linkage TF-IDF/co-occurrence similarity, with a pretrained-word-vector semantic rescue when exact matching finds nothing — and only genuinely multi-file clusters are reviewed in a calibration board; optional local Gemma improves names/tags one cluster at a time under a schema-constrained request, while deterministic collocation-aware terms remain the per-cluster fallback. Approval immediately moves the surfaced seeds into the folders they create, stores broad base-word/collocation/co-occurrence evidence, then rescans only the remaining top-level files for final review. Successful corrections add positive evidence to the chosen topic and negative evidence to the rejected topic. See `HIERARCHICAL_TOPICS.md` for persistence, scoring, privacy, UI, and migration behavior.

## Local model setup

The YOLO ONNX model is generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17 and is committed at `data/models/yolov8n.onnx` (~13MB, under GitHub's 100MB limit) — no setup needed. The semantic-rescue word vectors are pretrained fastText vectors (Korean + English), quantized to float16 and built locally at `data/models/word_vectors.npz` (~112MB, over GitHub's limit) by `embeddings_installer.py` after a consent prompt in the calibration flow, streaming only the most frequent words from Meta's official releases rather than downloading them whole. The classifier discovers both automatically and degrades gracefully (no object detection, no semantic rescue) when either is absent.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Accuracy and resource targets still require the private labelled corpus and reference Windows hardware described in the SRS. Do not claim those acceptance thresholds based solely on unit tests.
