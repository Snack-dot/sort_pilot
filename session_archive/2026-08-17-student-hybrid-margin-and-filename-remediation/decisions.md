# Decision Record

## D1 — Treat this as a remediation, not a new phase

**Decision:** No "Phase 9" framing anywhere — version strings, folder names, and commit messages all describe this as fixing defects in the already-shipped Phase 0-8 work.

**Rationale:** Explicit instruction from the branch owner, relaying the diagnostic report's own framing: "This should be treated as a remediation of the existing classifier, not as a new phase." Even the `Phase8OptionalEvidence` version bump went `v1` → `v2`, not to a `phase-9-*` name, specifically to honor this.

## D2 — Reuse the existing dead `SubjectProfile.keywords` field for filename aliases

**Decision:** Populate the already-declared-but-never-used `keywords: tuple[str, ...] = ()` field on `SubjectProfile` rather than inventing a new field or class.

**Rationale:** Minimal diff, and the field's existing validation (dedup, strip, tuple-of-strings) already fit the need exactly. Bumped `SUBJECT_PROFILE_VERSION` `"1"` → `"2"` since the JSON schema shape changed (each subject entry became `{prototype_texts, filename_aliases}` instead of a flat list), matching this codebase's established strict-versioning discipline for every other profile/policy file.

## D3 — Longest-alias-match, not per-subject independent scoring, for the new filename channel

**Decision:** The new subject filename channel resolves to *at most one* subject via the longest matching alias across all subjects, unlike the template axis's existing `file_name` channel (which scores every template independently and lets several templates get partial credit for the same filename).

**Rationale:** The specific defect this targets — `사회`/`통합사회` and `과학`/`통합과학` coexist in the 고등학생 catalog, and `통합사회`/`통합과학` literally contain `사회`/`과학` as substrings — requires disambiguation, not independent scoring. If both aliases matched independently the way template's do, the broader/wrong subject would always get credit alongside the specific/correct one. A load-time hygiene check rejects the same alias assigned to two different subjects; genuine equal-length ties at runtime resolve to no match at all (safer than guessing).

## D4 — Fix the calibration tie-break, then discover it wasn't sufficient by itself

**Decision:** First flipped `calibrate_axis`'s objective tuple from `-high_margin` to `+high_margin` (prefer the largest tied margin, not the smallest) — hand-verified safe against every existing test. Running the actual recalibration then showed template's margin barely moved (0.00011819... → 0.00011818...), because coverage-maximization dominates the tie-break: the algorithm will still choose a razor-thin margin over a safe one if that's what it takes to capture one more borderline held-out case, since accepted-count sits ahead of margin in the objective's priority order.

**Rationale for the follow-up fix:** Added a `minimum_margin` floor parameter to `calibrate_axis`/`calibrate_policy`, filtering candidate margins below the floor out of the search entirely — a hard constraint, not a tie-break. Empirically swept floor values against the real recalibration run: `0.02` was the smallest floor that already achieves the plateau result (template margin jumps to `0.141`, precision `95.5%→100%`; subject margin `0.0044→0.038`, precision `92.9%→96.2%`, both still clearing the 90%/50% held-out targets). Kept the tie-break fix too — it's still correct and safe, just not sufficient alone.

## D5 — Fix the calibration/production weight mismatch, including one not in the original report

**Decision:** `eval/run_policy_calibration.py` and `eval/run_personal_example_calibration.py` were both silently calibrating with `lexical_weight=0.0` (default) even though production (`service.py`) uses `subject_kiwi_lexical_weight=0.05` — meaning the packaged thresholds were never actually fit against the raw-score distribution production produces. Fixed both call sites to load `Phase8OptionalEvidence` and pass the real weights, including the new `filename_weight`.

**Rationale:** Without this fix, the new filename channel's effect wouldn't show up in recalibration at all, and the pre-existing lexical-weight gap — found independently while wiring the new channel through, not mentioned in the original report — would have stayed silently wrong right next to it.

## D6 — Expand the held-out corpus with invented cases, not real ones, for committed test data

**Decision:** Added 18 new invented cases to `eval/synthetic_student_held_out_corpus.json` (50 → 68) exercising the new subject aliases, the new template indicators, and genuine near-miss template pairs — all fabricated, none from the real report data.

**Rationale:** Explicit instruction from the diagnostic report itself: "Add tracked tests using equivalent invented filenames, not these real filenames." This is what makes the fix's logic verifiable by anyone who clones the repo, without ever touching the personal data that motivated it.

## D7 — Separately validate against the real data, kept strictly local

**Decision:** Once the branch owner made the actual real folder available locally, built a ground-truth label set (50 subject, 57 template entries, derived conservatively from literal filename evidence) and a runner script, both placed only under the git-ignored `eval/local/` directory — never staged, never committed, confirmed via `git check-ignore` and `git status` before and after.

**Rationale:** This is exactly the workflow the diagnostic report itself prescribed ("Recalibrate acceptance using these real labels locally under `eval/local/`; never commit the filenames or labels") and the existing repo convention already reserved that directory for precisely this purpose. It let the fix be validated against the exact real data that exposed the original defects, while keeping the personal data itself out of the repository entirely — only anonymous aggregate counts and generic vocabulary patterns are recorded in this archive.

## D8 — Fix a real, additional NFC/NFD Unicode bug found only by running the full real production pipeline

**Decision:** After the branch owner asked "what if you run the entire suite on those 100 files," a full-pipeline script was built (real text extraction via the actual `ClassifierEngine`, the real `EducationalClassificationService`, Gemma gracefully unavailable) instead of the earlier filename-only test. It initially showed a bizarre regression — template accuracy dropped to 0/57, all sent to review — traced to `Path(evidence.file_name).stem` containing NFD-decomposed Korean characters (macOS/APFS reports filenames pre-decomposed) failing literal substring matching against the NFC-composed indicator/alias strings in the JSON data, even though the two forms are visually identical. Fixed by NFC-normalizing both sides of every filename-indicator and filename-alias comparison (`template.py`'s `_indicator_score`, `e5.py`'s `_filename_scores`).

**Rationale:** This bug predates this remediation entirely — the *original* template `file_name` channel had the same defect for every one of its existing indicators, on any NFD-producing filesystem. It wasn't caught by the original report (its screenshots came from the app's normal usage, most likely on the branch owner's actual Windows machine, where NTFS does not decompose filenames the way macOS does) or by this remediation's own invented-corpus tests (Python string literals typed into a JSON/test file are NFC by construction regardless of host OS, so they never exercise this path). It was only found because the fix was validated against real macOS filesystem paths, not synthetic strings — directly vindicating the "empirically verify against real conditions, not just invented cases" approach used throughout. Added regression tests in both `tests/test_template_classifier.py` and `tests/test_subject_e5.py` using an explicitly NFD-decomposed string constructed in-process (`unicodedata.normalize("NFD", ...)`), so the test is portable and doesn't depend on which filesystem CI happens to run on.

## D9 — Accept the recalibrated `personal_example_policy.json` template weight jump (0.02 → 1.15) without further intervention

**Decision:** Regenerated `personal_example_policy.json` as a consequence of fixing D5's weight-passthrough bug and D6's expanded corpus, and kept the result (`template.weight` moved from `0.02` to `1.15`) as-is.

**Rationale:** Unlike the routing-margin defect, this mechanism's search objective is precision/accuracy-gated *before* any tie-break is reached (`corrections - regressions` dominates, evaluated only among candidates that already clear the 90%/50% targets on held-out data), and personal-example influence is itself gated behind a high minimum-similarity threshold (~0.886) — a large weight only fires for near-duplicate files a specific user has already corrected once, which is the intended behavior of that mechanism. The original report never flagged this axis, and second-guessing a legitimately targets-gated, data-driven result here would be scope creep beyond what was reported and verified.
