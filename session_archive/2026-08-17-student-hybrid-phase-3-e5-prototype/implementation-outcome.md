# Phase 3 Implementation Outcome

## Delivered implementation

- `sort_pilot/classification/data/subject_profiles_ko.json` — natural Korean subject prototypes covering the exact packaged catalog union.
- `sort_pilot/classification/subject.py` — strict subject-profile and natural-evidence contracts.
- `sort_pilot/classification/e5.py` — FastEmbed E5 encoder and catalog-only subject ranker.
- `sort_pilot/classification/__init__.py` — public Phase 3 exports.
- `tests/test_subject_e5.py` — strict loading, evidence separation, catalog bounds, ranking, cache, dimension, and CPU/cache-only adapter tests.
- `pyproject.toml` and `requirements.txt` — pinned FastEmbed and NumPy dependencies plus packaged profile data.

## Delivered documentation

- `README.md` — current Phase 3 capability and boundary.
- `CHANGELOG.md` — Phase 3 change record.
- `docs/FUNCTION_MAP.md` — new public and internal callable map entries.
- `docs/THIRD_PARTY.md` — FastEmbed, NumPy, exact E5 artifact, license, hash, size, and local-cache policy.
- this session archive — decisions, conversation reconstruction, phase completion, evidence, and outcome.

## Operational behavior

The encoder is local and CPU-only. It will not download by default. Once the exact model is present in `data/models/fastembed/`, the ranker embeds natural evidence, considers only subjects in the supplied catalog, and returns ordered candidates together with raw similarity and margin.

The Phase 3 ranker is intentionally not wired into the production organization flow. That boundary avoids silently introducing Phase 5 policy decisions before calibration exists.

## Stopping point

Phase 3 is the only new plan phase completed in this session. Phase 4 and later phases remain untouched. No commit or push was performed.
