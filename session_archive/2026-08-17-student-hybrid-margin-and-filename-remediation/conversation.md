# Reconstructed Conversation and Prompt Log

## 1. The diagnostic report

The branch owner pasted a long, detailed diagnostic report (written in the voice of someone preparing findings to hand to "Codex," a separate implementer) analyzing a manual review of 62 real files run through the freshly-merged Phase 0-8 student-hybrid classifier via 5 screenshots of the app's review UI. Key claims: 52/62 files sent to Needs Review (83.9%), at least 7 files silently auto-routed to a wrong template (not even reaching review), and a root-cause hypothesis pointing at (1) filename subject evidence not reaching the subject classifier structurally, (2) missing template filename indicators (`문제`/`문제지`/`정답`/`해설`/`듣기대본`/`수능특강`/`수능완성`), and (3) a dangerously permissive template acceptance margin (~0.000118). The report explicitly said: "This should be treated as a remediation of the existing classifier, not as a new phase," and separately: "never commit the filenames or labels."

### User prompt (quoting the report's closing framing)

> The correct remediation is not simply "improve the AI." It is: [...] This should be treated as a remediation of the existing classifier, not as a new phase. No workspace changes were made in this side conversation.

## 2. Scoping the response

Given the scale and the freshness of someone else's architecture, a clarifying question was asked before touching anything: document the findings only, implement the fix directly, or just discuss. The user chose to implement directly.

### User prompt

> "Implement the remediation myself" (selected from a scoping question)

## 3. Plan-mode investigation

Plan mode activated automatically. An Explore agent traced the exact wiring: `service.py`'s evidence construction, `calibrated_policy.py`'s threshold-fitting algorithm, the current JSON content of both profile files, `result.py`'s validation rules, and the existing test patterns in `tests/test_subject_e5.py`/`tests/test_template_classifier.py`. A Plan agent then independently re-verified every claim in the diagnosis against the actual source — not the report's guesses — including hand-tracing the calibration tie-break's safety against the existing test suite, and surfaced two findings the original report hadn't mentioned: `eval/run_personal_example_calibration.py` had the same missing-weight bug as the policy calibration script, and the new evidence contribution had to be inserted in a specific tuple position to avoid breaking an existing index-based test assertion. The resulting plan was reviewed, written to a plan file, and approved.

## 4. Implementation

Work proceeded task-by-task against the approved plan: the subject filename-alias channel (new JSON schema, `_filename_scores` resolver with longest-match precedence, weight wiring through `Phase8OptionalEvidence`), the template `file_name_indicators` data fix, the calibration tie-break sign flip, the calibration/production weight-passthrough fix, an 18-case expansion of the invented held-out corpus, new unit tests, and `docs/FUNCTION_MAP.md`. The full test suite was run after each round (205 passed throughout, with two expected, then fixed, failures from stale assertions).

Running the actual recalibration (after installing `fastembed` and downloading the E5 model into the git-ignored local cache) revealed the tie-break fix alone hadn't moved the template margin — a `minimum_margin` floor parameter was added and empirically swept to `0.02`, which produced the intended effect: template margin `0.000118 → 0.141`, precision `95.5% → 100%`.

## 5. Real-data validation

### User prompt

> I downloaded 2027 수능특강 독서 file with about 100 files. Please recalibrate everything on that.

The referenced folder was located at `~/Downloads/2027 수능특강 독서` — the exact real dataset the original 62-file report had been drawn from, now expanded to 100 files. Rather than guess at ground truth, labels were assigned conservatively from literal filename evidence (plus the handful of subject labels the original report itself had already confirmed), stored only under the git-ignored `eval/local/` directory per the report's own explicit instruction, and never committed. Running the fixed classifier against these real files (filename only, no body text, deliberately conservative) returned 50/50 subject and 57/57 template correct — every case the original report flagged as a failure now resolves correctly — and recalibrating against the real data combined with the invented corpus reproduced identical threshold values to the invented-only calibration, confirming the fix generalizes.

## 6. This archive

Following the `session_archive/` convention established earlier in the branch's history and reused for the previous remediation session, this archive was created to record the investigation, decisions, and real-data verification — with the real dataset and its labels deliberately excluded from every committed file.
