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

`synthetic_student_held_out_corpus.json` contains 68 additional made-up cases using the same simple fields. None of its filename/text pairs occurs in the Phase 2 corpus, it covers all 18 configured subjects and all five templates, and it was not used to write or revise the subject/template *prototype text*. (18 of its cases were added during the filename/margin remediation specifically to exercise the new catalog-bounded filename aliases and indicators; those aliases were derived from the fixed subject/template catalog itself, not fitted to this held-out result.)

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

## Phase 7 personal-example calibration

Phase 7 uses the made-up Phase 2 corpus as pretend previously approved personal examples and the separate 68-case made-up held-out corpus as future files. It derives subject and template weights and minimum similarities independently while retaining the Phase 5 routing thresholds.

Reproduce and verify the packaged rule with the already downloaded, Git-ignored E5 model:

```powershell
python eval/run_personal_example_calibration.py eval/synthetic_student_corpus.json eval/synthetic_student_held_out_corpus.json --model-cache data/models/fastembed --verify-policy sort_pilot/classification/data/personal_example_policy.json
```

The runner writes nothing. It prints only the rule and aggregate per-axis counts/rates. The tracked examples are entirely made up; do not substitute real filenames, text, labels, predictions, or corrections into either tracked corpus.

## Real labels stay local

Do not place an evaluation made from real files in any tracked synthetic JSON file. Put every real filename, extracted text, label, prediction, correction, and result under `eval/local/`. That directory is Git-ignored and its contents must never be committed, force-added, or uploaded to GitHub.

## Phase 8 optional evidence and low-end measurement

`synthetic_phase8_ablation_corpus.json` is the 30-case made-up development corpus. It was used to choose the smallest tested Kiwi lexical weight that cleared the agreed gates while retaining at least 90% authoritative-local subject precision. `synthetic_phase8_held_out_corpus.json` is a separate 30-case made-up final corpus with different filenames and wording. Neither file has invented case IDs.

Run the cache-only aggregate evaluation with the already available local models:

```powershell
python eval/run_phase8_ablation.py eval/synthetic_phase8_ablation_corpus.json --model-cache data/models/fastembed --vision-model data/models/yolov8n.onnx --synthetic-image eval/synthetic_phase8_image.ppm
python eval/run_phase8_ablation.py eval/synthetic_phase8_held_out_corpus.json --model-cache data/models/fastembed --vision-model data/models/yolov8n.onnx --synthetic-image eval/synthetic_phase8_image.ppm --verify-selection sort_pilot/classification/data/phase8_optional_evidence.json
```

The runner writes nothing and counts every unresolved result as incorrect. Each of subject accuracy, template accuracy, and combined-path accuracy must improve by at least five percentage points with an exact paired `p < 0.05`. Candidate P95 latency may be at most 10% above the Phase 7 baseline, and candidate peak process memory must stay at or below 2 GB.

The final command verifies the complete selection frozen from development rather than choosing again from held-out labels. Development retained PMI (`p=0.0078125`) and rejected visual evidence (`p=1.0`). The final made-up result retained layout-aware OCR, subject Kiwi lexical weight `0.05`, and PMI: subject accuracy rose from `6.67%` to `46.67%` (`p=0.000488`), template accuracy from `43.33%` to `100%` (`p=0.0000153`), and combined-path accuracy from `3.33%` to `46.67%` (`p=0.000244`). Authoritative-local subject precision was `10/11` on development and `14/14` on held-out. The final P95 latency reproduction was about `11.7 ms` versus `371.8 ms`, and peak process memory was about `905.4 MB`. Visual evidence and new model-session scheduling were not retained.

The measurement host had about 16 GB physical RAM. The agreed 2 GB peak-process limit is recorded as a low-memory viability proxy; this result does not claim that the host itself had 4–8 GB RAM.
