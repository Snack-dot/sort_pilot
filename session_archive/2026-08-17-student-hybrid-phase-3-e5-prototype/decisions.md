# Phase 3 Decisions

## Governing authority

- `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md` is the supreme plan.
- Documents under `plans/superseded/` remain reference-only.
- The exact Phase 3 nouns remain subject, subject profile, prototype, embedding, catalog, raw similarity, and margin.
- Phase 3 does not implement the five-template classifier, policy calibration, production-flow integration, or later phases.

## Subject profiles

- Subject profiles are packaged as inspectable JSON and must cover exactly the union of labels defined by the packaged 2026 subject catalog.
- Each profile contains natural Korean descriptions suitable for embedding.
- Missing labels, additional labels, additional fields, blank text, duplicate descriptions, and unsupported profile versions are rejected.
- Runtime ranking is restricted to the subjects in the saved student's selected catalog.

## E5 embedding and ranking

- The exact model is `intfloat/multilingual-e5-small` with 384-dimensional output.
- FastEmbed is registered explicitly for that model and forced to ONNX Runtime `CPUExecutionProvider`.
- Download is disabled by default; normal construction uses only the local cache. A caller must explicitly choose `allow_download=True` for the initial download.
- Natural subject evidence is embedded with the E5 `query:` prefix and natural subject prototypes with `passage:`.
- Engineered lexical terms are not serialized into the natural embedding text.
- Prototype vectors are averaged by subject and normalized. Evidence is normalized and ranked with NumPy cosine similarity.
- The result retains the raw cosine similarity and top-one-versus-top-two margin. It does not treat similarity as calibrated confidence.
- Vector shape, finiteness, and nonzero norm are validated.

## Evaluation boundary

- The ten-item manual mechanics check contains only made-up Korean text.
- Its 10/10 result is not reported as production subject accuracy or held-out model quality.
- No real filename, real extracted text, real label, real prediction, or real correction was added to tracked files.

## Repository boundary

- The downloaded model stays in Git-ignored `data/models/fastembed/`.
- No commit or push is part of this session.
