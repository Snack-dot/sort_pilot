# Evidence

## Static verification

- Parsed all Python files under `sort_pilot/` and `tests/` with `ast.parse`: 76 files passed after implementation.
- Searched all organizer call sites and updated each to pass an explicit sandbox root.
- `git diff --check` passed; only the repository's existing Windows line-ending warnings were reported.

## Dependency-free runtime checks

- Transactional organizer: safe move and Undo inside a temporary sandbox passed.
- Boundary rejection: outside source, outside destination, and unsafe legacy Undo history were rejected before changing files.
- Legacy action executor: move and Undo inside a temporary sandbox passed; an outside source was rejected.
- Default engine configuration: watched and destination roots both resolved to `~/Downloads/sandbox`.
- Default classifier adapter: old in-memory watch/destination settings were overridden and an outside file was rejected before the extraction pipeline was called.

## Environment limitation

The declared pytest suite could not start in the current global Python because `pytest==9.1.1` and runtime dependency `stop-words==2025.11.4` are not installed. No package installation was performed without separate approval. The focused tests were added and remain ready for the documented project environment.
