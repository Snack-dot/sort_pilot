# Decision Record

## D1 — Investigation standard: empirical, not speculative

**Decision:** Every root cause had to be reproduced or measured against real document pairs or a real corpus sample before a fix was written, and every fix had to be re-verified against the same evidence afterward.

**Rationale:** Explicit user requirement, given zero-recall behavior had already survived one round of calibration and teaching without being caught.

## D2 — Stay lexical/statistical, no LLM or VLM for classification

**Decision:** All fixes stayed within TF-IDF cosine similarity, co-occurrence pair weighting, PMI collocation extraction, pretrained (non-generative) word vectors, and YOLO object detection. The only generative-model step in the whole pipeline is optional, local, and used solely to turn an already-decided cluster into a human-readable folder name.

**Rationale:** Core design thesis of the project — that lightweight statistical methods can match documents by content without an LLM/VLM doing the semantic work. Confirmed explicitly by the user after the YOLO routing fix: this is what motivated the project in the first place.

## D3 — Pair-weight and threshold rebalancing

**Decision:** Rebalance `PAIR_WEIGHT_SCALE` and add `SMALL_BATCH_FLOOR_SCALE` rather than lowering the base similarity threshold globally.

**Rationale:** The threshold itself was reasonable for well-formed vocabulary; the actual defect was that co-occurrence pair weight was disproportionate to base-word weight, so real seed vocabulary essentially never contributed enough signal to cross any reasonable threshold. Verified by reverting and reapplying against real document pairs.

## D4 — YOLO routing fix

**Decision:** Remove the `if route in {"photo", "ambiguous"}` restriction; run YOLO whenever the model file exists.

**Rationale:** The dominant real-world image case — `.png` screenshots/saves without camera EXIF — was structurally routed away from object detection, making the YOLO-driven clustering the user wanted a dead code path in practice.

## D5 — Calibration pool widening and connectivity filtering

**Decision:** Sample up to 20 files per family (not 3), pre-cluster the pool against itself, and only surface genuinely-connected clusters (`min_cluster_size` filter) as calibration prospects.

**Rationale:** User-directed: "make huge clusters first, run discover on that pool against itself, then surface the clusters with genuinely connected members." A fixed random 3-file draw had no mechanism to guarantee the sample was actually representative of a real topic.

## D6 — Real stopword library

**Decision:** Replace the 4-word hardcoded stopword list with the `stop-words` package (BSD-3, static data, fully offline, already an approved dependency class in this project).

**Rationale:** Real English documents were found matching purely on function-word overlap, i.e. false positives driven by grammar rather than content.

## D7 — Semantic rescue: greedy matching over averaging, only as a fallback

**Decision:** Add a pretrained fastText (Korean + English) semantic layer that fires only when exact lexical/co-occurrence matching finds nothing, using greedy best-match word-pairing (a lightweight relaxed Word Mover's Distance) rather than vector averaging.

**Rationale:** Averaging was tried first per the user's request and empirically shown to blur "same topic" into "same broad domain" — too coarse. Greedy matching preserves more of the original word-level signal. Keeping it fallback-only (not primary) preserves D2.

## D8 — PMI collocation/bigram/trigram extraction

**Decision:** Add pointwise mutual information over each document's own token stream to extract fixed phrases, feeding them into the existing `body`-source term pipeline as ordinary features.

**Rationale:** User-suggested as "two very lightweight fixes" alongside semantic rescue; PMI is a standard, dependency-light, non-generative way to recover phrase-level meaning that word-level term weighting misses (e.g. "dining table" vs. independent "dining" and "table").

## D9 — Complete-linkage clustering

**Decision:** Replace single-linkage clustering with complete-linkage (every cross-pair, not just one connecting pair, must independently clear the similarity threshold).

**Rationale:** Single-linkage chaining was invisible at the small scale used for earlier verification and only surfaced at the full 760-file real-corpus scale, where it produced two mega-clusters (412 and 89 files) built from transitively-connected but not mutually-similar files. This was treated as the most severe defect found, since it silently merged unrelated content under one topic name.

## D10 — Human-readable fallback naming

**Decision:** Add `humanize_term()` to prefer collocation phrases and humanize object labels in `fallback_topic()`, instead of exposing raw internal feature-token syntax (`obj_person pair_dining_table+person`) as a folder name.

**Rationale:** A folder name a user cannot parse defeats the purpose of automatic organization even if the underlying cluster is correct.

## D11 — Local AI naming: one request per cluster, schema-constrained

**Decision:** Rewrite `local_tagger.py` to issue one `json_schema`-constrained request per cluster, using already-humanized terms, tolerating individual cluster failures instead of discarding the whole batch.

**Rationale:** The original batched, loosely-hinted multi-cluster request reliably produced malformed output (0/11 valid names on real data). Per-cluster requests with a grammar constraint fixed this completely (11/11) and isolate one bad cluster from poisoning the rest of the batch.

## D12 — Commit splitting for external review

**Decision:** Split the working tree into 10 logically-separated commits, each with a rationale-bearing message, rather than one combined commit — and do not push until explicitly told to.

**Rationale:** Explicit user instruction. The user positioned themselves as a reviewer acting on behalf of, but distinct from, the implementing team, who retain final call on the product. Small, independently-reviewable commits with stated rationale respect that boundary.

## D13 — Model artifact distribution

**Decision:** Commit `yolov8n.onnx` (~13 MB) directly; build a consent-gated, on-demand installer for `word_vectors.npz` (~112 MB) instead of committing it.

**Rationale:** `word_vectors.npz` exceeds GitHub's 100 MB hard file-size limit and cannot be committed as-is regardless of preference. The installer mirrors the existing consent-gated Gemma/llama.cpp installer pattern already in the codebase, streams only the top 100k words per language rather than the full multi-gigabyte source file, and uses structural (not hash) verification since its output is environment-dependent.

## D14 — Explicit, scoped push authorization

**Decision:** Treat "PUSH" as authorization for that specific set of 10 local commits only, not as standing permission for any future push.

**Rationale:** Consistent with the user's repeatedly stated caution throughout the session ("Don't push" appeared multiple times before this point) and with treating destructive/hard-to-reverse or externally-visible actions as requiring their own confirmation each time.

## D15 — Real-world validation run, gated by pre-review

**Decision:** Before executing (not dry-running) against the real `~/Downloads` folder, surface the weakest cluster, the unmatched-file count, and a plan summary for explicit user confirmation, then hard-abort (`RuntimeError`) if the executed run's exclusion set ever diverges from what was confirmed.

**Rationale:** Moving real personal files is not reversible-by-default the way a dry run is; the safety check exists specifically so that a change in the algorithm's clustering output between the reviewed plan and the executed run can never silently move a file the user asked to have excluded.

## D16 — Full reversal on request, via the run's own history

**Decision:** Undo via `organizer.undo_latest` against the exact `HistoryStore` batch the run itself created, rather than attempting to reconstruct original paths independently.

**Rationale:** The batch/journal already records the authoritative source path for every move; reconstructing paths any other way risks drift from what was actually written to disk.
