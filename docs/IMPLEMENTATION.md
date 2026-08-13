# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. It turns the compact tray prototype into the layered system specified by `SRS.md` and `ARCHITECTURE.md`, while retaining the original UI-facing dictionary contract.

## Implemented layers

`sort_pilot/classifier_engine/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers the application, queue, public JSON contract, migration, and classifier pipeline.

The root launcher and `sort_pilot/` application package use the manual Desktop/Downloads workflow from `app`. `classifier.py` and all compatibility aliases were removed; `sort_pilot.classifier_engine.ClassifierEngine` is the sole classifier used by the queue, scanner, and public JSON API. Every call runs `Pipeline.safe_classify()` and persists its Tier-1 or Naive Bayes evidence.

The manual app uses a two-thread Qt pool. Each pool thread retains its own analyzer, engine pipeline, SQLite connection, and RapidOCR instance. Progress and results cross back to the Qt main thread through signals. See `FUNCTION_MAP.md` for complete ownership and `INTEGRATION_PROCESS.md` for the branch integration record.

Hierarchical classification routes each file into a fixed Korean type family and then applies only family-specific profiles created or approved by the user. Engine categories never name destination topics, and there are no built-in topics. Unmatched document/image records can form dependency-free current-batch TF-IDF proposals, but a user must select and name them before use. See `HIERARCHICAL_TOPICS.md` for scoring, persistence, UI, and migration behavior.

## Local model setup

The ONNX model is generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17. Binary model files are excluded from Git. Copy `yolov8n.onnx` to `data/models/yolov8n.onnx`; the classifier discovers it automatically.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Accuracy and resource targets still require the private labelled corpus and reference Windows hardware described in the SRS. Do not claim those acceptance thresholds based solely on unit tests.
