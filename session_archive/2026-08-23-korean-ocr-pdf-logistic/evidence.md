# Evidence

## Automated tests

- OCR/PDF/TF-IDF/educational-service/HWP focused suite: 43 passed.
- 600-page synthetic PDF contract: exactly five `load_page` calls at indices `0`, `1`, `2`, `300`, and `599`.
- Follow-up PDF and academic-contract subset: 17 passed.
- Python compile check completed successfully.
- `git diff --check` reported no whitespace errors; only the repository's existing Windows LF/CRLF warnings were shown.

## Real sandbox audit (aggregate only)

- 35 images were available: 23 JPG, 3 JPEG, and 9 PNG.
- Nine real images were tested; all nine produced Korean text and all nine had `ok` quality.
- Mean recognition confidence across those samples was approximately 0.8504.
- One real camera-EXIF photo was routed as `photo`, produced Korean text, and scored approximately 0.7020.
- 200 PDFs were inspected using selected pages only: 904 selected pages total, not all document pages.
- 214 selected pages met the scan-like routing condition across 83 PDFs.
- Under the final three-second policy, the tested real scan candidate timed out, its worker was terminated, and it correctly returned `failed` for Needs Review.
- After the audit, no OCR, audit, or training child process remained.

## Asset verification

- Korean recognizer, local dictionary, detector, classifier, and manifest are installed below `~/Downloads/sandbox/.sort_pilot_state/models/rapidocr`.
- Repeated runtime engine creation used explicit local paths and reported `LangRec.KOREAN` plus `OCRVersion.PPOCRV5`.
- One-thread engine identity check confirmed reuse.

## Incomplete evidence

- The new v2 model metrics are not available because the final training run was stopped during cross-validation before any v2 artifact was saved.
- The last complete report is still v1 with 319 labels. Morning resumption must produce and validate `academic-logistic-training-v2` before claiming new model performance.
