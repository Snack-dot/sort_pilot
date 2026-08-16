# Implementation Outcome

Status: implemented, committed, pushed, and separately validated against real user data on `architecture-srs-implementation`.

## Delivered (fixes)

- Verified multilingual stopword library (`stop-words` package) replacing a 4-word hardcoded list.
- YOLO object detection routing fix: no longer structurally unreachable for EXIF-less `.png` files.
- Calibration sampling widened to 20 files per family with a `min_cluster_size` connectivity filter, replacing an unfiltered 3-file random draw.
- Rebalanced co-occurrence pair weight (`PAIR_WEIGHT_SCALE`) and small-batch discovery threshold (`SMALL_BATCH_FLOOR_SCALE`) against measured real seed-vocabulary behavior.
- Pretrained fastText (Korean + English) semantic rescue layer (`classifier_engine/embeddings.py`), fallback-only, using greedy best-match word-pairing rather than averaging.
- PMI-based bigram/trigram collocation extraction (`extract.py`), feeding humanized phrases into the existing term pipeline.
- Complete-linkage clustering (`topics.py`), replacing single-linkage clustering that chained unrelated files into mega-clusters at real corpus scale.
- `humanize_term()` fallback-naming fix, removing raw internal feature-token syntax from folder names.
- Rewritten local AI naming assistant (`local_tagger.py`): one `json_schema`-constrained request per cluster instead of one loosely-hinted batched request.
- Consent-gated `EmbeddingsInstaller` for the `word_vectors.npz` model artifact, mirroring the existing Gemma/llama.cpp installer pattern.
- `data/models/yolov8n.onnx` committed directly; `.gitignore` restructured from a directory-level exclude to a file-level negation to allow it.
- Documentation sync: `docs/HIERARCHICAL_TOPICS.md`, `docs/IMPLEMENTATION.md`, `docs/INTEGRATION_PROCESS.md`, `docs/FUNCTION_MAP.md`, `README.md`, `THIRD_PARTY.md`, `CHANGELOG.md`.
- New test coverage: `tests/test_embeddings_installer.py`.

## Verification (fixes)

- Real-world content-bearing topic coverage: 0% → approximately 88.7% (approximately 60.0% without the optional semantic-rescue/embeddings model), measured via full read-only dry runs against a real 760-file Downloads folder.
- Clustering defect: maximum cluster size 412 files (single-linkage) → 31 files (complete-linkage) on an identical real-corpus re-run.
- Local AI naming: 0/11 → 11/11 valid names against real cluster data.
- Fresh-clone, fresh-install integration check performed before push, confirming a new user has everything needed (`yolov8n.onnx` committed; `word_vectors.npz` installable via consent-gated download) to reach the documented coverage level without any manual Windows-specific setup.

## Delivered (real-world validation and reversal)

- Full (non-dry-run) execution of the fixed pipeline against a real, personal `~/Downloads` folder (760 files), gated by an explicit pre-execution review of the weakest cluster, the unmatched-file count, and a plan summary.
- A pre-move safety check that hard-aborts (`RuntimeError`) on any divergence between the confirmed exclusion set and the executed run's actual exclusion set; this caught and correctly blocked three distinct issues before any file was touched (see `evidence.md`).
- Successful run: 734/734 planned moves, 26 files correctly excluded and left in place, 101 topic profiles saved, 107 destination folders — matching the reviewed plan exactly.
- Full reversal on request via `organizer.undo_latest` against the run's own history batch: 734/734 files restored to original paths, created folders removed once empty, `~/Downloads` confirmed back to its original layout.

## Verification (real-world validation and reversal)

- Pre-run: two independent dry runs against the same 760-file corpus reproduced identical cluster counts (112) and identical membership for the flagged weak cluster (26 files), used as the basis for user confirmation.
- Post-run: folder breakdown printed and reviewed (see `evidence.md`); excluded-file count matched the confirmed 26 exactly.
- Post-undo: restored-file count (734) matched moved-file count exactly; top-level `~/Downloads` listing confirmed to match its pre-run state, files-only.

## Operational finding carried forward

`HistoryStore`'s on-disk location is keyed off `QApplication`'s application name via `QStandardPaths.AppDataLocation`. The packaged app sets this in `sort_pilot/app.py` (`"Sort Pilot"`); the ad hoc validation script used for this session's real-world run did not, so its move history landed in a differently-named AppData folder, invisible to the packaged app's own Undo action. Any future tooling that drives `organizer.execute_batch` outside `app.py`'s entry point should set the same application name first, or Undo will silently split across two history files. This is recorded here and in `CHANGELOG.md` (2026-08-16 entry) rather than fixed in code, since it is a property of how the ad hoc script was invoked, not a defect in `app.py` itself.

## Not delivered / explicitly out of scope

- No push beyond the 10 commits explicitly authorized by "PUSH" (`ddfe04c` through `6bc5466`). This archive's own companion commit (`5c8c5e8`) and any further documentation commits remain local until separately authorized.
- No file from the real Downloads folder, and no content derived from those files beyond aggregate counts and the specific pre-confirmed exclusion filenames, was committed or otherwise persisted into the repository.

## Detailed records

- Fix rationale: `decisions.md` (this archive)
- Prompt-by-prompt reconstruction: `conversation.md` (this archive)
- Raw evidence and log excerpts: `evidence.md` (this archive)
- Narrative changelog entries: root `CHANGELOG.md`, dated 2026-08-14 and 2026-08-16
