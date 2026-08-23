# Decision Record

## D1 — Rule out Gemma empirically before building anything new

**Decision:** Before proposing or implementing a new evidence channel, actually download the real Gemma 3 1B model (806 MB, SHA-256-verified against the pinned hash already in `local_tagger.py`), wire up a local `llama-server` (via Homebrew on this Mac, since the packaged runtime artifact is a Windows-only binary), and force the 12 real "partially resolved" files through the constrained fallback regardless of their calibrated route.

**Rationale:** The whole session's methodology has been "empirically verify, don't guess." Result: 0/12 correct — mostly the batch request failing to produce valid JSON under the 18-candidate subject enum's tight token budget, and in an isolated single-item test with a much smaller candidate list, one confident wrong answer ("정보" for a passage that opens "Dear Principal Jones..."). This is consistent with Gemma's own approved calibration target of only 50% held-out accuracy on escalated cases — it was never expected to be reliable here. This finding is what motivated proposing a deterministic alternative instead of tuning Gemma further.

## D2 — Language-detection channel: character-script ratio, not Kiwi tokenization behavior

**Decision:** Detect "predominantly non-Korean text" by counting Hangul syllable characters (U+AC00–U+D7A3) versus ASCII Latin letters directly in `evidence.natural_text`, requiring at least 30 combined letters before judging (`MIN_LANGUAGE_SIGNAL_LETTERS`) and a Latin ratio ≥ 0.6 (`LATIN_SCRIPT_RATIO_THRESHOLD`) before firing. When it fires, it scores exactly `영어` 1.0 and every other subject 0.0 — a positive-only signal, never used to penalize other subjects.

**Rationale:** The original framing considered using Kiwi's morphological-analysis output (already computed for the existing `lexical_terms` channel) as the "few Korean morphemes" signal, but Kiwi still tokenizes English words as unanalyzed/foreign tokens rather than returning nothing, making "token count" a noisier signal than directly measuring script composition. Direct character counting is simpler, fully deterministic, trivially testable, and doesn't depend on Kiwi's internal behavior on non-Korean input. The two thresholds (minimum letters, minimum ratio) exist specifically to avoid false positives on short fragments (e.g. a stray page number or a two-word English title) — both are hand-picked defaults, not yet calibrated against a large real corpus beyond the 12-case validation in `evidence.md`.

## D3 — PMI collocations: fractional match like template's existing channel, not exclusive-winner like the filename-alias channel

**Decision:** `E5SubjectClassifier._pmi_scores` scores each subject independently by the fraction of the evidence's extracted PMI collocations that overlap (bidirectional substring containment) with that subject's authored collocation list — mirroring `template.py`'s existing `_indicator_score` pattern, not the exclusive single-winner pattern used for the filename-alias channel.

**Rationale:** PMI collocations are enrichment evidence (a phrase overlapping a subject's typical vocabulary is suggestive, not identity-defining the way a literal subject name in a filename is), so multiple subjects can legitimately get partial credit for the same file — unlike the filename-alias case, where exactly one subject should ever be credited and crediting two would specifically reintroduce the 사회/통합사회 collision this session's earlier remediation fixed.

## D4 — Reused the existing PMI extraction pipeline and `pmi` toggle; authored 18 subject-specific collocation lists by hand

**Decision:** No new extraction code was needed — `classifier_engine/extract.py`'s existing PMI bigram/trigram extraction already flows through to `EducationalClassificationInput.pmi_collocations` (previously used only by the template axis). Reused the same `optional_evidence.pmi` boolean gate that already controls whether template receives this evidence, applying it identically to the new subject channel. Authored 3–5 plausible Korean noun-phrase collocations per catalog subject by hand (e.g. 과학 → "물질과 에너지", "화학 반응"; 수학 → "함수 그래프", "확률 통계"), plus a handful of English academic-content phrases for 영어 specifically (e.g. "reading comprehension", "topic sentence").

**Rationale:** Reusing the existing extraction and toggle avoids duplicating a pipeline that already works and already has its own resource-cost gate. The hand-authored collocation lists are a real content-authoring task with some inherent risk of imperfect match against actual Kiwi-tokenized bigrams (exact morpheme boundaries can't be guaranteed to match hand-typed phrases) — this is why the starting weight (0.05, matching the existing `subject_kiwi_lexical_weight`) was kept modest rather than assumed to be strong, and why real-data validation (not just the invented held-out corpus, which carries no PMI evidence at all) was the deciding check.

## D5 — Evidence-tuple insertion order preserves existing index-based test assertions

**Decision:** The two new `EvidenceContribution` entries (`pmi_collocation`, `language_signal`) were inserted between the existing `filename_alias` (index 2) and `kiwi_lexical` (now index 5, still last) entries, not appended at the very end.

**Rationale:** Existing tests from the earlier same-day remediation assert `decision.evidence[2].name == "filename_alias"` and `decision.evidence[-1].name == "kiwi_lexical"`. Preserving both of those required inserting the new channels in the middle rather than the end — the same lesson learned (and documented) during the filename-alias channel's own addition earlier this session.

## D6 — Starting weights kept modest, validated (not just assumed) against real data before finalizing

**Decision:** `subject_pmi_weight = 0.05` (same order as the existing Kiwi-lexical weight) and `subject_language_weight = 0.12` (close to, but slightly under, the filename-alias weight of 0.15, since it's a coarser signal than an exact literal filename match).

**Rationale:** Rather than asserting these values are correct, the actual real-data recalibration run (`evidence.md`) was used to check whether they produced a real, verified improvement — subject accuracy on the real ground-truth set went from 50/62 to 62/62 at these settings, with the packaged `calibrated_policy.json` thresholds staying reproducible from the committed invented-only corpus (unchanged, since the invented corpus contains no PMI collocations and no predominantly-English text to exercise either new channel). This is treated as sufficient initial validation, not as proof the weights are optimal — a larger, more diverse real corpus would be needed to tune them further.
