# Phase 8 Evidence

## Authority and checkpoint review

Read before continuing:

- `docs/AGENTS.md`;
- `README.md`;
- `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`;
- every file in the newest Phase 7 session archive;
- Git status and the latest commits.

The working branch began Phase 8 at reconstructed Phase 7 commit `213161d`. The local safety branch `safety/phase-0-7-complete-20260817` remained available. No push was performed.

## Development ablation

Command:

```powershell
.\.venv\Scripts\python.exe eval/run_phase8_ablation.py eval/synthetic_phase8_ablation_corpus.json --model-cache data/models/fastembed --vision-model data/models/yolov8n.onnx --synthetic-image eval/synthetic_phase8_image.ppm
```

The 30 made-up development cases selected `without_visual`: OCR layout enabled, subject Kiwi weight `0.05`, PMI enabled, visual evidence disabled, and new model-session scheduling disabled.

- subject: `0/30` to `10/30`, gain `0.333333`, exact paired `p=0.001953125`;
- template: `15/30` to `23/30`, gain `0.266667`, exact paired `p=0.0078125`;
- combined path: `0/30` to `7/30`, gain `0.233333`, exact paired `p=0.015625`;
- authoritative-local subject precision: `10/11 = 0.909091`;
- PMI contribution: eight improvements, zero regressions, `p=0.0078125`;
- visual contribution: zero improvements, zero regressions, `p=1.0`.

## Frozen held-out verification

Command:

```powershell
.\.venv\Scripts\python.exe eval/run_phase8_ablation.py eval/synthetic_phase8_held_out_corpus.json --model-cache data/models/fastembed --vision-model data/models/yolov8n.onnx --synthetic-image eval/synthetic_phase8_image.ppm --verify-selection sort_pilot/classification/data/phase8_optional_evidence.json
```

The separate 30-case made-up held-out corpus verified the fixed development selection:

- subject: `2/30` to `14/30`, gain `0.40`, 12 improvements, zero regressions, exact paired `p=0.00048828125`;
- template: `13/30` to `30/30`, gain `0.566667`, 17 improvements, zero regressions, exact paired `p=0.0000152587890625`;
- combined path: `1/30` to `14/30`, gain `0.433333`, 13 improvements, zero regressions, exact paired `p=0.000244140625`;
- authoritative-local subject precision: `14/14 = 1.0`.

The final resource reproduction measured:

- Phase 7 baseline P95 latency: about `371.8 ms`;
- selected candidate P95 latency: about `11.7 ms`;
- latency ratio: about `0.0315`;
- baseline peak process memory: about `905.4 MB`;
- selected candidate peak process memory: about `905.4 MB`;
- host physical memory: about `16240.8 MB`.

Resource values can vary between runs; the runner evaluates the measured values against the fixed limits each time.

## Focused and complete verification

Focused Phase 8, subject, extraction, service, and documentation checks passed `45` tests.

Complete command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Final results:

- complete suite: `192 passed in 6.71s`;
- dependency validation: `No broken requirements found.`;
- whitespace validation: no errors; only Git's existing LF-to-CRLF notices.

One intermediate complete run reported `191 passed, 1 failed` because a new service test still expected PMI to be disabled after the development selection had correctly retained it. The test input and expectation were corrected to verify retained PMI and rejected visual evidence. The next complete run passed all 192 tests.

## Privacy and repository evidence

- Both Phase 8 corpora contain only invented filenames, text, subjects, and templates.
- The small PPM image is made up for resource measurement.
- No real local filename, extracted text, label, prediction, or correction was used.
- `eval/local/` remains Git-ignored for any real evaluation.
- No personal-example or Gemma-cache document was added.
- No network call or model download occurred.
- No live organization, deletion, or push occurred.
