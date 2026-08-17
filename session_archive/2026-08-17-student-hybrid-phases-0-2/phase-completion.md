# Phase Completion Record

## Phase 0 — Remediate the foundation

Completed behavior:

- exactly subject and template axes;
- no `document_type` axis;
- complete per-axis representation and validation;
- subject labels and candidates bounded to the selected catalog;
- exactly five template labels and candidates;
- unresolved axes represented as review state;
- unresolved folder rendering and `OrganizationPlan` construction rejected;
- exact source/destination hierarchy and original filename enforced;
- catalog and student-profile documents reject missing or additional fields;
- active production classifier behavior remains separate from the educational contracts.

Focused evidence: `tests/test_education_contracts.py` passed 29 tests during recovery.

## Phase 1 — Subject catalog and onboarding persistence

Completed behavior:

- packaged inspectable `subjects_2026.json` catalog;
- persisted occupation, student type, grade, semester, and catalog reference only;
- atomic profile storage;
- onboarding limited to approved fixed choices;
- saved profile required before startup continuation, calibration, migration, organization collection, analysis, and preview;
- no institution, timetable, curriculum-transition, or school-specific data.

Focused evidence: Phase 0 and Phase 1 tests passed 34 tests together during recovery.

## Phase 2 — Evaluation framework

Completed behavior:

- labeled synthetic corpus containing made-up cases only;
- strict corpus and prediction JSON loading;
- no invented case IDs;
- ordered case/prediction matching;
- subject accuracy;
- template accuracy;
- combined-path accuracy;
- coverage;
- review rate;
- fallback rate;
- corrections;
- latency;
- memory;
- unresolved axes counted as incorrect;
- aggregate-only runner output;
- Git-ignored `eval/local/` boundary for all real-label material;
- tests and documentation;
- no folder usefulness measure.

Focused evidence: `tests/test_student_evaluation.py` passed 12 tests. Combined Phase 0–2 plus documentation tests passed 48 tests.

## Next phase boundary

Phase 3 has not started. Phases 0–2 passed the focused, full-suite, documentation, whitespace, active-reference, runner, ignore-rule, and Git-state verification required by the supreme plan. A later session may begin Phase 3 only by reading the supreme plan and this archive first.
