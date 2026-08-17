# Conversation Reconstruction

Date: 2026-08-17 (Asia/Seoul)

## Resumption

The user instructed the assistant to continue after Phase 3. Existing governing instructions required exact adherence to `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`, exact plan vocabulary, reference-only treatment of superseded documents, and a session record under `session_archive/`.

Before editing, the assistant read `docs/AGENTS.md`, `README.md`, the supreme plan, the newest Phase 3 archive, Git status, and the latest commits. The branch was `architecture-srs-implementation`, ahead of its remote by two commits, with the existing uncommitted Phase 0–3 work preserved. The latest commits remained `66f1a84` and `c9706d3`.

## Phase selection

The newest archive identified Phase 4 as the first unfinished phase. The controlling plan text required separate profiles and evidence weights for exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.

The assistant inspected the existing two-axis result representation, fixed `Template` values, Phase 3 E5 encoder, policy boundary, synthetic corpus, tests, package-data rules, and callable documentation. No Phase 4 implementation existed.

## Implementation

The plan names semantic intent, filename and lexical indicators, PMI collocations, OCR/layout evidence, optional visual evidence, and personal examples as available template evidence. The new template evidence representation keeps these sources separate. Only natural filename/body text is passed to E5; engineered values are never turned into a sentence.

The plan does not provide numerical tuning values, and Phase 5 owns held-out calibration. The assistant therefore recorded each source with a neutral `1.0` weight in each separate template profile. These are transparent starting weights, not calibrated values or confidence.

The classifier uses the existing local 384-dimensional multilingual E5 encoder, validates exactly five complete profiles, caches average prototype vectors, ranks all five templates, and retains raw score, top-two margin, every weighted contribution, and model/profile/policy versions. It does not add acceptance, fallback, or abstention thresholds.

## Made-up examples and profile review

The real cached E5 model was exercised against the ten tracked made-up corpus cases using natural filename/body text. The first run selected nine expected templates and exposed an ambiguous outside-school music-event description. The `교외활동` natural profile was clarified with a school-outside venue example. The next run selected all ten expected templates.

That ten-item result checks mechanics and profile wording only. It is not held-out calibration, a production-accuracy claim, or evidence from real local files.

## Verification and stopping point

Focused Phase 4 tests, the combined Phase 0–4 contract tests, and documentation checks passed. Complete-suite and repository checks are recorded in `evidence.md`. Phase 5 was not started. No commit or push was performed.
