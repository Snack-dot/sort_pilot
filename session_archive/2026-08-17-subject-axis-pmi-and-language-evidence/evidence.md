# Evidence

## Gemma capability test (real, before building anything new)

Real model: `gemma-3-1b-it-Q4_K_M.gguf`, downloaded from the pinned Hugging Face URL already in `local_tagger.py`, verified byte-for-byte (806,058,240 bytes, SHA-256 `8ccc5cd1f1b3602548715ae25a66ed73fd5dc68a210412eea643eb20eb75a135` — exact match to the pinned constant). Run via a local `llama-server` (Homebrew build on this Mac, symlinked into the installer's expected runtime path since the packaged runtime artifact is a Windows-only binary; the subprocess invocation code in `gemma_fallback.py` is otherwise unmodified and platform-agnostic).

All 12 real "partially resolved" subject cases (English content, no literal filename token) forced through `ConstrainedGemmaFallback.resolve_many` regardless of their real calibrated route:

```
Gemma correct: 0/12
```

10 of 12 returned no selection at all (batch JSON generation failed to complete under the token budget for an 18-candidate subject enum); the 2 that did return a selection were both wrong. A separate, manual single-item request with a much smaller 3-candidate list and a clearly English passage ("Dear Principal Jones, I hope this letter finds you well...") returned a confident, well-formed, but wrong answer: `정보` (Information/Computer Science). This confirms the failure is a real model-capability limit, not a batching/token-budget artifact alone.

## Real-data validation of the two new channels

Ground truth: the existing 50-entry real subject label set was extended with 12 more entries — files whose extracted body text is unambiguously English (verified by reading the actual extracted text, e.g. literal "Dear Principal Jones," "Dear Dog Owners," or the standard CSAT-English stem "다음 글의 주제로 가장 적절한 것은?") but which carry no literal "영어" filename token, matching exactly the pattern the branch owner's original diagnostic report separately flagged as "probable English misses." Total real subject ground truth: 62 entries (up from 50).

Running the classifier with real extracted text (not the earlier deliberately-conservative filename-only test) against this expanded ground truth:

```
SUBJECT: 62/62 correct   (previously 50/62 with the same real ground truth, before this change)
TEMPLATE: 57/57 correct  (unchanged — this change only touched the subject axis)
```

Recalibrating against the real 62/57 cases combined with the invented 68-case corpus:

```
subject:  same thresholds as before (high_score=0.8616..., high_margin=0.0378...)
          accepted=88/130, accepted_correct=87 (98.86% precision, up from 96.15%)
template: high_margin shifts slightly (0.1357 vs 0.1410) but the packaged, committed
          calibrated_policy.json was kept at the invented-only-reproducible value
          (0.1410) since that's what `eval/run_policy_calibration.py --verify-policy`
          must be able to reproduce without any real personal data.
```

Both `eval/run_policy_calibration.py --verify-policy` and `eval/run_personal_example_calibration.py --verify-policy` still pass against the packaged, committed JSON files using only the invented corpus — the new channels are wired into calibration but don't change the invented-only outcome (the invented corpus contains no PMI collocations and no predominantly-English text, so neither new channel fires on it).

## Full real-pipeline coverage, before and after

Using the actual production `EducationalClassificationService` (real text extraction, Gemma installed and ready but declining/failing as measured above) against all 100 real files:

```
                                  before this change   after this change
both axes resolved                41/100 (41.0%)        49/100 (49.0%)
subject sent to review            46/100                28/100
template sent to review           45/100                45/100 (unchanged)
subject accuracy (62 labeled)     50/62                 62/62
template accuracy (57 labeled)    51/57                 51/57 (unchanged)
```

The remaining 6 template misses are unrelated to this change (template axis wasn't touched) and remain safely routed to `NEEDS_REVIEW`, none wrong-but-confident. The remaining 28 subject-review files are now overwhelmingly concentrated in the 20 files with no extracted text at all (unsupported formats: `.hwp`, `.egg`, `.sdocx`, plus a few PDF extraction failures) rather than the "extractable but unresolved" pattern this change specifically targeted.

## Verification performed

- `python -m pytest tests/ -q` → 217 passed (up from 207; 10 new tests for the two channels), run after each round of edits.
- `git diff --check` → clean.
- `git status --porcelain eval/local/` → empty (git-ignored, confirmed).
- Real-filename leak check across every tracked file → zero matches.
