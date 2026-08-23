# Phase Completion Record

## Phase 3 — Subject profiles and E5 prototype

Completed behavior:

- natural-language Korean prototypes for every subject in the packaged catalog union;
- strict subject-profile loading and validation;
- exact `intfloat/multilingual-e5-small` model registration;
- 384-dimensional vector validation;
- ONNX Runtime CPU execution through FastEmbed;
- download-disabled-by-default local model loading;
- correct E5 `query:` and `passage:` prefixes;
- natural evidence embedded as natural text;
- engineered lexical evidence kept outside the embedding text;
- cached, normalized subject prototype vectors;
- ranking restricted to the student's selected catalog subjects;
- NumPy cosine ranking;
- retained raw top similarity and top-one-versus-top-two margin;
- no calibrated confidence claim;
- focused tests and project documentation;
- real local model smoke and made-up-text mechanics checks.

## Explicitly not implemented

- Phase 4's separate classifier for `학습자료`, `과제`, `교내활동`, `교외활동`, and `증빙서류`;
- Phase 5 acceptance, escalation, or abstention calibration;
- production organization-flow integration;
- any real-label tracked evaluation data.

## Next phase boundary

Phase 3 is complete under the supreme plan. Phase 4 is the next permitted phase, but it has not started in this session.
