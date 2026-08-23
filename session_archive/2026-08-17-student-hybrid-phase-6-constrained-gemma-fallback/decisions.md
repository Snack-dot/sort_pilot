# Phase 6 Decisions

- Phase 6 implements only constrained Gemma fallback. Phase 7 and later work remain out of scope.
- The only classification axes remain subject and template.
- A fallback request requires the validated saved student profile used by the classification flow.
- Subject candidates must be exact entries in that profile's selected `KR_STUDENT_2026_MVP_V1` list.
- Template candidates must be exactly `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`.
- Only an axis routed as `gemma_fallback` may enter this component. An authoritative local result cannot be reconsidered, and a local abstention cannot be escalated.
- Gemma receives ranked supplied candidates, their local raw scores, and bounded extracted evidence. It does not receive or return a path.
- The only valid result is one exact supplied candidate or the exact Needs Review output.
- Invented labels, altered labels, path-like labels, additional result fields, malformed output, unavailable Gemma, and retry exhaustion all remain Needs Review.
- The llama.cpp `json_schema`/`schema` keys appear only as the local server protocol's constrained-response mechanism required by Phase 6. They do not rename a product template or create another classification concept.
- One server handles up to five requests per batch. Only unresolved requests are retried, with two retries after the initial attempt.
- Cancellation is explicit, checked before startup and at bounded work boundaries, and terminates the active local server.
- Every valid result is cached immediately. Valid Needs Review output is cacheable; runtime failures and invalid output are not.
- Cache keys hash every model-visible input, relevant version, and student catalog constraint. Cache values contain only axis and validated selection.
- The cache never stores paths, filenames, natural text, or structured extracted evidence. Its path is supplied by the application and is local state, not a tracked repository file.
- The existing consent-gated, checksummed Gemma/llama.cpp installation remains authoritative. Phase 6 adds no dependency and performs no automatic download.
- The legacy local cluster-name generator remains unchanged because Phase 6 is a separate educational per-axis responsibility.
