# Phase 4 Decisions

## Governing boundary

- `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is supreme.
- The classifier has exactly five template candidates: `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Review remains state, not a sixth template.
- Phase 4 does not calibrate local acceptance, Gemma escalation, or abstention thresholds.
- Phase 4 does not integrate the educational classifier into the production organization flow.

## Separate profiles

- Each template has its own natural prototypes, filename indicators, lexical indicators, PMI collocations, OCR/layout indicators, optional visual indicators, evidence weights, and version.
- The packaged profile document must contain exactly the five fixed template labels and no additional top-level, profile, or evidence-weight fields.
- Profile lists must be nonempty and contain nonblank strings.
- Runtime classification requires exactly one profile per template and one shared profile version.

## Separate evidence

- Natural filename/body text is embedded as natural text with the E5 `query:` prefix.
- Natural profile text is embedded with the E5 `passage:` prefix.
- Filename, lexical, PMI-collocation, OCR/layout, optional visual, and personal-example evidence remains structured.
- Personal-example scores are bounded to the five templates and the raw similarity interval from `-1` to `1`. Phase 7 remains responsible for storing corrections as personal examples.

## Evidence weights and output

- Each template profile explicitly contains seven named evidence weights.
- Every weight starts at neutral `1.0`; no value is represented as calibrated.
- Phase 5 remains responsible for calibration against held-out data.
- The classifier ranks all five templates with a weighted raw score and retains the top-one-versus-top-two margin.
- Each returned contribution records its raw evidence value and its profile weight.
- Calibrated confidence remains `None`.

## Evaluation and repository safety

- Only the already tracked made-up corpus was used for the manual E5 mechanics check.
- No real file, filename, extracted text, label, prediction, or correction was added to tracked files.
- The existing Git-ignored E5 model cache was reused without a download.
- No commit or push was performed.
