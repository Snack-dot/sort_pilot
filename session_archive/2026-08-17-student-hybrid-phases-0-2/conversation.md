# Reconstructed Conversation and Work Log

## 1. Resume from the checkpoint

The user asked to continue the Sort Pilot student hybrid classifier from the latest checkpoint, read the newest session archive and the authoritative plan first, inspect Git status and recent commits, and resume from the first unfinished phase. The fixed templates were reaffirmed as `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.

The repository was on `architecture-srs-implementation`, two commits ahead of its remote. The latest checkpoint commits were `c9706d3` and `66f1a84`. A pre-existing untracked duplicate curriculum prompt was present and was not treated as implementation authority.

## 2. Vocabulary and plan-compliance correction

The user objected to introduced terminology that was not part of the plan, especially using “schema” in place of “template” and using “fixture” for the evaluation corpus. The user required exact plan vocabulary and instructed the assistant to stop and ask whenever the plan did not determine an implementation choice.

The user then requested exact explanations of subject, template, combined-path accuracy, corpus cases, and the two independent classification axes. The governing vocabulary was fixed as subject, template, combined-path accuracy, corpus, and Needs Review state.

## 3. Explicit recovery order

The user supplied the mandatory recovery sequence:

1. Complete Phase 0 with exactly subject and template axes, no `document_type`, full result validation, catalog-bounded subjects, five fixed templates, unresolved move blocking, and strict field rejection.
2. Complete Phase 1 by requiring the saved student profile before each relevant classification or organization flow and limiting onboarding to occupation, student type, grade, semester, and catalog version.
3. Rebuild Phase 2 with the exact plan measures, unresolved results counted as incorrect, strict loading, a runner, tests, and documentation, with folder usefulness removed.
4. Do not begin Phase 3 or later.
5. Verify focused tests, the full suite, documentation, whitespace, and Git state.

## 4. Phase 0 recovery

The classification representation was rebuilt around exactly two axes. Candidate scores, evidence contributions, raw score, calibrated confidence, margin, ranked candidates, decision source, model/profile/policy versions, and review state were validated. Subject decisions were bounded to the selected student type's catalog. Template decisions were bounded to the five fixed templates. Unresolved results could not render a destination or construct an `OrganizationPlan`. Catalog and profile loaders rejected missing or additional fields.

## 5. Phase 1 recovery

The persisted student profile was enforced before startup continuation, calibration, migration, candidate collection, analysis start, and preview. Onboarding remained limited to the five approved profile values. Focused tests verified that each relevant path stopped when no saved profile existed.

## 6. Phase 2 format correction

An early unfinished evaluation format introduced cryptic case IDs, repeated `KR_STUDENT_2026_MVP_V1` fields, and per-item anonymization flags. The user rejected these additions. The assistant acknowledged that the ID was invented, that the catalog identifier is a profile/catalog reference rather than a case ID, and that a local synthetic corpus did not need an anonymization flag.

The user amended Phase 2 from a labeled anonymized corpus to a labeled synthetic corpus. The user further required that any evaluation using real labels must not be tracked or uploaded to GitHub. The final implementation therefore uses only made-up tracked cases and labels, has no case IDs, joins ordered predictions by list position, writes no runner output, and reserves Git-ignored `eval/local/` for every real filename, text, label, prediction, correction, or result.

## 7. Phase 2 measures

The evaluation framework tracks subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory. Unresolved subject or template results count as incorrect for their respective accuracy; an unresolved axis also makes combined-path accuracy incorrect. Folder usefulness is absent.

## 8. Plan hierarchy

The user requested that old educational Markdown plans be treated as references and that the hybrid plan be supreme. The loose root curriculum prompt was confirmed byte-for-byte identical to its preserved copy under `plans/superseded/`, then the redundant root copy was removed. `plans/README.md` now establishes this order:

1. the user-controlled `HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` as supreme;
2. the user-supplied explicit curriculum document as the highest-ranked reference only;
3. the preliminary hybrid prompt;
4. the exploratory ADR.

Each superseded file carries an explicit reference-only warning.

## 9. Documentation relocation and architecture assessment

The user asked whether the root architecture document was outdated and whether the SRS and third-party inventory belonged under `docs/`. A complete 721-line read confirmed that the architecture described a watcher, a second UI process, one worker, automatic moves, old storage, old repository paths, and a real-label corpus workflow that do not describe the implemented app or supreme plan.

`ARCHITECTURE.md`, `SRS.md`, and `THIRD_PARTY.md` were moved into `docs/`. Active references were updated. The architecture and SRS are explicitly historical and cannot override the supreme plan.

## 10. Documentation and verification request

The user required that decisions, session history, phase completion, and other necessary documentation be written as each phase finishes. This archive follows the repository's established session format and adds a dedicated phase-completion record. No Phase 3 work was started.

## 11. Permanent agent rules

The user requested permanent repository-agent rules stating that the hybrid architecture plan is the main plan, superseded documents remain references, and every session must be recorded in the sessions folder. `docs/AGENTS.md` now names the exact supreme-plan path, reference-only directory, and existing `session_archive/` directory.
