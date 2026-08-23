# Evidence

## Git history

- `fix` was updated to `5c98de4` (`죽은 코드 정리`).
- `34e769a` introduced active role-aware LLM classification.
- `5c98de4` removed the inactive statistical/profile stacks.
- `architecture-srs-implementation` was updated to `6bc5466`, then to `e168964` through documentation commits `5c8c5e8` and `e168964`.

## Branch relationship at comparison time

At `6bc5466`, the architecture branch had no commits absent from `fix`; `fix` had 19 later commits. After the new archive commits, the branches diverged documentation-wise.

## Recovered real-world evidence

The 2026-08-14 archive records:

- content-bearing coverage approximately 0% to 88.7%;
- single-linkage maximum cluster size 412 versus complete-linkage approximately 31;
- local naming validity 0/11 versus 11/11;
- 734/734 planned moves completed;
- 734/734 moves reversed through history;
- three pre-move aborts that prevented execution-plan drift from touching files.

These results support keeping the existing classifier architecture and safe execution boundary, while also showing that coverage is not labeled accuracy.

## Verification during initial foundation work

- Initial educational contract tests: 5 passed.
- Expanded contract/documentation tests after persistence and subject interfaces: 11 passed.
- Final focused foundation tests after the policy arbiter: 14 passed.
- Python compilation and `git diff --check` passed.
- The existing analysis-queue test repeatedly exceeded its five-second deadline in this environment; the branch also emitted a pre-existing ONNX Runtime native access-violation trace. New foundation modules were not imported by that queue path.

## Public reference check

The Ministry notification and rollout information were checked only to evaluate the supplied Markdown. The final product decision deliberately does not implement a legal curriculum or year-by-year rollout engine; those materials inform the practical 2026 catalog only.

## Current-code mismatch evidence

The exploratory foundation currently contains behavior the final plan rejects:

- `Semester.COMMON` and `Semester.UNKNOWN`;
- hard-coded subject lists;
- `SPECIAL_SUBJECTS` containing artificial fallback subjects;
- `Activity.ACADEMIC = "학업"` instead of `학습자료`;
- `Activity.NEEDS_REVIEW` as a sixth template;
- folder rendering for fallback values;
- migration semantics around a generic curriculum version.

Phase 0 of the final plan lists these as mandatory remediation, with tests to be rewritten before production integration.
