# Phase 3 Evidence

## Starting Git state

- Branch: `architecture-srs-implementation`
- Tracking state: ahead of `origin/architecture-srs-implementation` by two commits.
- Latest local commits at session start:
  - `66f1a84 Record student hybrid checkpoint metadata`
  - `c9706d3 Checkpoint student hybrid classifier plan`
- The existing worktree contained uncommitted Phase 0–2 work and documentation moves. Those changes were preserved.

## Plan evidence

The controlling Phase 3 text appears in `plans/HYBRID_EDUCATIONAL_CLASSIFIER_PLAN.md`:

> Create natural-language subject prototypes, generate 384-dimensional multilingual E5 embeddings, rank only catalog subjects, and retain raw similarity and margin.

The same plan identifies FastEmbed, `intfloat/multilingual-e5-small`, ONNX Runtime `CPUExecutionProvider`, and NumPy cosine similarity as the primary local classifier stack. It also requires natural text to remain natural text instead of serializing engineered values into a fake sentence.

## Dependency and artifact evidence

- Virtual environment dependency: `fastembed==0.8.0`.
- Direct numerical dependency: `numpy==2.4.6`.
- Model identifier: `intfloat/multilingual-e5-small`.
- Hugging Face snapshot: `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- ONNX file size: `470,268,510` bytes.
- ONNX SHA-256: `CA456C06B3A9505DDFD9131408916DD79290368331E7D76BB621F1CBA6BC8665`.
- Cache location: `data/models/fastembed/`, excluded by the repository's model-cache ignore rule.
- Local smoke output: two finite, normalized `float32` vectors with shape `(2, 384)`.
- Final cache-only smoke output: one finite, normalized `float32` vector with shape `(1, 384)` and norm `1.0`.

## Test evidence

- `tests/test_subject_e5.py`: 9 passed.
- `tests/test_subject_e5.py tests/test_education_contracts.py`: 38 passed.
- `tests/test_subject_e5.py tests/test_documentation.py`: 11 passed after isolating the adapter-argument test from the unrelated legacy native DLL state.
- Complete suite: 109 passed in 9.50 seconds; pytest exit code `0`.

The complete suite still emits the previously observed Windows ONNX Runtime access-violation trace from the legacy vision path. This occurs independently of the Phase 3 focused tests, which pass without the trace. The Phase 3 adapter test uses an isolated FastEmbed stand-in to verify the exact registration, CPU-provider, cache-only, batching, and output-validation arguments without importing the native runtime a second time in the same full-suite process.

## Made-up-text mechanics check

Ten synthetic Korean examples covering 수학, 영어, 과학, 한국사, 국어, 정보, 통합과학, 음악, and 진로 produced the expected top subject after profile wording review. The check used the actual cached E5 model with downloads disabled. It is evidence that the implementation runs and that the prototype text is usable; it is not a production accuracy, calibration, or held-out evaluation claim.

## Final verification

- `pip check`: no broken requirements found.
- Installed versions confirmed: FastEmbed 0.8.0, NumPy 2.4.6, and ONNX Runtime 1.27.0.
- `git check-ignore -v` confirmed that the exact E5 ONNX artifact is excluded by `.gitignore`'s `data/models/*` rule.
- The final model SHA-256 and size match the dependency record above.
- `git diff --check`: passed.
- No trailing whitespace was found in the Phase 3 implementation, test, documentation, or archive files.
- No rejected `schema`, `fixture`, `document_type`, or folder-usefulness vocabulary was found in the Phase 3 implementation, tests, or archive.
- Final Git status remained on `architecture-srs-implementation`, ahead by two commits, with the pre-existing uncommitted Phase 0–2 work, documentation moves, and the new Phase 3 files visible.
- No commit or push was performed.
