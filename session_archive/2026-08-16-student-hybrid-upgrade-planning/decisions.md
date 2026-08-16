# Final Decision Record

## D1 — Implementation base

Use `architecture-srs-implementation` as the base because the goal is to upgrade its existing statistical classifier, not rebuild that architecture after its deletion on `fix`.

## D2 — Product identity

The only occupation is `학생`. User types are `중학생` and `고등학생`; institution labels are out of scope.

## D3 — Fixed hierarchy

Use `학생/{student type}/{grade}/{semester}/{subject}/{template}` and preserve the original filename. Only grades 1–3 and semesters 1–2 are valid.

## D4 — Five templates

The exact templates are `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`. `학습자료` replaces `학업`. Review is state, never a sixth folder.

## D5 — Subject catalog

Use one curated, static `KR_STUDENT_2026_MVP_V1` JSON catalog informed by familiar Korean student subjects. It is a sorting constraint, not a legal curriculum, institution, timetable, or revision-transition model. No special subjects or artificial fallback subjects are permitted.

## D6 — Independent axes

Classify subject and template independently. Each retains candidates, scores, margin, evidence, provenance, and review state.

## D7 — Hybrid authority

High-confidence local decisions are authoritative. Plausible ambiguity may reach Gemma with a closed candidate set. Insufficient evidence and invalid/unresolved Gemma output go to user review.

## D8 — Unresolved results

An unresolved result has nullable axes and cannot render a normal destination or create an approved move plan. The user must choose valid values in preview.

## D9 — Personalization

Store corrections as separate local nearest-neighbor examples. Do not fine-tune models or mutate global profiles from a single correction.

## D10 — Safety boundary

Keep classification independent of scanning safety, preview, immutable approved plans, transactional moves, rollback, history, and Undo.

## D11 — Experimental components

E5 and lexical evidence form the initial lightweight classifier. OCR layout, PMI, YOLO/LVIS, and low-memory scheduling must earn inclusion through evaluation and ablation.

## D12 — Superseded material

The two user-supplied preliminary prompts and the exploratory ADR are preserved under `plans/superseded/`. They are historical context only; `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is authoritative.
