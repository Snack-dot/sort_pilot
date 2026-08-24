# Sort Pilot

Sort Pilot is a Windows system-tray application that analyzes safe files on the Desktop and in Downloads, classifies the independent subject and template axes locally, and moves only files whose exact destination paths the user approves.

## Current workflow

```text
Tray action (Desktop / Downloads / both)
→ first-run student type / grade / semester setup
→ safe top-level candidate collection
→ deduplicated two-worker bounded extraction queue
→ independent catalog-bounded subject and five-template ranking
→ calibrated local acceptance / constrained Gemma fallback / Needs Review
→ fixed-choice subject and template preview
→ unresolved axes require user selection
→ explicit final approval freezes exact source and destination paths
→ exact original-name or collision-suffixed file moves
→ corrected decisions stored locally as separate personal examples
→ atomic JSON history and restart-safe Undo
```

There is no real-time filesystem watcher. Manual organization avoids repeated background scans, and each extraction worker reuses one local RapidOCR engine. The active destination hierarchy is exactly `학생/<학생 유형>/<학년>/<학기>/<과목>/<템플릿>`.

## Lower-level extraction interface

`ClassifierEngine` remains the lower-level extraction and compatibility interface used by the queue. Its historical type/topic fields are not educational classification axes and are not used to build the active destination. The educational result is produced by `EducationalClassificationService` and contains only subject and template decisions.

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

`analyze_json` and `analyze_many_json` are retained compatibility calls. The tray workflow consumes `AnalysisRecord` extraction evidence and disregards the historical type/topic destination returned by those calls.

## Features and safety

- First-run student setup stores only the fixed `학생` occupation, `중학생|고등학생`, grade 1–3, semester 1–2, and `KR_STUDENT_2026_MVP_V1` catalog version; it does not collect a school, institution, or timetable.
- Phase 2 evaluation uses a tracked, made-up student corpus and reports subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory. Unresolved results are incorrect for all applicable accuracy measures.
- Phase 3 provides natural-language profiles for every catalog subject and a CPU-only `intfloat/multilingual-e5-small` ranker. It validates 384-dimensional vectors, compares only the selected student type's catalog subjects with NumPy cosine similarity, and retains raw similarity and top-two margin without calling either value confidence.
- Phase 4 provides separate profiles and explicit evidence weights for exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. It ranks all five with natural semantic intent plus separate filename, lexical, PMI-collocation, OCR/layout, optional visual, and personal-example evidence, retaining raw score and margin without calibrated confidence.
- Phase 5 calibrates subject and template policy independently from 50 new made-up held-out cases. Authoritative local routes must achieve at least 90% held-out precision; the Gemma-escalation region must achieve at least 50% held-out top-label accuracy; weaker evidence remains Needs Review.
- Phase 6 provides a constrained local Gemma fallback only for a subject or template axis that Phase 5 routed as plausible but ambiguous. Each request contains ranked supplied candidates and bounded extracted evidence; valid output is one exact supplied candidate or Needs Review. Invalid or unavailable results remain Needs Review, while retry, cancellation, and a local hash-keyed cache reuse the reliable `fix`-branch behavior without allowing Gemma to return a path.
- Phase 7 connects those components to the tray workflow. It exposes unresolved subject/template axes for fixed-choice selection, freezes exact collision-resolved paths at final approval, executes those paths without reclassification, preserves transactional move and persistent Undo behavior, and stores only genuine corrections as separate local personal examples.
- Phase 8 retains only the optional evidence justified by paired made-up development and held-out measurements: layout-aware OCR, a bounded `0.05` Kiwi lexical contribution for subject ranking, and PMI. The active template classifier keeps the original OCR order for semantic intent and receives separate layout indicators. YOLO/LVIS visual evidence and new model-session scheduling are disabled.
- Personal examples contain a fingerprint, normalized embedding, approved subject/template, original prediction, bounded lexical evidence, and relevant versions. They contain no source path or raw extracted text, do not fine-tune E5 or Gemma, and do not mutate global subject/template profiles.
- Calibrated nearest-example evidence uses separate subject and template weights derived from made-up held-out data while retaining the Phase 5 routing thresholds and the approved 90%/50% operating targets.
- Manual Desktop, Downloads, or combined organization.
- Exactly two classification workers; duplicate paths are processed once per session.
- One reusable classifier pipeline, SQLite connection, and RapidOCR instance per worker thread.
- Cancellable extraction, local E5 classification, and Gemma fallback with no partial preview after cancellation.
- Local document, archive, image metadata, and layout-aware OCR extraction. The active educational flow does not run YOLO/LVIS.
- The preview allows only the selected student's catalog subjects, the five fixed templates, and Desktop or Downloads as the destination root. One top-level destination choice applies to every path group, while each group remains available for exceptions.
- Original filenames are preserved; collisions receive numeric suffixes.
- No move plan exists while either axis is unresolved, and no move occurs before final approval.
- Execution consumes the frozen `OrganizationPlan` and never recomputes classification.
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

### UI-only test mode

Set `SORT_PILOT_SIMPLE_CLASSIFIER=1` to bypass E5/Gemma classification with deterministic extension rules while testing the preview. This explicit mode labels itself in the preview and never moves files or stores personal correction examples after approval. The checked-in code keeps normal AI classification as the default; the local VS Code launch configuration may set this variable for UI work.

For a completely standalone preview with no scan, E5, Gemma, history, or file move services, run `python ui_demo.py`. The VS Code `Sort Pilot UI Preview (No AI)` launch configuration points directly to this sample-data window.

## Repository layout

```text
main.py                            desktop entry point
sort_pilot/app.py                  tray workflow and UI coordination
sort_pilot/analysis_queue.py       deduplicated two-worker analysis sessions
sort_pilot/onboarding.py           fixed-choice student setup dialog
sort_pilot/classification/         two-axis contracts, classifiers, policy, and constrained Gemma fallback
sort_pilot/educational_preview.py  fixed-axis review and immutable approved plans
sort_pilot/evaluation/             strict made-up corpus loading and evaluation measures
sort_pilot/local_tagger.py         pinned Gemma/llama.cpp installation support
sort_pilot/classifier_engine/      bounded extraction and retained compatibility engine
sort_pilot/history.py              atomic JSON move history and SQLite migration
sort_pilot/organizer.py            frozen-path moves, rollback, and Undo
tests/                             app, queue, contract, and engine tests
eval/                              aggregate runners and tracked synthetic student examples
docs/ARCHITECTURE.md               historical legacy-classifier architecture reference
docs/FUNCTION_MAP.md               complete function ownership and call-flow map
docs/INTEGRATION_PROCESS.md        app-branch integration record
docs/HIERARCHICAL_TOPICS.md        type/topic model, TF-IDF, profiles, and migration
docs/SRS.md                        historical legacy-classifier requirements
docs/THIRD_PARTY.md                dependency and model-artifact inventory
```

The retained extraction engine keeps its compatibility state under `%APPDATA%\tidy`. Those historical decisions do not select the educational subject, template, or destination. Move history and the single-instance lock use Qt's Sort Pilot application-data directory.

The student onboarding profile is stored atomically as `student_profile.json` in Qt's Sort Pilot application-data directory. Preview corrections are stored separately as `personal_examples.json`; Gemma cache entries are stored as `gemma_fallback_cache.json`. Both are private local state and are also named in `.gitignore` as an additional guard.

Phases 3–8 are wired into the active organization workflow. Both classifiers reuse the local E5 encoder; FastEmbed loads `data/models/fastembed/` without network access and forces ONNX Runtime's `CPUExecutionProvider`. Phase 5 centralizes the independent routing thresholds, Phase 6 reuses the consent-gated Gemma and llama.cpp artifacts, Phase 7 adds the independently calibrated personal-example rule, and Phase 8 adds only the measured OCR-layout/Kiwi selection. Downloaded E5 and Gemma artifacts remain Git-ignored.

Only made-up student evaluation cases and labels are tracked. Any evaluation using real local files, filenames, extracted text, labels, predictions, corrections, or results belongs under the Git-ignored `eval/local/` directory and must never be committed or uploaded to GitHub. The Phase 2 runner prints aggregate measures and writes no evaluation output.

The retained legacy vision model (`data/models/yolov8n.onnx`, ~13MB) is not invoked by the active educational flow after the Phase 8 ablation. Larger binaries are not committed. After consent, the app downloads the pinned 806MB Gemma GGUF and llama.cpp Windows CPU runtime, verifies their SHA-256 digests, and runs inference only on `127.0.0.1`. If installation or a given cluster's naming request fails, that cluster's deterministic collocation-aware name keeps calibration usable. The optional semantic-rescue word vectors (`data/models/word_vectors.npz`, ~112MB) are built locally after a separate consent prompt, streaming only the most frequent words from Meta's official fastText releases rather than downloading them in full; matching skips this step gracefully when it's absent. Provenance requirements are in `docs/THIRD_PARTY.md`.
