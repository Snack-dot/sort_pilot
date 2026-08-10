# AI File Organizer MVP

A lightweight desktop application that watches for newly downloaded files, classifies them, and suggests an appropriate folder.

The application runs in the background using the system tray.

Current flow:

    New file detected
    → classifier.py
    → classification result
    → user approval
    → organizer.py
    → create folder if needed
    → move file

The AI must never move, delete, or directly modify user files.

---

# Current Status

The desktop application flow is already implemented.

Main components:

    main.py
    app_controller.py
    tray.py
    watcher.py
    filters.py
    classifier.py
    organizer.py
    popup.py
    batch_scanner.py
    batch_preview.py

The current `classifier.py` is only a temporary rule-based classifier using filenames and extensions.

Example:

    운영체제_과제.pdf → 학교
    회사_회의록.docx → 업무
    쿠팡_영수증.png → 금융
    사진.jpg → 이미지

The current development task is to replace this rule-based logic with a local AI classifier.

---

# My Development Scope

My responsibility in this project is the classifier and local AI integration.

Primary file:

    classifier.py

New modules may be created if they are necessary for classifier functionality.

Possible examples:

    extractors/
    local_ai/

Keep the implementation as small and simple as possible.

Do not redesign unrelated parts of the project.

---

# CRITICAL RULES FOR CODEX

Before making changes:

1. Read this README.
2. Read `classifier.py`.
3. Find where `classifier.py` is called.
4. Check what return structure other modules expect.
5. Preserve compatibility with the existing application.

# External Downloads and Installation Rules

Do not download or install external executables, models, Python packages,
or dependencies without explicit approval.

Before any installation or download, YOU MUST:

1. State the exact package or file name.
2. State the official source.
3. Explain why it is required.
4. State the version.
5. Wait for explicit approval.

Do not proceed until approval is given.

Whenever practical, classifier-related dependencies MUST be installed locally
to this project.

Do NOT:

- install dependencies system-wide
- modify the system PATH
- install global Python packages
- place model or runtime files outside the project without approval

If a system-wide installation or PATH change is required, explain why and wait
for explicit approval before proceeding.

## Do not modify other modules without permission

You may READ other files to understand how the classifier is connected.

However, do NOT modify files outside the classifier scope unless it is absolutely necessary.

If another module must be changed:

1. Stop before modifying it.
2. Tell me exactly which file needs to change.
3. Explain why the change is required.
4. Explain what needs to change.
5. Wait for my explicit approval.

Only modify it after approval.

This applies especially to:

    watcher.py
    organizer.py
    filters.py
    app_controller.py
    tray.py
    popup.py
    batch_scanner.py
    batch_preview.py
    main.py

## Do not delete or rewrite existing code on your own

Never remove, replace, or refactor existing code just because you think it is cleaner.

Do NOT perform unsolicited:

- function deletion
- class deletion
- file deletion
- logic removal
- interface changes
- large refactoring
- renaming
- unrelated cleanup
- unrelated optimization

If deletion or modification of existing behavior is required, explain it first and wait for approval.

General rule:

    Add only what is necessary.
    Preserve existing behavior.
    Do not remove existing code without permission.
    Do not modify unrelated code without permission.

Finding a problem does NOT mean you should automatically fix it.

Report unrelated problems instead.

---

# Classifier Interface

The current classifier return format should be preserved unless a change is explicitly approved.

Expected structure:

    {
        "file_path": "C:/Users/user/Desktop/example.pdf",
        "file_name": "example.pdf",
        "folder": "학교",
        "reason": "학교 관련 파일로 판단했습니다."
    }

Internal fields such as `confidence` may be added later if useful, but existing required fields must not be removed or renamed without approval.

The AI only returns a classification result.

It must NOT:

- move files
- delete files
- create files
- execute shell commands
- overwrite files

Filesystem operations remain the responsibility of `organizer.py`.

---

# Local AI Architecture

No external AI API will be used.

User files must remain on the user's computer.

Do NOT use:

- OpenAI API
- Anthropic API
- Gemini API
- cloud inference APIs
- file upload services

AI inference must run locally.

Current first model candidate:

    Qwen3-VL-2B-Instruct

Current runtime direction:

    GGUF
    + llama.cpp
    + Q4_K_M quantization for initial testing

This is the first benchmark candidate, not yet a permanently fixed model.

The final model should be selected based on actual performance on this project.

Important evaluation criteria:

- Korean and English document understanding
- image understanding
- PDF document understanding
- CPU-only performance
- memory usage
- model size
- structured output reliability

GPU must not be required.

Target environment:

    Minimum: 8 GB RAM, CPU-only capable
    Recommended: 16 GB RAM

Because classification happens in the background, several seconds of processing time per file may be acceptable.

---

# Supported AI Scope for MVP

Content-aware classification should initially focus on:

- TXT
- Markdown
- PDF
- DOCX
- PPTX
- XLSX
- JPG
- JPEG
- PNG
- WEBP

Audio and video content analysis are NOT part of the current classifier MVP.

Examples:

    MP3
    WAV
    MP4
    MOV
    MKV

These may be handled later using simple extension-based rules instead of AI content analysis.

---

# Preprocessing Strategy

Do not send unnecessarily large raw files directly into the model.

Use lightweight local preprocessing first.

Examples:

    TXT / MD
    → read text
    → local AI

    DOCX
    → extract text
    → local AI

    PPTX
    → extract slide text
    → local AI

    XLSX
    → extract sheet names and representative cells
    → local AI

    Image
    → resize if necessary
    → local VLM

    PDF
    → extract text first
    → if text is insufficient, render selected page images
    → local VLM

Possible libraries:

- PyMuPDF
- python-docx
- python-pptx
- openpyxl
- Pillow

Avoid adding separate AI models unless necessary.

The goal is to use one lightweight local VLM where possible.

---

# System Tray Behavior

The application runs without a main window.

System tray menu:

    Desktop Cleanup
    ----------------
    Pause Watching / Resume Watching
    ----------------
    Exit

`Exit` should safely stop the watchdog observer, remove the tray icon, and terminate the PyQt application.

This functionality already exists and is outside the classifier task.

Do not modify it unless explicitly approved.

---

# Development Environment

Recommended:

    Python 3.11.9
    PyQt6 6.7.1
    watchdog 4.0.1

Setup:

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python main.py

The application normally runs in the system tray without showing a main window.

---

# Current Classifier Task

The immediate goal is:

    existing rule-based classifier
    → local file preprocessing
    → local Qwen3-VL inference
    → parse structured result
    → preserve existing classifier return format

Do not start by rewriting the whole project.

First inspect the current code and determine the smallest change required inside the classifier scope.

Before implementing changes, report:

- which files you intend to modify
- which files you intend to create
- whether any non-classifier module would need modification

If another developer's module needs modification, wait for approval before touching it.

After implementation, report:

- modified files
- newly created files
- deleted files, if any
- whether any external module was changed
- interface changes, if any
- test results