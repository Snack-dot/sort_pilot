# Phase 8 Implementation Outcome

Phase 8 is implemented in the active educational classification flow.

Delivered responsibilities:

- `sort_pilot/evaluation/phase8.py` — strict direct made-up case loading, exact paired significance, resource values, and complete gate reporting.
- `eval/run_phase8_ablation.py` — cache-only development selection and frozen held-out verification; it prints aggregate results and writes nothing.
- `eval/synthetic_phase8_ablation_corpus.json` — 30 made-up development cases with no invented IDs.
- `eval/synthetic_phase8_held_out_corpus.json` — 30 separate made-up held-out cases with no invented IDs.
- `eval/synthetic_phase8_image.ppm` — a made-up local image used only for resource measurement.
- `sort_pilot/classification/optional_evidence.py` and `data/phase8_optional_evidence.json` — strict inspectable selected evidence: OCR layout on, subject Kiwi weight `0.05`, PMI on, visual off, and new model-session scheduling off.
- `sort_pilot/classification/e5.py` — bounded inverse-frequency Kiwi lexical scoring retained as a separate visible subject evidence contribution.
- `sort_pilot/classifier_engine/extract.py` — column-aware OCR ordering, bounded layout indicators, transient original-order template text, and removal of active YOLO inference.
- `sort_pilot/classification/service.py` — independent subject/template natural-text embeddings, retained PMI, rejected visual evidence, and unchanged Phase 5 routing thresholds.
- `sort_pilot/classifier_engine/types.py`, `topics.py`, `analyzer.py`, and `sort_pilot/app.py` — transient original-order template text propagation without serialization.
- `tests/test_phase8_ablation.py`, `test_subject_e5.py`, `test_classifier_pipeline.py`, and `test_educational_service.py` — strict selection/corpus, structured evidence, OCR ordering, non-persistence, independent semantics, and active-channel coverage.
- `README.md`, `CHANGELOG.md`, `eval/README.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION.md`, and `docs/FUNCTION_MAP.md` — current active behavior, reproduction commands, reference status, and complete callable ownership.
- this Phase 8 session archive.

The active path still produces exactly subject and template decisions. It cannot invent a subject or a sixth template, and unresolved axes still cannot create a move plan.
