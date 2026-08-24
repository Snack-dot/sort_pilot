# Verification Evidence

- `.venv\\Scripts\\python.exe -m pytest tests/test_ui_demo.py tests/test_simple_classifier.py tests/test_educational_preview.py tests/test_documentation.py -q` → 18 passed.
- A five-second process smoke test with `SORT_PILOT_SIMPLE_CLASSIFIER=1` reported `SIMPLE_MODE_STARTED_OK`; the test process was then stopped.
- A separate five-second `ui_demo.py` smoke test with the classifier environment switch removed reported `UI_DEMO_STARTED_OK`.
- The isolated demo test verifies that importing and generating its 28 sample results does not import `onnxruntime` or `fastembed`.
- The Python 3.11 environment imports `onnxruntime 1.27.0`, `fastembed 0.8.0`, and `sort_pilot.app` successfully, although the simple classifier does not invoke E5 or Gemma.
- No private filenames or file contents are included in this archive.
