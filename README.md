# Sort Pilot

Sort Pilot is a Windows tray application that organizes safe top-level files from the Desktop and Downloads. All content extraction and Gemma inference stay on the local PC, and no file is moved before the user approves the preview.

## Current workflow

```text
Tray action (Desktop / Downloads / both)
→ user role selection (teacher / student / office worker)
→ safe candidate filtering
→ content-hash cache lookup
→ two-worker bounded text/OCR extraction for uncached files
→ extraction failures become Misc/Needs review
→ local Gemma classifies remaining files in batches of five
→ each valid result is cached immediately
→ editable 2–3 level organization-path preview
→ explicit approval and original-name moves
→ atomic JSON history and restart-safe Undo
```

There is no Tier-1 rule classifier, Naive Bayes model, decision database, background watcher, topic-profile calibration, or folder-migration workflow in the active application. File names, file families, and extracted terms are evidence for the local LLM; the LLM alone selects the role-aware organization path.

## Local extraction interface

`ClassifierEngine` is retained as the stable extraction interface. It does not make the final role-aware folder decision and does not create a decision database.

```python
from pathlib import Path
from sort_pilot.classifier_engine import ClassifierEngine

analyzer = ClassifierEngine()
record = analyzer.analyze_record(Path("C:/Users/user/Downloads/운영체제과제.pdf"))
print(record.terms)
print(record.content_extraction_failed)
```

The compatibility JSON methods still return a fixed file family with the `미분류` fallback:

```python
{
    "filepath": "C:/Users/user/Downloads/운영체제과제.pdf",
    "folder": "문서/미분류"
}
```

The tray workflow passes the extraction record to `LlmFileClassifier`, which applies the selected role template and produces the actual destination.

## Features and safety

- Manual Desktop, Downloads, or combined organization.
- User type can be changed from the tray at any time while idle.
- TXT, Markdown, CSV, RTF, IPYNB, PDF, DOCX, ODT, PPTX, XLSX, and image OCR extraction.
- IPYNB extraction reads Markdown/code cell sources and excludes outputs.
- `.zip`, `.winmd`, executables, shortcuts, temporary downloads, HWP, and HWPX are excluded.
- Failed supported-content extraction is sent directly to `기타/확인필요` and is not cached.
- On first classification, the app requests Gemma-terms consent and downloads the pinned Gemma and CPU `llama-server` artifacts with progress and cancellation.
- Downloaded AI artifacts are size/hash verified; Gemma requests contain only bounded file metadata and extracted terms and run on `127.0.0.1`.
- Five files are requested per LLM batch; missing results are retried up to two times.
- Folder output is schema-constrained, validated to 2–3 relative levels, and rejects full filenames or extensions as topic folders.
- Successful classifications are cached per file content, role, model, prompt version, and template version.
- Original filenames are preserved; collisions receive numeric suffixes.
- No move occurs before final approval.
- Completed move batches are stored atomically in `history.json` and can be undone after restart.
- A Qt lock prevents two Sort Pilot instances from running simultaneously.
- No cloud inference or file upload.

## Development and verification

Python 3.11–3.13 is recommended. Python 3.14 runs the app but skips optional YOLO inference because ONNX Runtime 1.27 can terminate that interpreter while creating the model session on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m pytest -q
```

Tests do not require the 806 MB model. Run the source application with:

```powershell
python main.py
```

The app has no main window. Right-click the `SP` system-tray icon to organize files, change the user type, undo the latest batch, or quit. The first organization request installs the local model only after explicit consent; later classifications reuse it offline.

## Repository layout

```text
main.py                              desktop entry point
sort_pilot/app.py                    tray workflow and UI coordination
sort_pilot/analysis_queue.py         cancellable extraction sessions
sort_pilot/classifier_engine/        extraction, file family routing, OCR, vision
sort_pilot/model_setup.py            first-use model consent and progress UI
sort_pilot/local_tagger.py           verified Gemma/llama.cpp installation and inference
sort_pilot/llm_file_classifier.py    role prompts, cache, validation, fallbacks
sort_pilot/preview.py                organization-path review and approval
sort_pilot/organizer.py              safe moves, rollback, collision handling, Undo
sort_pilot/history.py                atomic move history and legacy history migration
tests/                               extraction, LLM, queue, UI, and move tests
docs/FUNCTION_MAP.md                 callable ownership and call-flow map
```

`%APPDATA%\tidy` stores private extraction settings, classification cache, and the consented local model/runtime. Legacy `state.db`, classifier weights, calibration state, and topic-profile files may remain after upgrade but are no longer opened by the application.
