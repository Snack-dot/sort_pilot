# Decision Record

## D1 — Supreme plan

`plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is the sole normative educational implementation plan. Direct user amendments are recorded there before implementation. Superseded plans are references only.

## D2 — Exact vocabulary

Use subject, template, combined-path accuracy, corpus, and Needs Review. Do not substitute unrelated terminology or introduce additional classification concepts.

## D3 — Exactly two axes

Educational classification has exactly two independent axes: subject and template. There is no `document_type` axis.

## D4 — Bounded destinations

Subjects must be exact entries in the selected student type's subject catalog. Templates must be exactly `학습자료`, `과제`, `교내활동`, `교외활동`, or `증빙서류`. An unresolved axis blocks folder rendering and move-plan construction.

## D5 — Strict persisted inputs

Catalog and student-profile documents reject missing or additional fields. The profile stores only occupation, student type, grade, semester, and the catalog reference.

## D6 — Profile gate

Every relevant classification and organization flow requires a saved valid student profile, not only application startup.

## D7 — Synthetic tracked corpus

The repository tracks only a labeled synthetic corpus made from invented filenames and text. It does not use invented case IDs, per-item anonymization flags, or repeated catalog metadata.

## D8 — Real-label security boundary

Every evaluation involving real filenames, extracted text, labels, predictions, corrections, or results stays under Git-ignored `eval/local/`. It must never be committed, force-added, or uploaded to GitHub. The runner prints aggregate measures and writes no results.

## D9 — Required Phase 2 measures

Track subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory. Unresolved results are incorrect in each applicable accuracy measure. Folder usefulness is not part of Phase 2.

## D10 — Ordered evaluation inputs

Corpus cases and predictions are strict ordered JSON lists. List position connects a prediction with a synthetic corpus case, avoiding cryptic join identifiers.

## D11 — Documentation placement

Educational plan authority is documented under `plans/`. Historical architecture, SRS, and third-party inventory belong under `docs/`. Session evidence belongs under `session_archive/`.

## D12 — Phase boundary

Do not begin Phase 3 or later until Phases 0–2 conform to the supreme plan and all required verification completes.

## D13 — Collaboration boundary

Work uses only this user, this workspace, and repository evidence. No sub-agent or another person's workspace is used for implementation or reconstruction.

## D14 — Permanent repository-agent rules

`docs/AGENTS.md` permanently requires reading and following the supreme hybrid plan, keeping superseded documents reference-only, and recording every work session under `session_archive/`.
