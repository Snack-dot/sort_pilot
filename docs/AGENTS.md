# Repository Guidelines

## Project Structure & Module Organization

The application lives in `ai-file-organizer-team-mvp-fixed/`. `main.py` starts the PyQt6 tray application, while `app_controller.py` coordinates the UI and file-watching flow. `watcher.py` detects completed downloads; `filters.py` excludes temporary or irrelevant files; `classifier.py` returns folder suggestions; and `organizer.py` performs approved moves. UI code is split across `tray.py`, `popup.py`, and `batch_preview.py`; desktop discovery belongs to `batch_scanner.py`. `README.md` documents the current classifier contract and development boundaries. No automated test or asset directories currently exist.

## Build, Test, and Development Commands

Run commands from the application directory:

```powershell
cd ai-file-organizer-team-mvp-fixed
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

The first two commands create and activate an isolated environment; installation provides pinned PyQt6 and watchdog versions. `python main.py` launches the background system-tray application. There is no build step or configured test runner yet. Installing packages, models, runtimes, or executables requires explicit approval; identify the source and exact version first.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` for functions and modules, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Prefer `pathlib.Path`, type annotations, small focused functions, and explicit imports. Keep module responsibilities intact and avoid unrelated refactors. No formatter or linter is configured, so match the surrounding code.

## Testing Guidelines

For changes, perform focused manual checks and report what was exercised. Classifier work should verify the required keys `file_path`, `file_name`, `folder`, and `reason`, including representative Korean and English filenames. Never let classifier tests move, delete, overwrite, or upload user files. If adding automated tests, place them under `tests/`, name files `test_<module>.py`, and use `pytest` only after dependency approval.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout. Use short, imperative commit subjects such as `Preserve classifier fallback result`. Keep each commit scoped. Pull requests should explain behavior changes, list files touched, include manual test results, link relevant issues, and attach screenshots for tray or dialog changes.

## Safety & Scope

Read `README.md` before editing. Preserve the classifier return interface and keep inference local; cloud AI APIs and file-upload services are prohibited. Do not modify non-classifier modules or remove existing behavior without explicit approval; report unrelated problems instead.
