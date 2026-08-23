# Reconstructed Conversation and Work Log

## 1. Repository update and initial explanation

The user asked to update the repository from Git and explain the codebase. The clean `fix` branch was fast-forwarded from `d43051d` to `5c98de4`. The update removed roughly 5,000 lines of the prior Tier-1, Naive Bayes, calibration, semantic-vector, topic-profile, and review architecture, leaving extraction followed by role-aware local Gemma classification, preview, safe moves, and Undo. The `fix` suite reported 39 passed and 2 skipped.

## 2. Locating the AI-only transition

Git history established that commit `34e769a` changed the active app from topic-profile assignment to `LlmFileClassifier.classify()`. Commit `5c98de4` later deleted the inactive classifier stacks. The distinction was recorded as behavioral switch versus cleanup.

## 3. Return to the architecture branch

At the user's request, the checkout switched to `architecture-srs-implementation` and fast-forwarded from `0a53266` to `6bc5466`. Comparison showed that this branch was the ancestor of `fix`, while `fix` had 19 later commits. The architecture branch preserved statistical classification, calibration, profiles, semantic rescue, and optional Gemma naming.

## 4. New recall/precision archive

Two documentation commits were pulled: `5c8c5e8` and `e168964`. Their archive documented empirically verified improvements from zero effective real sorting to approximately 88.7% content-bearing coverage, complete-linkage repair, model distribution, 734 successful moves, and complete Undo. It also documented that coverage was not labeled accuracy and exposed plan/execution instability and Qt application-name-dependent history paths.

## 5. Proposed hybrid student architecture

The user supplied a broad middle/high-school hybrid plan combining curriculum constraints, E5, Korean lexical evidence, OCR structure, optional YOLO, correction retrieval, and constrained Gemma fallback. Analysis agreed with the narrowed domain and explicit authority policy but warned against implementing all optional evidence before labels, evaluation, and confidence calibration.

## 6. Choice of implementation base

The user clarified that the existing full classifier architecture should remain the base, augmented with the proposed upgrades, narrowed scope, and Gemma fallback. The desired hierarchy was established around student type, grade, semester, subject, and activity/template. The assistant corrected its earlier recommendation to start from `fix` and agreed to evolve `architecture-srs-implementation`, selectively porting operational Gemma improvements from `fix`.

## 7. Initial foundation implementation

The user said to start. The assistant added curriculum, classification-result, subject-interface, persistence, and policy modules plus tests and an ADR. The work established atomic JSON onboarding state, independent subject/activity decisions, raw score and margin, provenance, curriculum candidate filtering, and per-axis routing. Focused tests reached 14 passing. The active classifier and UI were not changed.

## 8. Simplification documents and compliance audit

The user added two Markdown specifications. The assistant read them and initially interpreted the explicit curriculum references as normative legal/revision requirements. It correctly found that exploratory code included extra semesters, special fallback subjects, and a sixth review template, but incorrectly recommended institution labels and year-by-year curriculum revision logic.

## 9. User correction and final scope

The user clarified:

- Use `중학생` and `고등학생`, because the occupation is student; do not model institutions.
- Use one 2026 MVP reference set; no year-by-year curriculum engine.
- Do not split official and active subjects.
- Do not allow special subjects.
- Use only five fixed templates.
- Curriculum material is a practical sorting reference, not a legal-compliance core.

The assistant acknowledged overinterpreting the reference and produced a simplified final plan.

## 10. Final naming correction and documentation request

The user approved the simplified plan and changed the first template from `학업` to `학습자료` to distinguish it from `과제`. The user requested one saved authoritative plan, preservation of superseded documents in a separate plans area, a complete session archive, and explicit remediation of every earlier implementation mistake. Those deliverables were then created.

## 11. Checkpoint and handoff request

The user requested completion of all pending plan/session documentation, a test and Git-status audit, a clearly named checkpoint commit, and recording of the branch and exact checkpoint hash in this archive. The user explicitly prohibited pushing without a separate request. The checkpoint and its archival metadata are recorded in `implementation-outcome.md`.
