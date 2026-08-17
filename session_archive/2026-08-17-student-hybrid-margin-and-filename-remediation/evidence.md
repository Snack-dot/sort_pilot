# Evidence

## Root cause 1 — no subject filename channel (code-verified)

`sort_pilot/classification/e5.py`'s `E5SubjectClassifier.classify()` combined only three channels before this fix: E5 cosine similarity (filename+body jointly embedded into one string, diluting literal tokens), a personal-example channel, and a Kiwi lexical channel fed exclusively from body/OCR text (`sort_pilot/classification/service.py`'s `classify_many`: `SubjectEvidence(item.file_name, item.natural_text, item.lexical_evidence, personal.subject)` — `lexical_evidence` is body/OCR terms, never filename tokens). The template axis already had an equivalent `file_name` channel (`TemplateClassifier._channel_scores` in `template.py`); the subject axis did not. `SubjectProfile.keywords` existed as a dataclass field but was validated and never populated — confirmed by the pre-fix test `tests/test_subject_e5.py::test_natural_language_profiles_cover_exact_catalog_subjects` asserting `all(profile.keywords == () for profile in profiles)`.

## Root cause 2 — calibration tie-break and coverage-maximization (code-verified, then empirically confirmed insufficient alone)

`calibrate_axis` in `sort_pilot/classification/calibrated_policy.py` grid-searches all observed `(raw_score, margin)` pairs and picks the argmax of an objective tuple. The original tuple's `-high_margin` term meant: among threshold combinations tied on coverage/precision/accuracy, prefer the *smallest* available margin. Flipping this sign (D4) was hand-verified safe against `tests/test_calibrated_policy.py` (no test asserts a specific `high_margin`/`high_score` value) and confirmed with `python -m pytest tests/test_calibrated_policy.py -q` → 10 passed both before and after.

Running the actual recalibration after the sign flip showed the fix alone was insufficient: template's margin moved from `0.00011819601058959961` to `0.00011818749564034003` — functionally unchanged — because `accepted` count sits ahead of `high_margin` in the objective's priority order, so the search still preferred a razor-thin margin over a safe one when it bought one extra accepted case (67/68 on the corpus at the time). Added a `minimum_margin` floor parameter instead (a hard filter on candidate margins, not a tie-break), swept empirically:

```
=== TEMPLATE margin floors (68-case invented held-out corpus) ===
floor=0.000  high_margin=0.00012  accepted=67  precision=0.955  escalated=1   acc=1.000  reviewed=0
floor=0.020  high_margin=0.14096  accepted=40  precision=1.000  escalated=28  acc=0.893  reviewed=0
floor=0.050  high_margin=0.14096  accepted=40  precision=1.000  escalated=28  acc=0.893  reviewed=0
floor=0.100  high_margin=0.14096  accepted=40  precision=1.000  escalated=28  acc=0.893  reviewed=0
floor=0.150  FAILED: no threshold combination meets the approved targets

=== SUBJECT margin floors ===
floor=0.000  high_margin=0.00436  accepted=28  precision=0.929  escalated=2   acc=0.500  reviewed=38
floor=0.020  high_margin=0.03778  accepted=26  precision=0.962  escalated=4   acc=0.500  reviewed=38
floor=0.050  high_margin=0.10434  accepted=24  precision=0.958  escalated=34  acc=0.500  reviewed=10
```

`0.02` was selected: it already reaches the plateau result for template, and for subject it materially improves precision (92.9% → 96.2%, fixing two real wrong-but-confident subject decisions the new filename channel had itself introduced) while both axes still clear the approved 90%/50% held-out targets.

## Final packaged thresholds (invented 68-case held-out corpus, `sort_pilot/classification/data/calibrated_policy.json`)

```
subject:  high_score=0.8616471886634827  high_margin=0.037775516510009766  gemma_score=0.8616471886634827
          accepted=26/26 correct=25 (96.15% precision) | escalated=4 correct=2 (50.0% accuracy) | reviewed=38
template: high_score=0.12044354847499303 high_margin=0.14095800263541086   gemma_score=0.12044354847499303
          accepted=40/40 correct=40 (100% precision)   | escalated=28 correct=25 (89.3% accuracy) | reviewed=0
```

Both clear the approved `CalibrationTargets(local_precision=0.90, gemma_accuracy=0.50)`. Reproducible with:
```
python -m eval.run_policy_calibration eval/synthetic_student_held_out_corpus.json --model-cache data/models/fastembed --verify-policy sort_pilot/classification/data/calibrated_policy.json
```

## Real-data validation (never committed — see `eval/local/`, git-ignored)

The branch owner made the exact real folder behind the original diagnostic report available locally (`~/Downloads/2027 수능특강 독서`, 100 real files — the same dataset the original 62-file report was drawn from). Ground-truth labels were built for 50 subject and 57 template cases from literal filename evidence (plus a few subject labels the original report had already confirmed the base E5 classifier got right without any filename help). Running the fixed classifier, filename-only (empty body text, deliberately conservative), against these real files:

```
SUBJECT:  50/50 correct
TEMPLATE: 57/57 correct
```

Every case the original report specifically flagged as a miss or a silent wrong auto-route resolved correctly, including two 국어-subject double-miss cases the report quoted verbatim, and the two math-subject files the report showed being silently auto-routed to the wrong template (one containing a `문제지` filename token, previously routed to 교내활동; one containing a `문제` filename token, previously routed to 증빙서류) — both now resolve to 과제.

Recalibrating against the real 50/57 cases combined with the invented 68-case corpus produced **identical threshold values** to the invented-only calibration — the already-packaged thresholds generalize to the real data without adjustment, and precision on the combined set is even higher (subject 98.7%, template 100%).

Coverage across all 100 real files (not just the labeled subset), filename-only, against the packaged policy:

```
both axes auto-accepted (concrete destination): 46/100 = 46.0%   (originally reported: 16.1%)
subject=needs_review, template=gemma_fallback:  25/100
subject=needs_review, template=accept_local:    15/100
subject=needs_review, template=needs_review:     8/100
subject=accept_local, template=gemma_fallback:   6/100
```

The one file the original report itself was uncertain about (a regional education-office exam-analysis document with no literal subject or template token in its filename) now correctly falls to `NEEDS_REVIEW` (subject, margin 0.0035 < floor 0.038) and `GEMMA_FALLBACK` (template, margin 0.0011 < floor 0.141) rather than being silently guessed — direct confirmation the margin floor prevents exactly the danger the report flagged, on the exact ambiguous case it raised.

## Full real production pipeline validation (real text extraction, not filename-only)

Prompted by "what if you run the entire suite on those 100 files," a second, more thorough validation ran the *actual* `EducationalClassificationService` (real PDF/DOCX text extraction via `ClassifierEngine`, Kiwi lexical terms, PMI collocations, OCR layout evidence where applicable, Gemma fallback gracefully reporting "unavailable" since no local model is installed in this environment) against the same 100 real files, instead of the deliberately simplified filename-only test.

The first run of this fuller test produced a bizarre regression — template accuracy 0/57, everything sent to review — which led to finding an additional, real bug: `Path(evidence.file_name).stem` on this machine returns NFD-decomposed Korean text (confirmed directly: `'해설' in Path(raw_macos_filename).stem` → `False`, `'해설' in Path(nfc_normalized_filename).stem` → `True`), which silently fails substring-containment matching against the NFC-composed indicator/alias strings in the packaged JSON data. This predates this remediation — the original template `file_name` channel had the identical defect for every one of its indicators, on any NFD-producing filesystem (macOS/APFS; not Windows/NTFS, which is why the original report's own observations weren't caused by this). Fixed by NFC-normalizing both sides of the comparison in `template.py::_indicator_score` (new `_normalize_match_text` helper) and `e5.py::_filename_scores`.

After the fix, re-running the full pipeline against all 100 real files:

```
both axes resolved (concrete destination): 41/100 = 41.0%
subject sent to review: 46/100
template sent to review: 45/100

SUBJECT accuracy vs ground truth:  50/50 correct
TEMPLATE accuracy vs ground truth: 51/57 correct (6 sent to Needs Review, none wrong-but-confident)
```

The 6 template cases that moved from "correct via filename alone" to "sent to review" under the full pipeline did so because real extracted body text sometimes pulls the E5 semantic-intent channel's contribution in a slightly different direction than the filename alone would, occasionally dropping the top-two margin below the 0.02 floor even though the file_name channel itself still favors the right answer — this is the margin-safety fix (D4) correctly trading a small amount of coverage for the guarantee that a genuinely close call never gets silently auto-routed. None of the 6 were wrong-but-confident; all landed safely in `NEEDS_REVIEW`.

## Verification performed

- `python -m pytest tests/ -q` → 205 passed (full suite, before and after every round of edits).
- `git diff --check` → clean, no whitespace errors.
- `git status --porcelain eval/local/` → empty both before and after creating the real-data files (directory is git-ignored, confirmed via `git check-ignore -v eval/local/real_ground_truth.json`).
- Real-filename leak check across every tracked file: grepped for every real filename fragment quoted in the original diagnostic report (excluding `.venv` and `eval/local/`) → zero matches after this archive itself was corrected to describe real files generically instead of quoting them (see note below).
- `python eval/run_phase8_ablation.py eval/synthetic_phase8_ablation_corpus.json --model-cache data/models/fastembed --verify-selection sort_pilot/classification/data/phase8_optional_evidence.json` → ran without error with the new `subject_filename_weight` field present.

**Self-correction:** an earlier draft of this document directly quoted several real filename fragments from the report (a math worksheet's filename, a regional education office's name, two textbook-series titles) while describing which cases were re-verified. That draft was never pushed, but it was staged locally, which is exactly the mistake the "never commit the filenames or labels" instruction exists to prevent. Caught by re-running the leak-check grep (with a broader pattern list than the first pass used) before committing, and rewritten above to describe every real case generically (subject/template pattern, filename token category) instead of quoting it.
