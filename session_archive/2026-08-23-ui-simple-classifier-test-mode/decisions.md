# Decision Record

## D1 — Gate the shortcut behind an explicit environment variable

The simple classifier is enabled only by `SORT_PILOT_SIMPLE_CLASSIFIER=1` (or another recognized true value). Normal launches retain the full educational classifier.

## D2 — Keep labels inside existing contracts

The shortcut selects only the current student's allowed subjects and the existing five templates. Documents map to the first subject and `학습자료`, images to the second subject and `교내활동`, and archives to the third subject and `과제`. Unknown extensions remain unresolved.

## D3 — Make the mode non-mutating without demo-only UI copy

The preview uses the same product-facing labels as the real application, while accepting the standalone/demo flow does not execute organization plans, write history, move files, or store correction examples.

## D4 — Provide a standalone UI entry point

`ui_demo.py` is separate from `main.py` and `AppController`. It uses only generated fake paths, so UI work cannot accidentally start the real scan/classification pipeline even if an environment variable or VS Code interpreter selection is wrong.
