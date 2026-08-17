# Phase 7 Evidence

## Authority and checkpoint review

Read before editing:

- `docs/AGENTS.md`;
- `README.md`;
- `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`;
- every file in `session_archive/2026-08-17-student-hybrid-phase-6-constrained-gemma-fallback/`;
- current educational classification, preview, organizer, tray, and application modules;
- Git status, branch, and latest five commits.

The active branch was `architecture-srs-implementation`, two commits ahead of its remote tracking branch. The latest commits before editing were `66f1a84 Record student hybrid checkpoint metadata` and `c9706d3 Checkpoint student hybrid classifier plan`. The existing dirty worktree from Phases 0–6 and documentation moves was preserved.

## Made-up calibration reproduction

Command:

```powershell
.\.venv\Scripts\python.exe eval\run_personal_example_calibration.py eval\synthetic_student_corpus.json eval\synthetic_student_held_out_corpus.json --model-cache data\models\fastembed --verify-policy sort_pilot\classification\data\personal_example_policy.json
```

Result: exit code 0 in 80.6 seconds. The recomputed policy exactly matched the packaged JSON.

Subject results over 50 made-up held-out cases:

- authoritative local: 8/8 correct, precision `1.0`;
- Gemma-routed top label: 17/31 correct, accuracy `0.5483870967741935`;
- Needs Review: 11;
- corrected top labels: 2;
- regressions: 0.

Template results over 50 made-up held-out cases:

- authoritative local: 47/49 correct, precision `0.9591836734693877`;
- Gemma-routed top label: 1/1 correct, accuracy `1.0`;
- Needs Review: 0;
- corrected top labels: 1;
- regressions: 0.

The runner printed aggregate results and wrote nothing.

## Focused verification

The final combined Phase 7/classifier/documentation command passed `69` tests. Additional focused groups passed `37`, `27`, `23`, `18`, and `12` tests while service, preview, personal storage/calibration, application, exact confirmation, and provenance issues were developed and reviewed.

## Complete verification

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Results:

- complete suite: `174 passed in 9.77s`, exit code 0;
- dependency check: `No broken requirements found.`;
- whitespace check: no errors, only existing LF-to-CRLF conversion warnings.

Two intermediate all-in-one reruns were interrupted during the known native ONNX Runtime import in the legacy vision test. That test passed by itself. A process-sensitive Qt dialog test was also replaced with a pure exact-confirmation test because earlier queue tests intentionally retain a `QCoreApplication`. The final all-in-one run then completed all 174 tests with exit code 0.

After the final pytest run reported success, the legacy Windows vision path again printed its ONNX Runtime access-violation traceback. The command still returned exit code 0 and all 174 tests passed. The trace originated in `classifier_engine/vision.py`, not in the Phase 7 service.

## Privacy and repository evidence

- Every calibration and test filename, text, label, prediction, and correction was made up.
- No real local file, filename, extracted text, label, prediction, or correction was used.
- `eval/local/` remains Git-ignored.
- `personal_examples.json` and `gemma_fallback_cache.json` are explicitly Git-ignored.
- A recursive workspace check found no personal-example or Gemma-cache file.
- No network call or model download was made.
- No live move, deletion, commit, or push was performed.
