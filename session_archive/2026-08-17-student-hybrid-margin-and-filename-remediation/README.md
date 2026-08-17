# Student-Hybrid Classifier Remediation: Filename Evidence and Margin Safety

Date: 2026-08-17
Repository: `https://github.com/Snack-dot/sort_pilot.git`
Active branch: `architecture-srs-implementation`

## Purpose

This archive records a remediation of the freshly-merged Phase 0-8 student-hybrid classifier (`sort_pilot/classification/`), not a new phase. A real-data test (62, later expanded to 100, real Korean exam-prep filenames from the branch owner's own downloaded exam-prep folder) found the classifier auto-routed only 16.1% of files and, worse, silently auto-routed at least 7 files to a wrong template without ever reaching review. The branch owner relayed a detailed diagnostic report and asked for the fix to be implemented directly, on the explicit condition that this stays a remediation (not a "Phase 9") and that no real filenames or labels from personal files are ever committed.

## Contents

- `conversation.md` — chronological reconstruction of the diagnostic report, the planning process, and the implementation.
- `decisions.md` — decision record for each of the two root-cause fixes and the supporting changes.
- `evidence.md` — code-verified root-cause evidence, before/after numbers, and the real-data validation results.
- `implementation-outcome.md` — delivered changes, verification performed, and final state.

## Two root causes, both verified against the actual source before any fix was written

1. **The subject axis had no filename evidence channel at all** — only the template axis did. Literal filename tokens like `국어`/`영어`/`한국사`/`사회`/`과학` frequently failed to resolve while `수학` (whose E5 embedding happened to score well without help) mostly worked, exactly as the report observed.
2. **The calibration procedure that fits accept/margin/fallback thresholds structurally preferred the smallest workable margin.** Even after fixing the tie-break direction, the deeper issue was that maximizing held-out coverage could still force an unsafe near-zero margin when it captured one extra borderline case — so a hard minimum-margin floor was needed, not just a tie-break sign flip.

## Real-data validation, not just invented test cases

After the fix, the branch owner made the exact folder of real files behind the original report available locally (never committed). Ground-truth labels for 50 subject and 57 template cases — built conservatively from literal filename evidence plus a few subject labels the branch owner's own report had already confirmed — were used to validate the fix directly against the real data that motivated it: **50/50 subject and 57/57 template predictions came back correct**, and the already-recalibrated thresholds (fit only against invented data) turned out to generalize to the real data without needing further adjustment. Across all 100 real files, the confident-auto-route rate rose from the originally reported 16.1% to 46.0%, using filename evidence alone with no body text at all.

## Current state at archival time

- All code, data, and test changes are committed locally; nothing has been pushed without separate authorization.
- The real file folder and its ground-truth labels live only under the git-ignored `eval/local/` directory, exactly as the diagnostic report itself specified ("never commit the filenames or labels"). They are not part of this archive or any commit.

## Provenance limitation

This is a good-faith reconstruction from the visible conversation, tool outputs, and verifiable local Git/repository state. No real personal filenames or file contents are reproduced anywhere in this archive — only aggregate counts and the specific filename patterns/tokens the fix targets (e.g. "문제지", "수능특강"), which are generic exam-material vocabulary, not identifying information.
