# Korean OCR, bounded PDF extraction, and academic logistic training

Date: 2026-08-23
Repository: `https://github.com/Snack-dot/sort_pilot.git`
Branch: `architecture-srs-implementation`

## Result

This session added verified local `korean_PP-OCRv5_mobile_rec` support to the existing RapidOCR structure, bounded PDF extraction, image/EXIF coverage, extraction-quality review gating, privacy-preserving word/character TF-IDF, PDF numeric features, HWP/HWPX extraction, and the sandbox-only academic logistic training pipeline.

The v2 training run was intentionally stopped before shutdown. No partial v2 model was saved; the last complete local report remains `academic-logistic-training-v1` with 319 labels.

## Morning restart

From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\eval\resume_academic_training.ps1
```

The script verifies the branch and clean worktree, verifies already-installed OCR assets without networking, runs focused tests, retrains from all 319 human-approved labels, and verifies the v2 privacy/report contract.

## Contents

- `conversation.md` — user requirements and scope changes.
- `decisions.md` — implementation and privacy decisions.
- `evidence.md` — tests and real-data aggregate validation.
- `implementation-outcome.md` — delivered behavior and remaining limitations.
- `morning-resume.md` — detailed recovery checklist.
