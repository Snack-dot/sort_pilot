# Sort Pilot

Sort Pilot is a Windows system-tray application that analyzes safe files on the Desktop and in Downloads, recommends hierarchical type/topic folders using a fully local classifier, and moves only the files explicitly approved by the user. Phases 0–5 also establish the separate student subject/template contracts, onboarding profile, synthetic evaluation harness, catalog-bounded multilingual E5 subject ranker, separate five-template classifier, and independently calibrated routing policy required by the authoritative hybrid-classifier plan; those new classification axes are not yet wired into the active organizer.

## Current workflow

```text
Tray action (Desktop / Downloads / both)
→ require fixed-choice student type / grade / semester setup
→ safe top-level candidate collection
→ deduplicated two-worker classification queue
→ real Pipeline Tier-1 / Naive Bayes decision and persistence
→ fixed file type + user-created topic profile resolution
→ first-run sample calibration when no user topics exist
→ approved seed files immediately create/populate topic folders
→ remaining-file editable topic review
→ cancellable progress dialog
→ editable destination preview
→ explicit user approval
→ original-name file moves
→ atomic JSON history and restart-safe Undo
```

There is no real-time filesystem watcher in the integrated app. Manual organization avoids repeated background scans, and each worker reuses one local RapidOCR engine rather than initializing ONNX Runtime for every image.

## Public classifier interface

`ClassifierEngine` is exported directly by `sort_pilot.classifier_engine` and returns Python dictionaries that are directly JSON-compatible. There is no separate compatibility classifier or fallback implementation; every call uses `Pipeline.safe_classify()`.

```python
from pathlib import Path
from sort_pilot.classifier_engine import ClassifierEngine

classifier = ClassifierEngine()
try:
    result = classifier.analyze_json(Path("C:/Users/user/Downloads/운영체제과제.pdf"))
finally:
    classifier.close()
```

Single file:

```python
{
    "filepath": "C:/Users/user/Downloads/운영체제과제.pdf",
    "folder": "문서/미분류"
}
```

Multiple files:

```python
{
    "results": [
        {"filepath": "C:/Users/user/Downloads/운영체제과제.pdf", "folder": "문서/내과제"},
        {"filepath": "C:/Users/user/Downloads/쿠팡영수증.png", "folder": "이미지/구매기록"}
    ]
}
```

Use `ClassifierEngine.analyze_json(path)` or `analyze_many_json(paths)`. The fixed roots are `문서`, `이미지`, `압축파일`, `오디오`, `동영상`, and `기타`; unmatched topics use `미분류`. A fresh install contains no semantic topics. `내과제` and `구매기록` above are examples of profiles confirmed by the user during calibration. Engine decisions are persisted as evidence but never become destination topic names automatically.

## Features and safety

- Strict packaged `KR_STUDENT_2026_MVP_V1` subject catalog for `중학생` and `고등학생`, grades 1–3, and semesters 1–2.
- Exactly two educational classification axes: catalog-bounded subject and one of `학습자료`, `과제`, `교내활동`, `교외활동`, or `증빙서류`.
- Unresolved subject or template decisions are `Needs Review` state and cannot produce a move plan.
- Atomic local student profile containing only occupation, student type, grade, semester, and catalog version; relevant organization flows require it.
- Strict made-up evaluation corpus and prediction loaders with subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory metrics. Real evaluation material stays under ignored `eval/local/`.
- Natural-language profiles for every catalog subject and a CPU-only `intfloat/multilingual-e5-small` prototype that ranks only the selected student's catalog subjects, retaining raw cosine similarity and margin without claiming calibrated confidence.
- Separate profiles for exactly five templates, with semantic intent, filename, lexical, PMI-collocation, OCR/layout, optional visual, and personal-example evidence kept as distinct weighted inputs. The Phase 4 weights are neutral mechanics, not calibrated routing thresholds.
- Independently calibrated subject and template routes using a separate 50-case made-up held-out corpus: authoritative local decisions must meet 90% held-out precision, while the Gemma escalation region must meet 50% held-out top-label accuracy; lower evidence remains `Needs Review`.
- Manual Desktop, Downloads, or combined organization.
- Real Tier-1 and learned Naive Bayes decisions persisted as evidence for every analyzed file.
- Deterministic top-level type routing with independent, user-owned topic profiles per type.
- User-created topic names, tags, enable/disable state, and learn-only example files.
- First-run calibration samples up to 20 safe top-level files per type and still works with one or two; only clusters of two or more genuinely connected files are surfaced for review, and unsurfaced files are retried with priority in a later round. Approval immediately creates `<유형>/<주제>` folders and moves those seed files into them.
- Complete-linkage TF-IDF/co-occurrence clustering proposes topics, backed by PMI-filtered bigram/trigram collocation detection and a pretrained-word-vector semantic rescue for when exact term overlap isn't enough; an optional local Google Gemma 3 1B model improves names and tag lists, one cluster at a time under a schema-constrained request, after explicit terms/download consent.
- The calibration board supports moving files between topics, renaming, editing tags, splitting, merging, and excluding samples.
- The final batch review uses an editable topic selector. Confirmed predictions reinforce a profile; corrections reinforce the chosen profile and demote the rejected profile.
- Profile data is version 3 and stores a broad bounded vocabulary: base-word weights plus up to 120 weighted within-file co-occurrence pairs per seed. It also stores independent negative correction evidence without raw contents or example paths.
- Manual previewed migration from a user-named flat folder such as `직접선택` to `문서/직접선택` or `이미지/직접선택`.
- Exactly two classification workers; duplicate paths are processed once per session.
- One reusable classifier pipeline, SQLite connection, and RapidOCR instance per worker thread.
- Cancellable progress with no partial preview after cancellation.
- Local document, archive, image, OCR, and optional ONNX object features; YOLO object detection runs on any eligible image once the local model is installed, independent of screenshot/photo routing.
- Semantic topics use actual local contents only: TXT/Markdown/CSV/RTF, PDF, DOCX, ODT, PPTX, XLSX, ZIP entry names, and image OCR/object (including object-pair co-occurrence) evidence. Filenames, extensions, and generic metadata may inform the lower-level engine decision but cannot create or select a topic. Up to 160 distinct body terms are retained per readable document, plus statistically significant bigram/trigram phrases (filtered by pointwise mutual information, not just raw adjacency).
- A local semantic rescue matches records against profiles by pretrained word-vector similarity only when exact term matching finds nothing, using greedy word-to-word pairing rather than averaging; it never replaces the exact-match path, only supplements it.
- Calibration samples only formats with a bundled content extractor, and extraction-empty samples cannot create a profile. `.hwp` and `.hwpx` are excluded from collection while the content architecture is being validated; legacy binary DOC/XLS/PPT files are not calibration seeds.
- Editable destination root and relative folder for every file.
- Original filenames are preserved; collisions receive numeric suffixes.
- No move occurs before final approval.
- Completed move batches are stored atomically in `history.json` and can be undone after restart.
- The latest active legacy `history.db` batch is migrated once without modifying the database.
- A Qt lock prevents two Sort Pilot instances from running simultaneously.
- No cloud inference or file upload.

## Setup and verification

Python 3.11 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
python main.py
```

The app has no main window. Right-click the `SP` system-tray icon to organize files, undo the latest batch, or quit.

## Repository layout

```text
main.py                            desktop entry point
sort_pilot/app.py                  tray workflow and UI coordination
sort_pilot/onboarding.py           fixed-choice student-profile setup
sort_pilot/curriculum/             strict student profile and subject catalog contracts
sort_pilot/classification/         subject/template result and routing contracts
sort_pilot/classification/e5.py    Phase 3 catalog-bounded subject ranking prototype
sort_pilot/classification/template.py Phase 4 five-template ranking prototype
sort_pilot/classification/calibrated_policy.py Phase 5 per-axis routing calibration
sort_pilot/evaluation/             strict labeled-corpus loading and aggregate evaluation
sort_pilot/analysis_queue.py       deduplicated two-worker analysis sessions
sort_pilot/calibration.py          bounded sampling, editable drafts, signed feedback
sort_pilot/calibration_dialog.py   calibration board and consent/install UI
sort_pilot/local_tagger.py         pinned Gemma/llama.cpp install and localhost inference
sort_pilot/classifier_engine/      sole public classifier, extraction, scoring, persistence, topics, vision
sort_pilot/topic_dialogs.py        topic profile and TF-IDF proposal UI
sort_pilot/migration.py            safe flat-folder hierarchy migration planning
sort_pilot/history.py              atomic JSON move history and SQLite migration
sort_pilot/preview.py              destination review and approval
sort_pilot/organizer.py            safe moves, rollback, collision handling, Undo
tests/                             app, queue, contract, and engine tests
eval/                              tracked made-up evaluation inputs and cache-only runner
plans/                             authoritative hybrid plan and reference-plan hierarchy
docs/FUNCTION_MAP.md               complete function ownership and call-flow map
docs/INTEGRATION_PROCESS.md        app-branch integration record
docs/HIERARCHICAL_TOPICS.md        type/topic model, TF-IDF, profiles, and migration
```

Classifier state intentionally remains under the legacy `%APPDATA%\tidy` directory so the package rename does not orphan learned weights or decisions. Versioned topic profiles and hashed calibration history are stored locally; no example paths or raw contents are retained. Move history and the single-instance lock use Qt's Sort Pilot application-data directory.

The vision model (`data/models/yolov8n.onnx`, ~13MB) is committed directly and used automatically. Larger binaries are not committed. After consent, the app downloads the pinned 806MB Gemma GGUF and llama.cpp Windows CPU runtime, verifies their SHA-256 digests, and runs inference only on `127.0.0.1`. If installation or a given cluster's naming request fails, that cluster's deterministic collocation-aware name keeps calibration usable. The optional semantic-rescue word vectors (`data/models/word_vectors.npz`, ~112MB) are built locally after a separate consent prompt, streaming only the most frequent words from Meta's official fastText releases rather than downloading them in full; matching skips this step gracefully when it's absent. Provenance requirements are in `docs/THIRD_PARTY.md`.
