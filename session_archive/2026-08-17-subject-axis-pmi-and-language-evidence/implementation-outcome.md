# Implementation Outcome

Status: implemented, tested, and validated against real data on `architecture-srs-implementation`. Not yet committed/pushed at archival time — see repository state before assuming otherwise.

## Delivered

- **PMI collocation channel for the subject axis**: `sort_pilot/classification/subject.py` (`SubjectEvidence.pmi_collocations` field, `SubjectProfile.pmi_collocations` field, `SUBJECT_PROFILE_VERSION` bumped to `"3"`), `sort_pilot/classification/data/subject_profiles_ko.json` (18 hand-authored per-subject collocation lists), `sort_pilot/classification/e5.py` (`E5SubjectClassifier._pmi_scores`, fractional-match scoring mirroring the template axis's existing pattern).
- **Language-detection channel for the subject axis**: `E5SubjectClassifier._language_scores` — deterministic Hangul-vs-Latin character-ratio detector (`MIN_LANGUAGE_SIGNAL_LETTERS = 30`, `LATIN_SCRIPT_RATIO_THRESHOLD = 0.6`), a positive-only signal for `영어`.
- **Weight wiring**: `subject_pmi_weight` and `subject_language_weight` added to `Phase8OptionalEvidence` (version bumped to `phase-8-optional-evidence-v3`), starting values `0.05` and `0.12` respectively, wired through `service.py`'s real classification call and every calibration/ablation script (`eval/run_policy_calibration.py`, `eval/run_personal_example_calibration.py`, `eval/run_phase8_ablation.py`).
- **`classify()`'s evidence tuple** gained two new entries (`pmi_collocation`, `language_signal`), inserted between the existing `filename_alias` and `kiwi_lexical` entries to preserve existing index-based test assertions.
- **10 new tests** in `tests/test_subject_e5.py`: PMI channel structure/no-match/invalid-weight, language-signal boost/zero-on-Korean-or-short-text/invalid-weight.
- **Documentation**: `docs/FUNCTION_MAP.md` updated, this session archive, and a new dated `CHANGELOG.md` entry.

## Verification

- `python -m pytest tests/ -q`: 217 passed (up from 207), run repeatedly through implementation and after every fix.
- Real Gemma capability test performed first (see `evidence.md`): 0/12 correct, which is what motivated this deterministic approach instead of tuning Gemma further.
- Real-data validation: subject accuracy 50/62 → 62/62 on the real, ground-truth-labeled subset (extended from 50 to 62 real entries, 12 added and independently verified from actual extracted English text). Full real-pipeline coverage across all 100 real files: 41% → 49%.
- Packaged `calibrated_policy.json` and `personal_example_policy.json` re-verified against the committed invented-only corpus (`--verify-policy` passes for both) — unchanged, since the invented corpus doesn't exercise either new channel, confirming the improvement comes entirely from the new real-evidence channels rather than a recalibration side effect.
- `git diff --check`: clean.
- Real-filename leak grep across every tracked file: zero matches.
- `git status --porcelain eval/local/`: empty (git-ignored, confirmed).

## Not delivered / explicitly out of scope

- No push. Not yet committed at archival time.
- The template axis was not touched — its 6 remaining real-data misses are unrelated to this change and were already safely routed to review before and after.
- The 20 real files with no extracted text at all (unsupported formats) were not addressed — out of scope for this specific request, previously identified as a separate lever (extraction format support).
- Threshold/weight values (`0.05`, `0.12`) were validated against the available real data but not exhaustively tuned; a larger, more diverse real corpus would be needed to optimize them further.
- The real Gemma model download, the real file folder, and its ground-truth labels remain strictly local under `eval/local/`; none are part of this archive or any commit.
