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

## Phase 5 held-out calibration

`synthetic_student_held_out_corpus.json` contains 50 additional made-up cases using the same simple fields. None of its filename/text pairs occurs in the Phase 2 corpus, it covers all 18 configured subjects and all five templates, and it was not used to write or revise the subject/template profiles.

The approved operating targets are:

```text
local acceptance: 90% held-out precision
Gemma escalation: 50% held-out top-label accuracy
below escalation threshold: Needs Review
```

Reproduce and verify the independently calibrated subject/template thresholds with the already downloaded, Git-ignored E5 model:

```powershell
python eval/run_policy_calibration.py eval/synthetic_student_held_out_corpus.json --model-cache data/models/fastembed --verify-policy sort_pilot/classification/data/calibrated_policy.json
```

The runner writes nothing. It prints only the centralized policy and aggregate per-axis counts/rates. Do not revise profiles from this held-out result; doing so would invalidate the separation between profile writing and policy calibration.

## Real labels stay local

Do not place an evaluation made from real files in any tracked synthetic JSON file. Put every real filename, extracted text, label, prediction, correction, and result under `eval/local/`. That directory is Git-ignored and its contents must never be committed, force-added, or uploaded to GitHub.
