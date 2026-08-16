# Reconstructed Conversation and Prompt Log

This document preserves user prompts verbatim where available and summarizes assistant/tool activity professionally. Per-message timestamps were not exposed by the conversation; date boundaries are inferred from Git commit timestamps and background-task log output.

## 1. Repository setup and design philosophy

### User prompt

> https://github.com/Snack-dot/sort_pilot/tree/architecture-srs-implementation clone this repo in the documents somewhere and let's go bug hunting

### Assistant action

Cloned the repository into `~/Documents/sort_pilot` at branch `architecture-srs-implementation` and began a general bug-hunting review.

### User prompt

> the initial proposed idea is to use NLP methods like co-occurence with the words to classify the files based on their contents. Rather than using an LLM. Same for pictures, using YOLO object detection to find the words and creating co-occurence networks in lieu of actual semantic knowledge.

This established the design constraint honored throughout the session: classification stays lexical/statistical (TF-IDF, co-occurrence, PMI collocations, YOLO object labels), with only an optional, clearly-labeled local LLM step for human-readable naming — never for classification itself.

## 2. Root-cause investigation

### User prompt (paraphrased from context)

The user reported that calibrating on 3 folders and teaching the classifier had produced zero real sorts across a 500-file run, and asked for a deep, empirically-verified investigation into why, with fixes for each distinct root cause found — not speculative fixes.

### Assistant investigation and findings

Working file-by-file through `classifier_engine/`, five independent root causes were found and verified against real document pairs and real corpus samples before any fix was written:

1. Co-occurrence pair weight was miscalibrated against base-word weight, so real seed vocabulary essentially never cleared the matching threshold.
2. YOLO object detection was structurally unreachable for the dominant real-world case (`.png` files without camera EXIF), because of a routing condition that excluded them.
3. First-run calibration sampled only 3 files per family with no connectivity filter, so the surfaced "clusters" were frequently unrelated files with no real basis for a shared profile.
4. The stopword list was four hardcoded words; real English documents were matching purely on function-word overlap.
5. There was no semantic fallback at all: two documents about the same topic using different vocabulary had zero lexical overlap and therefore zero similarity.

## 3. Iterative theory refinement

### User prompt

> Hmmm, how would you make it sure that it's automatic? Rather than a random 3 file draw, how do you make sure that the draw draws the similar ones to make a profile?

### Assistant response

Proposed widening the sampling pool and adding a `min_cluster_size` connectivity filter so only genuinely-connected file groups are surfaced as calibration prospects, rather than an arbitrary fixed-size random draw.

### User prompt

> Yeah that make sense. Make huge clusters first, run discover on that pool against itself, then surface the clusters with genuinely connected members as calibration prospects. I want the Yolo thing to work though because that's what spawned this idea in the first place - using YOLO's object detection to cluster images based on similarity (yolo or other lighter weight object detection models as opposed to full VLMs). Other file organizers use LLMS and VLMs to do this and my theory is that you don't need to do it.

Confirmed the pool-then-filter calibration design and reaffirmed the no-VLM constraint specifically for the image path, which shaped the YOLO routing fix (fix root cause 2 above) and kept the resulting `pair:` object co-occurrence features flowing into the same lexical matcher used for text.

### Follow-up refinements (paraphrased from context)

Across several exchanges the user progressively relaxed and then re-tightened the acceptance criteria for false positives — settling on "false positives are okay; keeping recall at the hypernym threshold is already a win" — and asked, in sequence, for:

- A word2vec-style semantic rescue layer to be tried for cases with zero lexical overlap.
- Greedy best-match word-vector pairing to be tried instead of vector averaging, after averaging was shown empirically to blur "same topic" into "same broad domain."
- PMI-based bigram/trigram collocation extraction to be tried: "Collocation and bigram/trigram networks are two very lightweight fixes... try that."

Each was implemented and verified against real document pairs before being kept.

## 4. Full-scale real-data validation (read-only)

### User prompt

> Try doing this to my full downloads folder - but don't allow it to move. Just see what it does.

### Assistant action and finding

Ran a read-only dry-run plan against the real `~/Downloads` folder (760 files). This surfaced a defect invisible at the small scale used for earlier testing: single-linkage clustering was transitively chaining unrelated files into two mega-clusters of 412 and 89 files. Replacing it with complete-linkage clustering (every cross-pair must independently clear the similarity threshold) dropped the maximum cluster size to 31/24 files and raised cluster count from 11 to 112 on an identical re-run of the same corpus.

## 5. Naming quality

### User prompt

> Honestly, now I'd need to make sure the name of these clusters make sense and it's honestly a legitimately lightweight program for organizing docs. I'd probably use this.

### Assistant action

Found that `fallback_topic()` was leaking raw internal feature-token syntax into folder names (e.g. `obj_person pair_dining_table+person`). Added `humanize_term()` to prefer collocation phrases and humanize object labels before they reach a folder name.

### User prompt

> One last thing - check whether the AI naming works?

### Assistant finding

Tested the optional local Gemma naming assistant end-to-end against real cluster data and found it reliably failed in its original batched form (0/11 valid names): a loose JSON hint under one multi-cluster request produced malformed output and wrong topic names.

### User prompt

> try both

### Assistant action

Tried both one-request-per-cluster and a `json_schema`-constrained response format; the combination fixed the failure completely (11/11 valid names against the same real cluster data) and was kept.

## 6. Session documentation and commit splitting

### User prompt

> Alright write this session and update all the docs and we can be good to go. We went from 0 to 88%, that's pretty good.

### Assistant action

Updated `docs/HIERARCHICAL_TOPICS.md`, `docs/IMPLEMENTATION.md`, `docs/INTEGRATION_PROCESS.md`, `docs/FUNCTION_MAP.md`, `README.md`, `THIRD_PARTY.md`, and added a dated `CHANGELOG.md` entry summarizing the recall/precision correction.

### User prompt

> Split the commit. Write those commits somewhere. Do not push. It was my idea but it was still a different team who was building this. I felt responsible for them so I decided to independently verify the problems and do fixes instead of leaving them for dead. They get final call with the final product.

### Assistant action

Split the accumulated working-tree changes into 9 logically-separated commits (later 10, see §8), each with a rationale-bearing message aimed at a reviewer who was not present for the investigation. Nothing was pushed at this point.

## 7. Distribution verification

### User prompt

> One final thing - will this work without changing anything about the windows and stuff? Like if I push this and my friend gets it, can she just run it and see about 90% coverage?

### Assistant finding

The honest answer was no, not without additional setup: two required model files (`data/models/yolov8n.onnx`, `data/models/word_vectors.npz`) were gitignored and would be silently absent on a fresh clone, well below the ~112 MB and ~13 MB sizes needed for full coverage.

## 8. Model artifact handling

### User prompt

> Just commit yolov8n.onnx and the word_vectors.npz. We've already put it in the third_party.md anyway. We're already using stopwords too anyway. Just commit all of it.

### Assistant action (interrupted mid-flow by the user)

> [Tool use interrupted by user] Fine, commit yolov8n.onnx directly and build a consent-gated download step for word_vectors.npz before committing. Don't push. I haven't gotten a confirmation yet.

`word_vectors.npz` (~112 MB) exceeds GitHub's 100 MB hard file-size limit and cannot be committed directly. `yolov8n.onnx` (~13 MB) was committed directly after fixing a `.gitignore` structure bug (a directory-level exclude was blocking a file-level negation). A consent-gated `EmbeddingsInstaller` was built for `word_vectors.npz`, streaming only the top 100k words per language from the official fastText vectors rather than the full multi-gigabyte file, with structural verification since the output is environment-dependent rather than byte-identical.

## 9. Integration verification and push

### User prompt

> Make sure everything is all integrated so that when she gets this push (do not push yet), she can immediately run it.

### Assistant action

Performed a fresh-clone, fresh-install verification to confirm a new user would have everything needed to run at the documented coverage level.

### User prompt

> PUSH

### Assistant action

Pushed the 10 local commits (`ddfe04c` through `6bc5466`) to `origin/architecture-srs-implementation`. This was treated as a single, explicit authorization for that specific push, not a standing permission for future pushes.

## 10. Real-world validation and reversal

### User prompt

> Lol can you run the pipeline on my downloads folder? I kind of need to organize it.

### Assistant action

Ran the fixed pipeline end-to-end (not a dry run) against the real `~/Downloads` folder. Before moving anything, the plan was reviewed with the user via targeted questions covering the weakest cluster, the 223 unmatched files, and whether to review the full 108-folder plan or a summary; the user chose to leave the weak cluster in place, include the unmatched files, and see a summary rather than the full plan.

Reaching a clean execution took three aborted attempts, each caught by a pre-move safety check before any real file was touched — a diagnostic counting bug, a macOS NFC/NFD Unicode filename-normalization mismatch, and one borderline file with run-to-run unstable cluster assignment (resolved by matching confirmed filenames directly, independent of clustering output). The fourth attempt completed cleanly: 734/734 planned moves succeeded, 26 files correctly excluded and left in place, matching the previously-reviewed plan exactly.

### User prompt

> Reverse pls. undo.

### Assistant action

Used `organizer.undo_latest` against the run's own `HistoryStore` batch to restore all 734 files to their original paths, then removed the folders the run had created once they were empty (including two that were "empty" only because they contained a macOS `.DS_Store` Finder artifact). `~/Downloads` was confirmed back to its pre-run layout.

## 11. This archive

### User prompt

> You didn't commit or add this sessions conversation log. Add them please so the next user knows what exactly happened in this session.

### Follow-up

> Did you read the sessions folder?

### Assistant action

The initial response to the first prompt was a `CHANGELOG.md` entry written from conversation context, without having located the existing `session_archive/` convention first. Once pointed at `session_archive/2026-08-13-app-classifier-integration/`, this archive was created to match that established format.
