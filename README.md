# Sort Pilot — Local Classifier Architecture

This branch develops the SRS and architecture-driven local classification engine on top of the original tray MVP. The repository's `main` branch remains the smaller pre-architecture application; this branch contains the experimental full local pipeline.

## What is included

- Tier 1 ordered filename and extension rules
- Local document, archive, image, and OCR feature extraction
- Korean morphological tokenization
- Multinomial Naive Bayes scoring, margin gating, and explanations
- SQLite queue, review records, decisions, and undo journal
- Bootstrap learning, feedback, calibration, and atomic model storage
- Dry-run-safe action execution and startup reconciliation
- YOLOv8n ONNX object, pair, count, and image-context features
- Evaluation and resource-export utilities

See [SRS.md](SRS.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) for requirements, design, and current coverage.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
cd ai-file-organizer-team-mvp-fixed
python main.py
```

Model binaries are intentionally not committed. Place the locally exported model at `data/models/yolov8n.onnx`. The expected hashes and export provenance are documented in `THIRD_PARTY.md`.

## Safety

Classification is local-only. Do not upload files or use cloud inference. Dry-run remains the default, uncertain decisions enter the review queue, and model or dependency downloads require explicit approval.

