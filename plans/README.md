# Educational plan authority

This directory has one governing implementation plan and a separate set of historical references.

## Authority order

1. [`HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`](HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md) is the user-controlled, supreme implementation plan.
2. [`superseded/Codex Prompt — Explicit Korean Curriculum Dataset and Rules.md`](superseded/Codex%20Prompt%20%E2%80%94%20Explicit%20Korean%20Curriculum%20Dataset%20and%20Rules.md) is the user-supplied curriculum reference and is the most important reference document.
3. [`superseded/Codex Prompt — Sort Pilot Hybrid Educational Classifier.md`](superseded/Codex%20Prompt%20%E2%80%94%20Sort%20Pilot%20Hybrid%20Educational%20Classifier.md) is a preliminary implementation reference.
4. [`superseded/ADR-001-EDUCATION-HYBRID.md`](superseded/ADR-001-EDUCATION-HYBRID.md) is an exploratory architecture record.

Only item 1 is normative. Items 2–4 are references under `superseded/`; none may override, expand, rename, or reinterpret the supreme plan.

## Implementation rule

- Follow the exact vocabulary, axes, fields, phases, constraints, and amendments written in the supreme plan.
- Consult a superseded document only for background that does not conflict with the supreme plan.
- Never restore superseded institution labels, curriculum-transition logic, fallback subjects/templates, the old `학업` term, a document-type axis, or any other behavior excluded by the supreme plan.
- Record an approved user amendment in the supreme plan before implementing it.
- If the supreme plan does not determine a necessary implementation choice, stop and ask the user first.
