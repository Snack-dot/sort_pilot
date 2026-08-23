# Conversation summary

The user requested:

- all user-file operations remain limited to `~/Downloads/sandbox`;
- HWP/HWPX support and removal of one valueless empty HWP plus its approved label rows;
- logistic-regression training from 300+ human-approved labels on independent subject and academic-document-type axes;
- RapidOCR retention with `korean_PP-OCRv5_mobile_rec`, an explicit local Korean dictionary, one-time checksum-verified installation, and no runtime network fallback;
- OCR for JPG/JPEG, PNG, BMP, WEBP, TIFF, and EXIF-oriented camera photos;
- selective PDF native-text extraction, scan-page OCR, transient OCR text, separate PDF numeric features, word and character TF-IDF, and Needs Review for failed/weak extraction;
- a later performance correction: never iterate a whole long PDF, load at most pages 1, 2, 3, middle, and last; OCR at most one selected page at 150 DPI with a hard three-second limit; do not hash complete source files for cache identity;
- commit, push, archive the session, and provide a one-command morning restart.

No real file names, label rows, extracted text, or OCR text are included in this archive.
