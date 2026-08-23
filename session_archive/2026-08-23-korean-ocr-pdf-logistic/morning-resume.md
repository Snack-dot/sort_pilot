# Morning resume checklist

## One-command path

Open PowerShell in the repository and run:

```powershell
cd "C:\Users\nobody haha\Downloads\sort_pilot-app"
powershell -ExecutionPolicy Bypass -File .\eval\resume_academic_training.ps1
```

The helper deliberately refuses to run on the wrong branch or a dirty worktree.

## What the helper does

1. Confirms `architecture-srs-implementation` is checked out.
2. Confirms the committed worktree is clean.
3. Selects the repository venv or the existing adjacent compatible venv.
4. Verifies the already-installed Korean OCR assets and hashes without downloading.
5. Runs focused OCR, PDF, TF-IDF, educational-service, logistic, HWP, and sandbox tests.
6. Starts `eval/train_academic_logistic.py` from all 319 human-approved sandbox labels.
7. Requires a final `academic-logistic-training-v2` report with at least 300 labels and both raw-text privacy flags false.

## If interrupted again

- Stop only the `eval/train_academic_logistic.py` Python parent and child processes.
- The trainer writes final artifacts atomically at the end, so the last complete model remains available.
- Re-run the same PowerShell helper; extraction and training restart from the beginning.

## Expected local-only prerequisites

- `~/Downloads/sandbox/training_labels.csv`
- the 319 sandbox training documents
- `~/Downloads/sandbox/.sort_pilot_state/models/rapidocr`
- `~/Downloads/sandbox/.sort_pilot_state/models/fastembed`

None of these local data/model files are committed or pushed.
