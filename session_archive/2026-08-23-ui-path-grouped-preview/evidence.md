# Verification Evidence

## Passing checks

- `python -m pytest tests/test_educational_preview.py tests/test_documentation.py -q` → 14 passed.
- The focused UI coverage verifies destination grouping, alphabetical representative selection, `파일명 외 N개`, Needs Review ordering, summary-row filtering, and approved-count button text.
- Broader Python 3.14 run excluding `tests/test_onboarding.py` → 211 passed, 1 unrelated analysis-queue timeout.
- Re-running that analysis-queue test alone produced the same 5-second timeout; no UI code is on that path.
- The task-scoped UI, test, documentation, changelog, and archive diff passes `git diff --check`.

## Environment limitation

The full suite cannot be collected with the machine's default Python 3.14 because `onnxruntime==1.27.0` fails to load its native DLL while importing `sort_pilot.app`. The repository recommends Python 3.11; that interpreter is present but does not currently have the pinned project dependencies installed.
