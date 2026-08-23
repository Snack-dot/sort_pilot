# ADR-001: Curriculum-constrained educational hybrid classification

> **Status:** Superseded exploratory reference only. `../HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme and overrides every conflict.

## Status

Accepted for implementation foundation on 2026-08-16.

## Context

Sort Pilot has alternated between a statistical-first classifier with user-owned topic profiles and a simpler Gemma-first classifier. The new MVP narrows the product to Korean middle and high school students and needs an explicit authority policy before either implementation is extended.

## Decision

The primary authority is a curriculum-constrained local classifier. It resolves subject and activity as independent axes using inspectable local evidence. High-confidence local decisions cannot be overridden by Gemma. Medium-confidence axes may be sent independently to Gemma with a closed candidate list. Low-confidence or unresolved axes require user review.

The initial rendered hierarchy is:

```text
학생/<중학생|고등학생>/<1|2|3>학년/<1학기|2학기|공통|미확인>/<과목|비교과|공통|과목미확인>/<학업|과제|교내활동|교외활동|증빙서류|분류미확인>
```

Classification state remains richer than the folder path. Document type, evidence, scores, margins, provenance, model/profile versions, and review state remain internal fields. An approved organization plan must eventually freeze the exact source and destination paths before execution.

## Consequences

- The existing local classifier architecture remains the implementation base.
- Gemma becomes a constrained per-axis fallback rather than a universal classifier or folder-name generator.
- Curriculum, subject, activity, document type, and personal examples require distinct versioned contracts.
- Raw similarity scores are not described as probabilities until calibrated on held-out labeled data.
- `비교과`, `공통`, and explicit unknown values prevent the curriculum constraint from forcing unsupported subjects.
- Existing safe extraction, preview, transactional movement, rollback, and Undo remain independent from classifier authority.

## Deferred decisions

- Authoritative curriculum data and elective customization
- Embedding model and subject-profile construction
- Score calibration and fallback thresholds
- Final internal document-type taxonomy
- Measured inclusion of OCR-layout, PMI, and YOLO evidence
