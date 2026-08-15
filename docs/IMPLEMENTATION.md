# Implementation Notes

The active application is intentionally small: `app.py` coordinates tray actions, `analysis_queue.py` extracts file evidence, `llm_file_classifier.py` applies role policy and caching, and `local_tagger.py` runs verified local Gemma inference. Approved moves are handled by `organizer.py` and recorded by `history.py`.

`sort_pilot/classifier_engine/` is now an extraction package rather than a second classification stack. It contains extraction configuration, data contracts, document/OCR/vision extraction, fixed file-family routing, and the compatibility `ClassifierEngine` adapter. It does not contain Tier1, Naive Bayes, classifier learning, decision persistence, review queues, watchers, or engine move actions.

The Qt queue uses two workers. Each thread reuses its analyzer and RapidOCR instance. Extraction failures are represented in `AnalysisRecord` instead of being allowed to erase successful later stages or create unrelated decision-state failures.

Gemma runs through a pinned llama.cpp runtime installed under `%APPDATA%\tidy\local_ai`. `model_setup.py` owns terms consent and cancellable progress; `LocalModelInstaller` downloads, verifies, and atomically installs the exact artifacts. The file classifier batches five records, uses schema-constrained output, retries missing results, validates all paths, and saves each successful item immediately. Failed extraction and invalid/missing inference both fall back to `기타/확인필요`.

Run verification from the repository root:

```powershell
python -m pytest -q
python -m pip check
```

The old `%APPDATA%\tidy\state.db`, model weights, calibration state, and topic profiles are deliberately not deleted during upgrade because they are user-local legacy data. Current code does not open or modify them.
