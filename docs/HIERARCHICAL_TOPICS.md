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

Resolution is intentionally simple: a matching `user`, `discovered`, or `migration` profile wins; otherwise the topic is `미분류`. Topic scoring excludes extension and generic media metadata, then applies existing extraction-source weights.

For each family batch:

1. Weighted TF is `log(1 + weight)`.
2. Smoothed IDF is `log((1 + N) / (1 + df)) + 1`.
3. Sparse vectors are L2-normalized.
4. Profile/example cosine similarity is compared to `0.25` for documents, `0.20` for images, and `0.30` for other families.
5. Explicit normalized user tags are five-times-weighted pseudo-document terms.
6. Final score is `max(0, positive cosine - 0.65 × negative cosine)`, so a correction can overcome an overly broad tag without deleting it.

Single-file/public JSON analysis runs and persists the real engine decision, then checks only saved user-owned profiles. With an empty profile store it returns `<유형>/미분류`. It never creates a discovered TF-IDF profile or moves a file.

### Sample calibration and adaptive discovery

When no profiles exist, organization is paused for calibration. The sampler reads only safe top-level Desktop/Downloads files, chooses at most 3 per family, round-robins source/extension buckets, and prefers fingerprints not used by an earlier calibration. A family with only one or two files is still calibrated. Fingerprints are hashes of resolved path metadata; readable paths are not stored. Samples are analyzed by the existing two-worker queue and never moved.

For every family, pairwise cosine values derive a bounded threshold from their median and median absolute deviation. Stable centroid grouping and refinement then choose the number of clusters automatically; an evidence-free sample stays separate rather than being forced into a generic topic.

The optional local tagger sends only family, bounded filenames, and top extracted terms to Gemma 3 1B. It returns strict JSON containing `cluster_id`, `topic`, and `tags`. The model and pinned llama.cpp CPU runtime are downloaded only after Gemma-terms consent, verified by size and SHA-256, run on a temporary `127.0.0.1` port, and terminated after one request. Invalid output, timeout, refusal, or installation failure falls back to deterministic top-term names.

The calibration board has separate immutable-family tabs. Users can drag sample files between cards, create or rename topics, edit tags, split selected files, merge checked topics, or explicitly exclude samples. No profile is written until the final confirmation. Rerunning calibration retains existing profiles and offers them as destination cards.

After calibration, the app analyzes the requested full batch. The preview topic selector permits confirmation, correction, or creation of a user topic. Learning occurs only after a successful approved move: confirmation adds positive evidence, while changing A to B adds positive evidence to B and negative evidence to A. Canceled, unchecked, failed, and `미분류` rows do not learn.

## Existing-folder migration

`기존 폴더 계층화` is a separate manual action. It recursively examines safe files below Desktop and Downloads top-level folders but never moves anything before preview approval.

- `직접선택/1차/과제.pdf` becomes `문서/직접선택/1차/과제.pdf` after approval.
- A direct file under an existing fixed root becomes `<유형>/미분류/<파일>`.
- Files already below `<유형>/<주제>` are skipped.
- Successfully approved migration groups update independent family/topic profiles from their extracted features.
- Existing collision handling, atomic move history, rollback, and Undo remain authoritative.

Renaming or deleting a topic profile never renames or deletes an existing physical folder.
