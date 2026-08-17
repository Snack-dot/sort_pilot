# Student Hybrid Phase 8 Session Archive

Date: 2026-08-17 (Asia/Seoul)

Repository: `https://github.com/Snack-dot/sort_pilot.git`

Active branch: `architecture-srs-implementation`

## Purpose

This archive records Phase 8 optional evidence and low-end optimization under `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`.

## Outcome

Phase 8 retains layout-aware OCR, a separate subject Kiwi lexical contribution with weight `0.05`, and PMI. It rejects YOLO/LVIS visual evidence and new model-session scheduling from the active educational flow. The exact two axes remain subject and template, and the five templates remain exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.

The frozen development selection passed on a separate made-up held-out corpus. Subject accuracy improved from `6.67%` to `46.67%`, template accuracy from `43.33%` to `100%`, and combined-path accuracy from `3.33%` to `46.67%`. All three exact paired probabilities were below `0.001`.

## Contents

- `conversation.md` — good-faith reconstruction of the user instructions and this Phase 8 session.
- `decisions.md` — Phase 8 gates, retained evidence, rejected evidence, and boundaries.
- `phase-completion.md` — Phase 8 completion state.
- `evidence.md` — evaluation, resource, test, dependency, documentation, privacy, and repository evidence.
- `implementation-outcome.md` — delivered files and active behavior.

## Authority

`plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme. Documents under `plans/superseded/` and the legacy architecture/SRS remain references only.
