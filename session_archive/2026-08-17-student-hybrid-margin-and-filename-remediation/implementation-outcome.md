# Implementation Outcome

Status: implemented, tested, and validated against real data on `architecture-srs-implementation`. Not yet committed/pushed at archival time — see repository state before assuming otherwise.

## Delivered

- **Subject filename-alias evidence channel**: `sort_pilot/classification/data/subject_profiles_ko.json` (v2, per-subject `filename_aliases`), `subject.py` (`SUBJECT_PROFILE_VERSION` v2, populates the previously-dead `SubjectProfile.keywords`, load-time duplicate-alias rejection), `e5.py` (`E5SubjectClassifier._filename_scores` longest-match resolver, `filename_weight` parameter, new `filename_alias` evidence contribution), `optional_evidence.py` (`subject_filename_weight` field, `phase-8-optional-evidence-v2`), `service.py` (wired into the live classification call).
- **Template `file_name_indicators` data fix**: `template_profiles_ko.json` — 과제 gained `문제`/`문제지`; 학습자료 gained `정답`/`듣기대본`/`수능특강`/`수능완성` (해설 was already present, correcting the original report's claim it was missing). No code or version change needed.
- **Calibration tie-break fix + margin floor**: `calibrated_policy.py`'s `calibrate_axis` now prefers the largest tied margin (not the smallest) and accepts a `minimum_margin` floor parameter that hard-filters unsafe candidate margins out of the search entirely; `calibrate_policy` threads per-axis floors through.
- **Calibration/production weight-passthrough fix**: `eval/run_policy_calibration.py` and `eval/run_personal_example_calibration.py` now load `Phase8OptionalEvidence` and pass real `lexical_weight`/`filename_weight` instead of silently defaulting to 0.0; `eval/run_phase8_ablation.py` threads the new weight through its variant matrix and selection guard.
- **Expanded held-out corpus**: `eval/synthetic_student_held_out_corpus.json` 50 → 68 invented cases; every exact-count assertion updated (`tests/test_calibrated_policy.py`, `eval/README.md`).
- **Recalibrated, real-world-validated policy files**: `sort_pilot/classification/data/calibrated_policy.json` and `personal_example_policy.json` regenerated from the fixed, expanded corpus with the margin floor applied, then separately validated against 50/57 real labeled files without needing further adjustment.
- **NFC/NFD Unicode filename-matching fix**: found via full real-pipeline validation (real text extraction, not filename-only), not the original report. `template.py::_indicator_score` and `e5.py::_filename_scores` now NFC-normalize before comparing, fixing a pre-existing defect (not introduced by this remediation) that silently broke every filename-indicator match on macOS/APFS, which reports Korean filenames pre-decomposed.
- **Tests**: new/updated cases in `tests/test_subject_e5.py` (longest-match precedence, no-match behavior, weight wiring, invalid-weight rejection, duplicate-alias rejection, stale-assertion fixes), `tests/test_template_classifier.py` (new filename indicators), `tests/test_phase8_ablation.py` and `tests/test_personal_calibration.py` (updated field/value assertions).
- **Documentation**: `docs/FUNCTION_MAP.md` updated, this session archive, and a `CHANGELOG.md` entry.

## Verification

- `python -m pytest tests/ -q`: 205 passed, run repeatedly through the implementation and after every fix.
- Actual recalibration executed (not just planned): `fastembed==0.8.0` installed, E5 model downloaded to the git-ignored `data/models/fastembed` cache, `eval/run_policy_calibration.py` and `eval/run_personal_example_calibration.py` both run and `--verify-policy`-confirmed against the overwritten packaged JSON files.
- Real-data validation (filename-only, deliberately conservative): 50/50 subject and 57/57 template correct against a real 100-file folder (the exact dataset behind the original report), ground truth and runner kept strictly under the git-ignored `eval/local/`. Combined real+invented recalibration reproduced identical thresholds to invented-only, confirming generalization.
- Full real-pipeline validation (real text extraction, real service, Gemma gracefully unavailable): initially regressed to 0/57 template correct, which led to finding and fixing the NFC/NFD bug above. After the fix: 50/50 subject, 51/57 template correct (6 safely sent to review, none wrong-but-confident), 41% of all 100 files resolved on both axes. Full details and numbers in `evidence.md`.
- `eval/run_phase8_ablation.py ... --verify-selection` ran cleanly with the new field present.
- `git diff --check`: clean.
- Real-filename leak grep across every tracked file: zero matches.
- `git status --porcelain eval/local/`: empty (directory git-ignored, confirmed via `git check-ignore -v`).

## Not delivered / explicitly out of scope

- No push. This work is not yet committed at archival time — see the repository's actual `git log`/`git status` for current state, not this document, since commit/push timing is decided separately from implementation.
- `personal_example_policy.json`'s recalibrated `template.weight` (0.02 → 1.15) was accepted as a legitimate, targets-gated, data-driven consequence of the other fixes rather than independently re-examined — see `decisions.md` D8 for why this was judged out of the reported scope.
- The real 100-file folder, its ground-truth labels, and the runner script that used them remain local-only under `eval/local/`; they are not part of this archive, any commit, or any other file this session touched.
