# Phase 5 Evidence So Far

## Git state

- Branch: `architecture-srs-implementation`.
- Branch remained ahead of its remote by two commits.
- Latest commits remained `66f1a84` and `c9706d3`.
- Existing uncommitted Phase 0–4 work was preserved.

## Plan evidence

The supreme plan requires per-axis calibration of local acceptance, Gemma escalation, and abstention thresholds using held-out data. It describes the three routing outcomes but supplies no minimum local precision or numerical plausibility boundary.

The user supplied those values: 90% local precision and 50% Gemma-escalation top-label accuracy.

## Existing-code evidence

- `RoutingThresholds` currently contains `high_score`, `high_margin`, and `gemma_score`.
- `route_axis` already keeps explicit abstention in Needs Review and prevents Gemma from overriding a decision that clears both local gates.
- Existing educational tests use illustrative values, not held-out calibrated values.
- The legacy `classifier_engine.learning.calibrate` function has a `0.97` default, but it is not part of the supreme educational plan and calibrates only one margin threshold.

## Held-out data evidence

- File: `eval/synthetic_student_held_out_corpus.json`.
- Cases: 50.
- Catalog subjects represented: 18 of 18.
- Templates represented: 5 of 5.
- Repeated filename/text pairs from the Phase 2 corpus: 0.
- All filenames, text, and labels are made up.
- The data was created after Phase 4 and was not used to revise profiles.

## Derived policy evidence

Subject thresholds:

- local raw score: `0.8336313366889954`;
- local top-two margin: `0.02738821506500244`;
- Gemma raw score: `0.8336313366889954`.

Template thresholds:

- local raw score: `0.12044353996004377`;
- local top-two margin: `0.00011819601058959961`;
- Gemma raw score: `0.12044353996004377`.

Achieved held-out routing:

- subject local: 7/7 correct, 100%;
- subject escalation: 16/32 correct, 50%;
- subject review: 11;
- template local: 46/49 correct, 93.88%;
- template escalation: 1/1 correct, 100%;
- template review: 0.

The cache-only runner reproduced these exact values and verified `sort_pilot/classification/data/calibrated_policy.json` without writing output files.

## Verification state

- Calibration-focused tests: 10 passed.
- Calibration plus documentation tests: 12 passed.
- Phase 0–5 focused classification, evaluation, and documentation tests: 79 passed.
- Complete suite: 136 passed in 9.49 seconds; pytest exit code `0`.

The complete suite still emits the previously recorded Windows ONNX Runtime access-violation trace from the legacy vision path after the tests pass. The Phase 5 focused tests and cache-only calibration runs complete without that trace.

## Final repository verification

- `pip check`: no broken requirements found.
- `git diff --check`: passed.
- `git check-ignore -v` confirmed both the E5 model cache and `eval/local/` real-label boundary remain ignored.
- No trailing whitespace was found in the Phase 5 implementation, data, tests, runner, or archive.
- No rejected `schema`, `fixture`, `document_type`, or folder-usefulness vocabulary was found in the Phase 5 implementation, tests, data, or archive.
- Final Git status remained on `architecture-srs-implementation`, ahead by two commits, with the existing uncommitted work and new Phase 5 files visible.
- No commit or push was performed.
