# Sort Pilot — Local Classifier Architecture

This branch develops the SRS and architecture-driven local classification engine on top of the tray application in `main`. It preserves `main`'s root launcher and `sort_pilot/` package layout while adding the experimental local pipeline under `sort_pilot/tidy/`.

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
python main.py
```

## Repository layout

```text
main.py                    # desktop entry point
requirements.txt           # runtime dependencies
sort_pilot/                # application package from main
  classifier.py            # stable analyzer contract and pipeline adapter
  tidy/                    # architecture-driven local classifier engine
tests/                     # baseline app and classifier tests
data/                      # default rules and seed lexicon
docs/                      # implementation notes
eval/                      # offline evaluation utilities
```

Model binaries are intentionally not committed. Place the locally exported model at `data/models/yolov8n.onnx`. Expected hashes and export provenance are documented in [THIRD_PARTY.md](THIRD_PARTY.md).

## Safety

Classification is local-only. Do not upload files or use cloud inference. Dry-run remains the default, uncertain decisions enter the review queue, and model or dependency downloads require explicit approval.
