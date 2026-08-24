# UI Simple Classifier Test Mode

Date: 2026-08-23
Active branch: `ui`

## Purpose

This session added a deliberately explicit, non-production classification path so the grouped preview can be tested without local E5/Gemma inference.

## Result

When `SORT_PILOT_SIMPLE_CLASSIFIER=1`, common document, image, and archive extensions receive deterministic catalog-bounded subject/template results, while unknown extensions remain Needs Review. The preview clearly labels the mode, and accepting the final confirmation performs no file move and stores no personal examples.

The production classifier remains unchanged and is used whenever the environment switch is absent.

For UI-only work, `ui_demo.py` is the preferred entry point. It constructs 28 fake path-only samples and opens the grouped preview without importing the app controller, scanning a folder, loading E5/Gemma, reading history, or executing moves.
