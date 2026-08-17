# Student evaluation

Phase 2 evaluates the two independent classification axes: subject and template. The tracked files in this directory use only made-up examples.

## Tracked synthetic corpus

`synthetic_student_corpus.json` contains an ordered `cases` list. Every case has only:

```text
file_name
text
student_type
grade
semester
subject
template
```

The file names and text are invented. `subject` must be an exact entry in the selected student type's subject catalog, and `template` must be exactly one of `학습자료`, `과제`, `교내활동`, `교외활동`, or `증빙서류`.

`synthetic_student_predictions.json` contains predictions in the same order. List order connects a prediction to a corpus case; there are no invented case IDs.

Run the aggregate evaluation from the repository root:

```powershell
python eval/run_student_evaluation.py eval/synthetic_student_corpus.json eval/synthetic_student_predictions.json
```

The runner writes nothing. It prints subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory. An unresolved subject or template is incorrect for its accuracy measure, and any unresolved axis makes combined-path accuracy incorrect.

## Real labels stay local

Do not place an evaluation made from real files in any tracked synthetic JSON file. Put every real filename, extracted text, label, prediction, correction, and result under `eval/local/`. That directory is Git-ignored and its contents must never be committed, force-added, or uploaded to GitHub.
