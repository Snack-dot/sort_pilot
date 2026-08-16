# Recall/Precision Fix Session and Real-World Validation Archive

Date span: 2026-08-14 through 2026-08-16
Repository: `https://github.com/Snack-dot/sort_pilot.git`
Working directory: `~/Documents/sort_pilot` (macOS)
Active branch: `architecture-srs-implementation`

## Purpose

This archive records an independently-run investigation and fix session, requested by the branch's original author acting as a reviewer rather than the implementing team: the classifier had been calibrated on 3 sample folders but produced zero real sorts across a 500-file test. The goal was to find the actual, empirically-verified root causes (not speculation), fix them, and hand the result back to the implementing team for their own final review before anything was pushed.

It also records what came after the fixes landed: an honest distribution check (would a fresh clone actually work for someone who isn't this machine), the resulting model-artifact handling work, the explicit push, and — at the reviewer's own request — a full real-world run of the fixed pipeline against a real, personal Downloads folder, followed by a full reversal of that run.

## Contents

- `conversation.md` — chronological reconstruction of user prompts and assistant actions/responses, using verbatim prompts where they were available in context.
- `decisions.md` — decision record with rationale for each fix and each non-obvious operational choice.
- `evidence.md` — repository, runtime, and empirical evidence gathered during diagnosis and validation.
- `implementation-outcome.md` — delivered changes, commit list, and final verification results, including the real-world run and its reversal.

## Current state at archival time

- 11 commits landed on `architecture-srs-implementation` from this session (`ddfe04c` through `5c8c5e8`, listed in `implementation-outcome.md`) and were pushed to `origin` after explicit, singular authorization ("PUSH").
- The real Downloads folder used for validation is back to its original layout; the validation run itself was fully undone at the folder owner's request and is not part of any committed change.
- No file from that personal Downloads folder was committed, uploaded, or otherwise left the local machine; only aggregate counts and folder-name statistics from the run are recorded in this archive and in `CHANGELOG.md`.

## Provenance limitation

This is a good-faith reconstruction from the visible conversation, tool outputs, and verifiable local Git/repository state at archival time. It does not claim access to hidden model reasoning, deleted messages, or system data outside what was directly observed during the session.
