# Repository and Runtime Evidence

## Git state at archival time

```text
branch: architecture-srs-implementation
HEAD: f91b43b Move local assets out of repository root
upstream: origin/architecture-srs-implementation
modified: sort_pilot/classifier.py
origin: https://github.com/Snack-dot/sort_pilot.git
```

Known current-branch history:

```text
f91b43b Move local assets out of repository root
937cbab Align architecture branch with main layout
5718b27 Add architecture-driven local classifier
1899611 ai, ui 임의로 함
```

The interrupted fetch did not establish a local `refs/remotes/origin/app` reference.

## App-branch evidence

Separate local checkout:

```text
path: C:\Users\nobody haha\Downloads\sort_pilot-app
branch: app
commit: 8b51ce1 실시간 다운로드 감지에서 수동 정리로 변경
tracking: origin/app
working tree: clean
```

GitHub read-only lookup on 2026-08-13 reported:

```text
refs/heads/app: 42f92c1db9a3a55c09b2d5fc3a83608cf950355c
```

The commit after `8b51ce1` was:

```text
42f92c1 정리 위치 선택 기능 구현
```

It added current-location display and Desktop/Downloads destination-root selection to the preview workflow.

## OCR diagnosis evidence

- Downloads root contained 627 top-level files.
- 88 were images; 68 were PNG files.
- `sort_pilot/tidy/extract.py` instantiated `RapidOCR()` inside `_ocr()` for each qualifying image.
- PNG images were routed as screenshots and therefore sent through OCR.
- Logged initialization intervals of roughly 3–5 seconds matched per-image engine construction and analysis.
- Two Sort Pilot-related Python processes were found and terminated during diagnosis.

## Current classifier change

The uncommitted change adds:

```python
LocalPipelineAnalyzer.analyze_json(file_path)
LocalPipelineAnalyzer.analyze_many_json(file_paths)
```

The methods return Python dictionaries using `filepath` and `folder`; multiple results are wrapped by `results`. A focused validation and the three `tests.test_core` tests passed when this change was introduced.

## Source integrity statement

This evidence was assembled from Git commands, repository files, the separate app checkout, a read-only GitHub ref/API query, process inspection, and the visible conversation. No inaccessible or hidden cache contents are represented as evidence.
