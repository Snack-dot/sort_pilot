# Repository and Runtime Evidence

## Git state at archival time

```text
branch: architecture-srs-implementation
HEAD: 5c8c5e8 Document real-world validation run and its reversal
upstream: origin/architecture-srs-implementation (ahead 1, unpushed)
origin: https://github.com/Snack-dot/sort_pilot.git
```

Commits from this session, oldest to newest, all pushed to `origin` except the last (`5c8c5e8`, this archive's companion CHANGELOG entry):

```text
ddfe04c Add verified multilingual stopword library
6392ee3 Fix YOLO detection unreachable for screenshot-routed images
fe0365c Widen calibration sampling pool and surface only connected clusters
c4cde65 Fix near-zero real-world topic coverage: rebalance pair weight and small-batch threshold
bd9efbe Add pretrained-embedding semantic rescue and PMI collocation extraction
7093e3d Fix clustering chaining defect: switch to complete-linkage
0c48876 Fix topic naming leaking raw feature-token syntax; fix and verify AI naming
8d25688 Document this session's recall/precision investigation and fixes
92634c1 Commit yolov8n.onnx directly
6bc5466 Build consent-gated download step for word_vectors.npz
5c8c5e8 Document real-world validation run and its reversal
```

## Clustering defect evidence (single-linkage vs. complete-linkage)

Read-only dry-run against the real `~/Downloads` folder (760 files), run twice independently, reproduced identically both times:

- Single-linkage (before fix): two mega-clusters of 412 and 89 files, 11 clusters total.
- Complete-linkage (after fix): maximum cluster size 31/24 files, 112 clusters total, 102 topic profiles created.

## AI naming verification evidence

- Before fix (batched, loosely-hinted multi-cluster request): 0/11 valid names against real cluster data.
- After fix (one `json_schema`-constrained request per cluster): 11/11 valid names against the same real cluster data.

## Model artifact evidence

```text
data/models/yolov8n.onnx        ~13 MB   committed directly, SHA-256 9A7B7B813051D0C529B41E229FF1FF799EC93286618AC51533EF15DA3E51B2E5
data/models/word_vectors.npz    ~112 MB  exceeds GitHub's 100 MB hard limit; not committed
```

`EmbeddingsInstaller` reference structural check:

```text
REFERENCE_SHA256 = "aee86795e9892825da0a7d02c67d5ac7f66c4ea16360d642c9ddf1f58828b972"
```

(Documented as structural/provenance verification, not a byte-identical hash gate, since the installer's own output is environment-dependent — top-100k-words-per-language streamed from the official `cc.ko.300.vec.gz`/`cc.en.300.vec.gz` fastText vectors.)

## Real-world validation run evidence (2026-08-14/16, `~/Downloads`, 760 files)

Three attempts were aborted by the pre-move safety check before any real file was touched, each with a distinct, verified root cause:

```text
Attempt 1: RuntimeError: expected to exclude exactly 26 files (confirmed with user),
           but reproduced clustering excludes 2.
           Root cause: assistant's own diagnostic counter used plain assignment
           instead of accumulation across 5 independently-matching clusters.

Attempt 2: RuntimeError: excluded-file set doesn't match what was confirmed with the user.
           missing: {'김승진CLAUDE.pdf', '온라인_해커스 토익 1000제3_리딩_해설집(통합).pdf',
                     '컴퓨터학개론 - 발표 4조 (2) (1).pptx'}
           extra:   {'컴퓨터학개론 - 발표 4조 (2) (1).pptx', '김승진CLAUDE.pdf'}
           Root cause: macOS NFD (decomposed) filenames on disk vs. NFC (composed)
           filenames in the confirmed-name literal; same two names appeared as both
           "missing" and "extra" because they were byte-different but visually identical.

Attempt 3: RuntimeError: 1 file(s) confirmed with the user as excluded are NOT excluded
           this run: {'온라인_해커스 토익 1000제3_리딩_해설집(통합).pdf'}
           Root cause: this file's cluster assignment was not stable run-to-run
           (borderline similarity score); resolved by matching confirmed filenames
           directly rather than depending on cluster membership.

Attempt 4 (final): completed cleanly.
```

Final successful run output:

```text
analyzing 760 files...
extraction done in 124s
force-excluding 26 files by confirmed name match

734 files to move, 26 excluded (staying in place)
MOVED 734/734 files
saved 101 topic profiles to /Users/seungjinkim/.local/share/tidy/topic_profiles.json

final folder breakdown (107 folders):
  문서/미분류: 70
  기타/미분류: 55
  문서/회귀 분석: 50
  압축파일/미분류: 37
  문서/경북대학교 국어: 33
  이미지/person book: 27
  이미지/미분류: 27
  오디오/미분류: 23
  ... (99 more folders)
```

## Reversal evidence

```text
restored 734 files
```

All 734 restored paths matched the originals recorded in the run's own `HistoryStore` batch (at `~/Library/Application Support/execute_real_organize.py/history.json`, since the validation script constructed `QApplication` without `setApplicationName("Sort Pilot")`). Post-reversal, `~/Downloads` top-level listing was diffed against a pre-run listing and matched, files-only. Three top-level folders the run had created (`문서`, `동영상`, `이미지`) were empty except for a macOS `.DS_Store` Finder artifact each; these were removed after confirming no other content remained.

## Source integrity statement

This evidence was assembled from Git commands, repository files, background-task log output captured during the actual run and undo, and the visible conversation. No file contents from the personal Downloads folder are represented here — only aggregate counts, folder-name statistics, and the specific filenames that were part of the explicitly reviewed and confirmed exclusion list.
