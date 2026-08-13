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

The move preview renders the detected type as a read-only column. Users may edit the topic or preserved subpath, but approved output always reconstructs the destination beneath the fixed type root.

## Topic profiles

Profiles live in `%APPDATA%\tidy\topic_profiles.json` using an atomic version-1 JSON document. Each profile contains:

- stable ID, fixed family, and validated single-folder name;
- normalized tags;
- averaged example term weights and example count;
- origin (`user`, `discovered`, or `migration`);
- enabled state and timestamps.

Example paths and raw file contents are never stored. A fresh profile document is empty: there are no built-in topics or semantic seed lexicon. Version-1 `builtin` entries are removed automatically when the profile document is loaded. Every remaining profile was created by the user, named during an approved TF-IDF proposal, or learned from an approved migration group.

The `폴더/태그 관리` tray action lets the user create, rename, enable/disable, or delete profiles. Dragged/selected examples are extracted through the same two-worker queue and update only a profile of the selected family; they are never moved. Physical folders are created only by a later approved move.

## Matching and TF-IDF

Every file first runs the complete `Pipeline.safe_classify()` path. This evaluates Tier-1 evidence rules, extracts local filename/body/OCR/object/pair features, scores the learned Naive Bayes model, persists the decision, and returns its decision ID. The category/action/margin are retained for diagnostics and future feedback, but are never copied into a destination topic. Default coursework and purchase patterns add evidence marks rather than terminal categories.

Resolution is intentionally simple: a matching `user`, `discovered`, or `migration` profile wins; otherwise the topic is `미분류`. Topic scoring excludes extension and generic media metadata, then applies existing extraction-source weights.

For each family batch:

1. Weighted TF is `log(1 + weight)`.
2. Smoothed IDF is `log((1 + N) / (1 + df)) + 1`.
3. Sparse vectors are L2-normalized.
4. Profile/example cosine similarity is compared to `0.25` for documents, `0.20` for images, and `0.30` for other families.
5. Explicit normalized user tags are five-times-weighted pseudo-document terms; a complete tag-token or filename-phrase match overrides the cosine threshold.

Single-file/public JSON analysis runs and persists the real engine decision, then checks only saved user-owned profiles. With an empty profile store it returns `<유형>/미분류`. It never creates a discovered TF-IDF profile or moves a file.

### Current-batch discovery

Only unmatched documents and images are clustered. Records are processed in stable resolved-path order using deterministic greedy centroid assignment followed by up to five refinement passes. Minimum cosine is `0.30` for documents and `0.22` for images.

A proposal requires at least five documents or ten images. The dialog shows the top eight centroid terms and five closest representative filenames. Approved proposals require a valid user-supplied name, are saved as independent family profiles, and apply immediately to the current batch. Rejected and undersized clusters remain `미분류`.

## Existing-folder migration

`기존 폴더 계층화` is a separate manual action. It recursively examines safe files below Desktop and Downloads top-level folders but never moves anything before preview approval.

- `직접선택/1차/과제.pdf` becomes `문서/직접선택/1차/과제.pdf` after approval.
- A direct file under an existing fixed root becomes `<유형>/미분류/<파일>`.
- Files already below `<유형>/<주제>` are skipped.
- Successfully approved migration groups update independent family/topic profiles from their extracted features.
- Existing collision handling, atomic move history, rollback, and Undo remain authoritative.

Renaming or deleting a topic profile never renames or deletes an existing physical folder.
