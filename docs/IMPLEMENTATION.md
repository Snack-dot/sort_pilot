# Architecture Implementation Notes

## Branch purpose

This work belongs on a feature branch rather than `main`. It turns the compact tray prototype into the layered system specified by `SRS.md` and `ARCHITECTURE.md`, while retaining the original UI-facing dictionary contract.

## Implemented layers

`src/tidy/` contains configuration, data contracts, extraction, Tier 1 rules, Naive Bayes classification, learning, persistence, reconciliation, actions, and ONNX vision. `eval/` provides repeatable classifier metrics and decision-resource export. `tests/` covers token normalization, model learning and persistence, dry-run/collision safety, text extraction, and vision post-processing.

The legacy application under `ai-file-organizer-team-mvp-fixed/` remains runnable. Its `classifier.py` imports the new pipeline and falls back to the original rules if initialization is unavailable.

## Local model setup

The ONNX model is generated from the official Ultralytics YOLOv8n checkpoint at 640×640 with opset 17. Binary model files are excluded from Git. Copy `yolov8n.onnx` to `data/models/yolov8n.onnx`; the classifier discovers it automatically.

## Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Accuracy and resource targets still require the private labelled corpus and reference Windows hardware described in the SRS. Do not claim those acceptance thresholds based solely on unit tests.

