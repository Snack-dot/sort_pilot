# Subject-Axis PMI Collocation and Language-Detection Evidence

Date: 2026-08-17
Repository: `https://github.com/Snack-dot/sort_pilot.git`
Active branch: `architecture-srs-implementation`

## Purpose

This archive records a follow-up enhancement to the subject-axis classifier, built directly on top of the same-day filename-evidence-and-margin-safety remediation (`session_archive/2026-08-17-student-hybrid-margin-and-filename-remediation/`). After that remediation shipped, a full real-pipeline validation against 100 real files (`~/Downloads/2027 수능특강 독서`) found the fix left one specific gap unaddressed: 17 files where template correctly resolved locally but subject did not ("partially resolved"), 12 of which were real English-language exam content with no literal "영어" token anywhere in the filename.

The branch owner asked whether the project's original lightweight-NLP philosophy (predating the Phase 0-8 hybrid rewrite) could help close this gap, specifically requesting a script-based language-detection channel and PMI collocation extraction for the subject axis — mirroring capabilities the template axis and the retired general-purpose classifier engine already had, but the subject axis never did.

## What was tried and ruled out first

Before building this, the actual local Gemma fallback was downloaded, verified (SHA-256 against the pinned hash), and run against the same 12 real files with their true label forced through as a request regardless of calibrated routing. Result: 0/12 correct — mostly declining (batch JSON generation failing under the 18-candidate subject enum's token budget) and, in an isolated single-item test with a much smaller candidate list, one confident wrong answer. This ruled out "just turn on Gemma" as a fix for this specific gap and motivated the deterministic approach recorded here instead.

## Contents

- `conversation.md` — chronological reconstruction of the request and the Gemma capability test that preceded it.
- `decisions.md` — design decisions for both new evidence channels.
- `evidence.md` — before/after numbers from real-data validation.
- `implementation-outcome.md` — delivered changes and verification performed.

## Result

Subject-axis accuracy against the real, ground-truth-labeled subset rose from 50/62 to **62/62** using real extracted text; the specific "partially resolved" pattern the branch owner flagged as a problem is resolved for the subject axis. Overall real-file coverage (both axes resolved) rose from 41% to 49%. The remaining gap is now entirely on the template axis and among files with no extractable text at all (unsupported formats), neither of which this change targeted.

## Current state at archival time

All code, data, and test changes are committed locally; nothing has been pushed without separate authorization. The real Gemma model download, the real file folder, and its ground-truth labels remain strictly under the git-ignored `eval/local/` directory and are not part of this archive or any commit.

## Provenance limitation

This is a good-faith reconstruction from the visible conversation, tool outputs, and verifiable local Git/repository state. No real personal filenames or file contents are reproduced anywhere in this archive.
