# Hierarchical Type and Topic Classification

## Destination model

The classifier treats file kind and semantic topic as independent axes:

```text
문서/내과제
이미지/가족사진
문서/고객A
이미지/미분류
```

The fixed first-level roots are `문서`, `이미지`, `압축파일`, `오디오`, `동영상`, and `기타`. Extension routing is authoritative when known, MIME supplies a fallback, and unknown files use `기타`. Executables, scripts, shortcuts, and partial downloads remain excluded before classification.

Every normal destination has exactly two semantic levels. The reserved `미분류` topic is used when no enabled family-specific profile meets its threshold. Previewed legacy migration may preserve additional existing subfolders below the topic.

The move preview renders the detected type as a read-only column. Users select an existing topic or type a new single-folder topic name, but approved output always reconstructs the destination beneath the fixed type root.

## Topic profiles

Profiles live in `%APPDATA%\tidy\topic_profiles.json` using an atomic version-3 JSON document. Each profile contains:

- stable ID, fixed family, and validated single-folder name;
- normalized tags;
- averaged positive example weights/count and negative correction weights/count;
- origin (`user`, `discovered`, or `migration`);
- enabled state and timestamps.

Example paths and raw file contents are never stored. A fresh profile document is empty: there are no built-in topics or semantic seed lexicon. Version-1 `builtin` entries are removed and version-1/2 documents are migrated with empty negative evidence. Every remaining profile was created or confirmed by the user.

The `폴더/태그 관리` tray action lets the user create, rename, enable/disable, or delete profiles. Dragged/selected examples are extracted through the same two-worker queue and update only a profile of the selected family; they are never moved. Physical folders are created only by a later approved move.

## Matching and TF-IDF

Every file first runs the complete `Pipeline.safe_classify()` path. This evaluates Tier-1 evidence rules, extracts local filename/body/OCR/object/pair features, scores the learned Naive Bayes model, persists the decision, and returns its decision ID. The category/action/margin are retained for diagnostics and future feedback, but are never copied into a destination topic. Default coursework and purchase patterns add evidence marks rather than terminal categories.

Content extraction is real and local. Plain text/Markdown/CSV/RTF, PDF, DOCX, ODT, PPTX, and XLSX content is bounded to 20,000 characters and up to 160 distinct body terms. PDF reads the first five pages, workbooks read representative cells, ZIP uses entry names, and eligible images use OCR plus YOLO object evidence whenever the local ONNX model exists (regardless of screenshot/photo routing). Topic vectors retain only body, OCR, object (`obj:`), and object-pair (`pair:`) terms: filename, extension, and generic metadata features can still inform the lower-level engine decision, but cannot create or select a semantic topic. Stopword filtering for both languages comes from the `stop-words` package rather than a hardcoded list. `.hwp` and `.hwpx` are excluded from app collection during architecture validation, while legacy binary DOC/XLS/PPT files cannot become calibration seeds.

Body text also yields statistically significant adjacent bigrams and trigrams (`collocations()` in `extract.py`): an n-gram is kept only when its pointwise mutual information over the document's own token stream clears a floor, so incidental word adjacency is filtered from genuine fixed phrases (e.g. `회귀 분석`). These flow through the same `body`-source pipeline as single words, prefixed `bi:`/`tri:`.

Resolution is intentionally simple: a matching `user`, `discovered`, or `migration` profile wins; otherwise the topic is `미분류`. Topic scoring excludes extension and generic media metadata, then applies existing extraction-source weights.

For each family batch:

1. Weighted TF is `log(1 + weight)`.
2. Smoothed IDF is `log((1 + N) / (1 + df)) + 1`.
3. Within-document co-occurrence pairs are weighted at `PAIR_WEIGHT_SCALE × sqrt(weight(A) × weight(B))` (currently `0.1`) so they inform similarity without outweighing the base words they're derived from.
4. Sparse vectors are L2-normalized.
5. Profile/example cosine similarity is compared to `0.25` for documents, `0.20` for images, and `0.30` for other families.
6. Explicit normalized user tags add `1.5` pseudo-document weight per content token; filenames never satisfy a tag.
7. Final score is `max(0, positive cosine - 0.65 × negative cosine)`, so a correction can overcome an overly broad tag without deleting it.
8. If exact/co-occurrence matching finds nothing, a pretrained-word-vector rescue can still match a record to a profile — see "Semantic rescue" below.

### Semantic rescue

Pure lexical/co-occurrence matching only fires on exact term overlap, which real independently-written documents on the same topic often don't have enough of. When step 7 above finds no qualifying profile for a record, `classifier_engine/embeddings.py` gets one more chance: it takes each side's top-`TOP_N_TERMS` (5) most distinctive words (by `weight × idf`), resolves each to a pretrained fastText vector (Korean + English, `data/models/word_vectors.npz`, not committed), and compares the two documents by greedy best-match pairing — every word on each side matched to its closest counterpart on the other, not averaged into one vector. Averaging was tried first and rejected: it measures "same broad domain" rather than "same topic" (in testing, a university transcript scored 0.72–0.75 against an unrelated CS lecture, nearly as high as genuine same-topic pairs). A match requires clearing `SEMANTIC_MATCH_THRESHOLD` (currently `0.30`, tuned for hypernym-level grouping — e.g. a transcript and a lecture from the same university sharing a folder is acceptable; a document connecting only through a long chain of unrelated intermediate documents is not). `obj:`/`bi:`/`tri:` tokens resolve by decomposing into their constituent words before vector lookup; `pair:`/`co:` tokens have no single-vector meaning and are skipped. If no pretrained vectors are bundled, this step is a no-op and matching falls back to lexical-only, exactly as before this layer existed.

The same rescue mechanism also gates cluster formation during discovery (see below): two records can join a cluster if either their lexical cosine or their semantic similarity clears its threshold.

Single-file/public JSON analysis runs and persists the real engine decision, then checks only saved user-owned profiles. With an empty profile store it returns `<유형>/미분류`. It never creates a discovered TF-IDF profile or moves a file.

### Sample calibration and adaptive discovery

When no profiles exist, organization is paused for calibration. The sampler reads only safe top-level Desktop/Downloads files whose formats have bundled content extraction, chooses at most 20 per family (`CalibrationSampler(per_family=20)`), round-robins source/extension buckets, and prefers fingerprints not used by an earlier calibration. A family with only one or two readable files is still calibrated. After extraction, an empty-content record is removed before topic discovery and cannot be moved as a seed. Fingerprints are hashes captured before movement; readable paths are not stored. Samples are analyzed by the existing two-worker queue.

Discovery runs over that wider pool, but `CalibrationService.build_draft(..., min_cluster_size=2)` only surfaces clusters with two or more genuinely connected members as calibration proposals — singleton files aren't shown or forced into a review row. Only the records referenced by a surfaced cluster (`CalibrationDraft.surfaced_records()`) get their fingerprints remembered, so unsurfaced files stay "unseen" and are re-sampled with priority in a later calibration round instead of being silently dropped forever.

For every family, batches of up to three vectors use `SMALL_BATCH_FLOOR_SCALE × floor` (currently `0.2×` the full-batch discovery floor) rather than the full floor directly — real short-seed vocabulary essentially never clears the full-batch threshold, so the unscaled floor made three-file batches fail to cluster in practice. Larger batches derive a conservative bounded threshold from the positive-similarity median minus its median absolute deviation. Clustering is **complete-linkage**: two records only join the same cluster group if every cross-pair between the two groups independently clears the threshold (lexical cosine, or the semantic rescue described above), not just one connecting path — this was changed from single-linkage/connected-components after real full-corpus testing (~760 files) showed single-linkage chaining unrelated files transitively into one dominant cluster per family. Evidence-free samples are excluded rather than being forced into filename-derived topics.

The optional local tagger sends one cluster at a time — family, bounded filenames, and humanized top extracted terms (collocations and object labels rendered as plain words/phrases, not raw `bi:`/`obj:` tokens) — to Gemma 3 1B, one HTTP request per cluster against the same running local server. Each request is constrained by a real `json_schema` `response_format` (`{"topic": string, "tags": string[3..8]}`), which the local llama.cpp server enforces at generation time. A cluster's suggestion is used only if that cluster's own request parses and validates; other clusters in the same batch are unaffected by one failure. The model and pinned llama.cpp CPU runtime are downloaded only after Gemma-terms consent, verified by size and SHA-256, run on a temporary `127.0.0.1` port, and terminated after the batch. Invalid output, timeout, refusal, or installation failure for a given cluster falls back to the deterministic `fallback_topic()` name for that cluster only.

The calibration board has separate immutable-family tabs. Users can drag sample files between cards, create or rename topics, edit tags, split selected files, merge checked topics, or explicitly exclude samples. Confirmation is step one: the app builds each profile, creates `<유형>/<주제>` under the seed's current source root, and transactionally moves the seed files there. If any seed move fails, all seed moves roll back; if profile persistence fails, the completed seed batch is undone. Rerunning calibration retains existing profiles and offers them as destination cards.

Each seed contributes up to 40 weighted base words (including PMI-qualified collocation phrases, prefixed `bi:`/`tri:`) and 120 strongest canonical unordered word pairs. A pair is always stored with a stable lexical identity such as `co:orbit|quantum`, regardless of which word is more frequent, and receives `PAIR_WEIGHT_SCALE × sqrt(weight(A) × weight(B))` (currently `0.1×`). Cluster evidence averages these vectors. The editable visible tag list includes up to 60 high-weight base words, while the persisted centroid retains the co-occurrence pairs used for contextual matching. When no proposal or model suggestion supplies a name, `fallback_topic()` (`calibration.py`) prefers a collocation phrase over loosely joining two unrelated top terms, and `humanize_term()` (`classifier_engine/topics.py`) strips/renders raw feature-token prefixes (`obj:`, `bi:`, `tri:`) so folder names never leak internal syntax like `obj_person`.

After the seed files have moved, the app rescans the original top-level source. Because seeds are now nested, only remaining files enter step two. The preview topic selector permits confirmation, correction, or creation of a user topic. Learning occurs only after a successful approved move: confirmation adds positive evidence, while changing A to B adds positive evidence to B and negative evidence to A. Canceled, unchecked, failed, and `미분류` rows do not learn.

## Existing-folder migration

`기존 폴더 계층화` is a separate manual action. It recursively examines safe files below Desktop and Downloads top-level folders but never moves anything before preview approval.

- `직접선택/1차/과제.pdf` becomes `문서/직접선택/1차/과제.pdf` after approval.
- A direct file under an existing fixed root becomes `<유형>/미분류/<파일>`.
- Files already below `<유형>/<주제>` are skipped.
- Successfully approved migration groups update independent family/topic profiles from their extracted features.
- Existing collision handling, atomic move history, rollback, and Undo remain authoritative.

Renaming or deleting a topic profile never renames or deletes an existing physical folder.
