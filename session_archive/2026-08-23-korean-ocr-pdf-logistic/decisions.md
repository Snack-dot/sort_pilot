# Decisions

## OCR assets and offline execution

- Pin RapidOCR `3.5.0` and the official RapidAI `korean_PP-OCRv5_rec_mobile_infer.onnx` artifact.
- Verify the recognizer against SHA-256 `cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b`.
- Extract the recognizer's embedded character list to an explicit local dictionary and verify it matches the model on load.
- Copy the packaged detector and orientation classifier into the sandbox model directory and pass all detector/classifier/recognizer/dictionary paths explicitly to RapidOCR.
- Keep downloading in the explicit installer only. Runtime loading fails closed when assets are absent or invalid.
- Reuse one image OCR engine per worker thread. PDF OCR uses a reusable child worker owned by that thread so a timed-out ONNX inference can be terminated safely.

## PDF performance contract

- Use `document.page_count` and `document.load_page(index)` only.
- Select no more than indices `0`, `1`, `2`, `page_count // 2`, and `page_count - 1`, removing duplicates while preserving order.
- Extract native text and image ratio only for selected pages.
- OCR no more than the first selected scan-like page, at 150 DPI.
- End page OCR after three seconds by terminating the dedicated child worker; do not retry another page.
- Cache only in process memory, with `(resolved path, size, mtime_ns)` as the key. Never read a source file body to compute a cache hash.

## Classification and privacy

- Keep PDF title, author, and keyword tokens as weak `pdf_meta` evidence.
- Keep page count, sampled-page count, scan ratio, image ratio, and text characters per page as numeric columns; never turn them into pseudo-sentences.
- Use separate hashed word and character TF-IDF channels. Persist only IDF arrays and bin schema, not a raw vocabulary.
- Force new files with `failed` or `low_confidence` extraction to Needs Review on both axes.
- Human-approved training labels remain eligible even when OCR times out; their remaining filename/native-text evidence is still usable.
- Keep natural text, template-order OCR text, and layout evidence transient and omit them from JSON/SQLite serialization.

## Training status

- The completed local v1 model remains intact.
- The v2 run reached extraction completion but was stopped during repeated cross-validation because the session was ending.
- Resume v2 from the start in the morning with the committed PowerShell helper.
