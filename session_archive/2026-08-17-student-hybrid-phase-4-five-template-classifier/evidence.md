# Phase 4 Evidence

## Starting Git state

- Branch: `architecture-srs-implementation`.
- Tracking state: ahead of `origin/architecture-srs-implementation` by two commits.
- Latest local commits:
  - `66f1a84 Record student hybrid checkpoint metadata`
  - `c9706d3 Checkpoint student hybrid classifier plan`
- Existing uncommitted Phase 0–3 work and documentation moves were preserved.

## Plan evidence

The controlling Phase 4 text in `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` requires:

> Implement separate profiles and evidence weights for `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.

The plan's template-classifier section lists semantic intent, filename and lexical indicators, PMI collocations, OCR/layout evidence, optional visual evidence, and personal examples. The primary-classifier section requires natural text to remain natural and engineered values to remain structured.

## Implementation evidence

- `template_profiles_ko.json` contains exactly the five fixed labels.
- Every profile has seven explicit weights with neutral `1.0` values.
- The loader rejects missing/additional templates, additional fields, invalid evidence lists, unsupported versions, and invalid weights.
- The classifier validates the exact E5 identifier and 384-dimensional output.
- Candidate output always contains exactly the five fixed templates.
- Each result retains weighted raw score, margin, seven contributions, and versions while calibrated confidence remains absent.

## Made-up model check

The existing cache-only `intfloat/multilingual-e5-small` model classified the ten tracked made-up corpus cases using filename and natural body text. After one natural `교외활동` profile clarification, all ten expected templates were selected. Several natural-only examples had very small margins, which is retained evidence for Phase 5 rather than hidden by an invented threshold.

This is a mechanics check on made-up examples, not production accuracy or held-out calibration.

## Test evidence

- Phase 4 focused tests: 17 passed.
- Phase 0–4 classification contracts: 55 passed.
- Phase 4 plus documentation checks: 19 passed.
- Complete suite: 126 passed in 9.17 seconds; pytest exit code `0`.

The complete suite still emits the previously recorded Windows ONNX Runtime access-violation trace from the legacy vision path after the tests pass. The Phase 4 focused tests and the cache-only E5 model check complete without that trace.

## Final verification

- `pip check`: no broken requirements found.
- `git diff --check`: passed.
- `git check-ignore -v` confirmed that the reused E5 ONNX artifact remains excluded by `.gitignore`'s `data/models/*` rule.
- No trailing whitespace was found in the Phase 4 implementation, profile, test, or archive files.
- No rejected `schema`, `fixture`, `document_type`, or folder-usefulness vocabulary was found in the Phase 4 implementation, tests, or archive.
- Final Git status remained on `architecture-srs-implementation`, ahead by two commits, with the pre-existing uncommitted work and the new Phase 4 files visible.
- No commit or push was performed.
