# Sort Pilot Student Hybrid Classifier — Final MVP Plan

Status: authoritative implementation plan

Date: 2026-08-16

Supersedes: every document under `plans/superseded/`

Authority: this user-controlled plan is supreme. `plans/README.md` defines the reference hierarchy; superseded documents may provide background only and never override this plan.

## 1. Product boundary

Sort Pilot targets one occupation only:

```text
학생
```

The user selects:

```text
학생 유형: 중학생 | 고등학생
학년:      1학년 | 2학년 | 3학년
학기:      1학기 | 2학기
```

The application organizes files that are already downloaded. It does not model schools, educational institutions, legal curriculum compliance, nationwide schedules, or year-by-year curriculum transitions.

## 2. Fixed destination contract

Every approved normal result has exactly this hierarchy:

```text
학생/{중학생|고등학생}/{1학년|2학년|3학년}/{1학기|2학기}/{과목}/{학습자료|과제|교내활동|교외활동|증빙서류}/original_filename.ext
```

Example:

```text
학생/중학생/1학년/1학기/수학/과제/함수숙제.pdf
```

The five and only five template folders are:

```text
학습자료
과제
교내활동
교외활동
증빙서류
```

`학습자료` replaces every earlier use of `학업` because it distinguishes study material from assignments more clearly.

The classifier cannot invent a subject, template, root, or additional path component. Original filenames are preserved.

## 3. Needs Review is state, not a folder

An unresolved axis is represented as state:

```json
{
  "subject": null,
  "template": null,
  "needs_review": true
}
```

There is no `기타`, `미확인`, `분류미확인`, `공통`, `비교과`, or `과목미확인` subject/template folder. A result cannot render a final destination until the user selects one configured subject and one of the five templates in preview.

## 4. Simplified 2026 subject catalog

Use one static, versioned MVP catalog informed by subjects familiar to Korean students in 2026:

```text
KR_STUDENT_2026_MVP_V1
```

This catalog is a sorting constraint, not a legal or institutional model. It has:

- one middle-student subject list;
- one high-student subject list;
- no academic-year resolver;
- no 2015/2022 transition engine;
- no official-versus-active split;
- no school timetable;
- no school-specific configuration;
- no special-subject system.

Store the catalog in inspectable JSON rather than classifier, prompt, or UI source code:

```text
sort_pilot/curriculum/data/subjects_2026.json
```

The classifier and Gemma may choose only exact entries loaded from the selected student-type list.

## 5. Classification representation

Folder layout remains separate from internal evidence. Each axis retains:

```text
label or unresolved
raw score
calibrated confidence when available
top-1/top-2 margin
ranked candidates
evidence contributions
decision source
model/profile/policy versions
review state
```

Decision sources include:

```text
local_classifier
gemma_fallback
user
cache
personal_example
needs_review
```

## 6. Two independent tasks

### Subject classifier

Chooses exactly one configured 2026 MVP subject or abstains. Inputs may include filename, native/OCR text, E5 similarity, Kiwi lexical evidence, and personal examples.

### Template classifier

Chooses exactly one of the five fixed templates or abstains. It uses its own weights and may use semantic intent, filename and lexical indicators, PMI collocations, OCR/layout evidence, optional visual evidence, and personal examples.

Subject and template are routed independently. Gemma may resolve one ambiguous axis without reconsidering a confident result on the other.

## 7. Primary local classifier

The existing classifier architecture remains the implementation base. Upgrade it with:

```text
FastEmbed
intfloat/multilingual-e5-small
ONNX Runtime CPUExecutionProvider
NumPy cosine similarity
Kiwi morphology and lexical features
structured OCR evidence
optional PMI, YOLO/LVIS, and personal-example evidence
```

Natural text is embedded as natural text. Engineered numbers, layout statistics, and visual tokens remain structured evidence rather than being serialized into a fake sentence.

Raw similarity is not called probability. Feature weights and thresholds are centralized and calibrated against labeled data.

## 8. Explicit hybrid authority policy

For each axis:

```text
high raw score + sufficient top-two margin
→ accept local result
→ Gemma cannot override

plausible but ambiguous local evidence
→ constrained Gemma fallback

insufficient evidence or explicit abstention
→ Needs Review

Gemma unresolved or invalid
→ Needs Review
```

Gemma receives only supplied subject candidates, the five templates, ranked local scores, and bounded extracted evidence. Its schema allows one supplied candidate or `Needs Review`; it never returns a path.

## 9. Personalization

Preview corrections are stored locally as separate personal examples containing the fingerprint, embedding, approved subject/template, original prediction, lexical evidence, and relevant versions.

Future files use nearest-example similarity as additional evidence. Do not fine-tune E5 or Gemma and do not mutate global subject/template profiles after one correction.

## 10. Safety and execution

Preserve existing candidate safety, bounded extraction, editable preview, path validation, filename preservation, collision handling, transactional moves, rollback, JSON history, and persistent Undo.

Classification produces an `OrganizationPlan`. Approval freezes exact source and destination paths. Execution never recomputes classification after approval.

## 11. Required remediation of work already introduced

Before onboarding or E5 integration, correct every exploratory assumption that is outside this final plan:

1. Keep `중학생` and `고등학생`; never replace them with institution labels `중학교` or `고등학교`.
2. Replace the generic curriculum/version model with the single `KR_STUDENT_2026_MVP_V1` subject-catalog version.
3. Remove academic-year migration concepts and `requires_migration` behavior tied to curriculum revisions.
4. Remove hard-coded `COMMON_SUBJECTS`, `MIDDLE_SUBJECTS`, and `HIGH_SUBJECTS` from Python; load the curated catalog from JSON.
5. Remove the official-versus-active subject distinction from proposed designs.
6. Remove `Semester.COMMON` and `Semester.UNKNOWN`; retain only first and second semester.
7. Remove `SPECIAL_SUBJECTS`, including `비교과`, `공통`, and `과목미확인`.
8. Replace `Activity.ACADEMIC = "학업"` with the fixed template `학습자료`.
9. Remove `Activity.NEEDS_REVIEW`; review remains state and never becomes a sixth template.
10. Allow unresolved subject/template labels in pre-preview results, but forbid folder rendering and move-plan construction until both are valid.
11. Rewrite tests that currently require obsolete fallback folders or `학업`.
12. Replace the superseded ADR with this plan as the sole normative architecture document.
13. Correct changelog language that describes explicit fallback subjects/templates as intended behavior.

## 12. Implementation phases

### Phase 0 — Remediate the foundation

Apply all thirteen corrections above and keep the active production classifier unchanged. Add contract tests for the exact six folder directories beneath `학생` and the five-template enum.

### Phase 1 — Subject catalog and onboarding persistence

Add the 2026 JSON catalog and persist occupation, student type, grade, semester, and catalog version. No institution or timetable data is collected.

### Phase 2 — Evaluation framework

Build a labeled synthetic corpus and track subject accuracy, template accuracy, combined-path accuracy, coverage, review rate, fallback rate, corrections, latency, and memory.

Only made-up corpus cases and their labels may be tracked. Any evaluation using real local files, filenames, extracted text, labels, predictions, or corrections remains local-only under the Git-ignored `eval/local/` directory and must never be committed or uploaded to GitHub.

### Phase 3 — Subject profiles and E5 prototype

Create natural-language subject prototypes, generate 384-dimensional multilingual E5 embeddings, rank only catalog subjects, and retain raw similarity and margin.

### Phase 4 — Five-template classifier

Implement separate profiles and evidence weights for `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.

### Phase 5 — Calibrated policy

Calibrate per-axis local acceptance, Gemma escalation, and abstention thresholds using held-out data.

### Phase 6 — Constrained Gemma fallback

Port the reliable local Gemma server, schema, cancellation, retry, and caching behavior from `fix`, but restrict output to supplied per-axis candidates.

### Phase 7 — Preview, immutable plan, and corrections

Expose unresolved axes for user selection, freeze approved paths, preserve move/Undo behavior, and store corrections as personal examples.

### Phase 8 — Optional evidence and low-end optimization

Add OCR-layout, PMI, YOLO/LVIS, and model-session scheduling only when ablation and 4–8 GB hardware measurements justify them.

## 13. MVP acceptance criteria

The MVP succeeds when most ordinary files resolve locally, Gemma handles only genuine ambiguity, unresolved files remain safe in preview, every approved path uses a configured subject and one of the five templates, decisions remain observable, inference remains local, and performance is acceptable on measured consumer hardware.

## 14. Governing principle

> Use the smallest, cheapest, most inspectable local mechanism that can confidently sort the file. Use constrained Gemma only for ambiguity. Ask the user instead of guessing.
