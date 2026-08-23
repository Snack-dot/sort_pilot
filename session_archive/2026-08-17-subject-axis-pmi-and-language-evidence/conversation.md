# Reconstructed Conversation and Prompt Log

## 1. The gap surfaced by the previous remediation's own real-pipeline test

Immediately after the same-day filename-evidence-and-margin-safety remediation, the branch owner asked to see the real breakdown behind the 41% coverage figure. That breakdown showed 17 real files where the template axis resolved locally but the subject axis did not ("partially resolved"), and manual inspection of their extracted text showed 12 of them were genuinely English-language exam content with no literal "영어" filename token — the same pattern the branch owner's original diagnostic report had separately flagged as "probable English misses."

### User prompt

> Partially resolved is a problem. I need that fixed. 14 that is unable to be parsed is okay (that doesn't count). If you fix the partially resolved and add the gemma, then it should be perfect (discounting unsupported files). 4 remainder is okay (that's enough for human input.)

## 2. Testing Gemma before trusting it

Rather than assume "add Gemma" would close the gap, the actual Gemma 3 1B model was downloaded, verified, and wired to a local runtime, then forced through all 12 real cases regardless of calibrated routing.

### Result reported back

0/12 correct — mostly declining under the real 18-candidate subject enum's token budget, and confidently wrong in an isolated smaller-candidate test. This was reported honestly rather than proceeding as if Gemma had solved the problem.

### User prompt (mid-explanation, before a proposed follow-up question was answered)

> What's the difference between this architectural change and the previous one? Specifically, the NLP based ideas. The previous one had a coverage of 88% and was... more or less accurate. This one is 41% using only the classifier. Can you tell me specifically what has been changed?

A detailed architectural comparison was given: different test corpus, closed dual-axis fixed-taxonomy classification with an explicit 90%-precision floor versus the old open-vocabulary single-axis clustering, and the mechanical effect of requiring two independently-gated conditions to both clear a strict bar.

### User prompt

> Do you think some of the previous NLP methods could be used to improve this?

Recommended, in 2-3 sentences per the exploratory-question norm: a cheap script-based language-detection signal (reusing the fact that Kiwi/extraction already runs on every file) as the most promising lever, PMI collocation extraction as a secondary lever (already exists for the template axis, never extended to subject), and explicitly not reviving the old fastText semantic-rescue layer since E5 already covers that role.

### User prompt

> Yes, implement the language-detection channel. Try the PMI collocation too.

## 3. Implementation

Both channels were added to the subject axis in the same pattern established by the filename-alias channel earlier the same day: a new `SubjectEvidence.pmi_collocations` field (reusing the extraction pipeline and `optional_evidence.pmi` toggle already wired for the template axis), a `SubjectProfile.pmi_collocations` field with 18 hand-authored per-subject collocation lists, `E5SubjectClassifier._pmi_scores` (fractional match, mirroring the template axis's existing pattern) and `E5SubjectClassifier._language_scores` (Hangul-vs-Latin character-ratio detector, positive-only signal for 영어), both wired through `Phase8OptionalEvidence` (bumped to v3) and every calibration/ablation script that had needed the same fix for the filename-alias channel earlier that day.

## 4. Validation

Real-data validation (the same 100-file folder and expanded ground truth, kept strictly local under `eval/local/`) showed subject accuracy rising from 50/62 to 62/62, and overall real-file coverage rising from 41% to 49% — with the template axis and the 20 no-extracted-text files unaffected, exactly as expected since this change only targeted the subject axis's content-based evidence.

## 5. This archive

Created following the same `session_archive/` convention as the earlier same-day remediation, kept as a separate entry since this is a genuinely new capability addition built at the branch owner's explicit request, not a bug fix.
