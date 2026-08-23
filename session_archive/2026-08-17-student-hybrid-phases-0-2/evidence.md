# Evidence

## Required starting state

- Branch: `architecture-srs-implementation`.
- Remote relation at start: two local commits ahead of `origin/architecture-srs-implementation`.
- Latest commits inspected:
  - `66f1a84 Record student hybrid checkpoint metadata`
  - `c9706d3 Checkpoint student hybrid classifier plan`
  - `e168964 Add session archive for recall/precision fixes and real-world validation`
- Latest checkpoint archive read: `session_archive/2026-08-16-student-hybrid-upgrade-planning/`.
- Supreme plan read: `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`.

## Plan and reference evidence

The loose root curriculum document and its preserved superseded copy had the same SHA-256:

```text
56F576D0B8CBE4BBADA0BE40E7D0DD3A56D2291F264999CED64BD9C8579A4391
```

This established that removing the loose duplicate did not remove the preserved reference. The three superseded educational plans were read completely before their hierarchy was recorded.

## Architecture evidence

`ARCHITECTURE.md` contained 721 lines and was read completely. Its historical design includes a filesystem watcher, a second UI process, a single worker, automatic move thresholds, old storage and repository layouts, and an old real-label evaluation workflow. Those elements establish why it is marked historical and moved under `docs/`.

## Focused tests

- Phase 0 contracts: 29 passed during recovery.
- Phase 0 and Phase 1 combined: 34 passed during recovery.
- Phase 2 evaluation: 12 passed in 0.24 seconds after correcting one floating-point display artifact.
- Phase 0–2 plus documentation: 48 passed in 0.84 seconds.

The first Phase 2 test invocation used the system Python and failed because pytest was not installed there. No package was installed. The repository's existing `.venv` interpreter was used for all subsequent tests.

## Synthetic evaluation result

The tracked made-up corpus and predictions produce:

```json
{
  "cases": 10,
  "subject_accuracy": 0.7,
  "template_accuracy": 0.6,
  "combined_path_accuracy": 0.5,
  "coverage": 0.8,
  "review_rate": 0.2,
  "fallback_rate": 0.3,
  "corrections": 5,
  "latency_ms": {"mean": 23.0, "p50": 19.5, "p95": 38.85},
  "memory_mb": {"mean": 97.6, "maximum": 104.0}
}
```

These numbers validate the evaluator mechanics only. They are not claims about classifier quality because both corpus and predictions are synthetic.

## Security evidence

- `.gitignore` contains `/eval/local/`.
- The tracked corpus contains made-up filenames and text only.
- The runner accepts ordered input, prints aggregate JSON, and has no output-file option.
- A test confirms the local real-label directory remains ignored.

## Final verification

- Complete suite: 100 passed in 9.49 seconds; command exit code 0.
- Documentation callable audit: included in the complete passing suite.
- Phase 0–2 and documentation focus: 48 passed in 0.84 seconds.
- Synthetic evaluation focus: 12 passed in 0.24 seconds.
- Aggregate runner: exit code 0 and output matched the documented measures.
- `git diff --check`: exit code 0; only expected Git line-ending notices were emitted.
- New-file trailing-whitespace search: no matches.
- Rejected Phase 2 term search across active implementation, tests, plan, README, and changelog: no matches.
- `git check-ignore -v eval/local/private-labels.json`: confirmed `.gitignore` rule `/eval/local/`.
- Active architecture/SRS/third-party references point to or resolve within `docs/`.
- Final branch relation: `architecture-srs-implementation` remains two commits ahead of its remote.
- No commit or push was performed.

After all 100 tests completed successfully, the process emitted the pre-existing ONNX Runtime Windows native access-violation trace while importing `onnxruntime` through the vision path. Pytest still returned exit code 0. This is recorded as a known native-runtime reliability warning, not described as clean native shutdown and not attributed to the Phase 0–2 educational modules.
