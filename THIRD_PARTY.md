# Third-party software

| Dependency | Version | License | Purpose |
| --- | --- | --- | --- |
| PyQt6 | 6.7.1 | GPL-3.0/commercial | Desktop tray and dialogs |
| kiwipiepy | 0.23.2 | LGPL-3.0 | Korean morphology |
| PyMuPDF | 1.28.0 | AGPL-3.0/commercial | PDF text and rendering |
| python-docx | 1.2.0 | MIT | DOCX text extraction |
| python-pptx | 1.0.2 | MIT | PPTX text extraction |
| openpyxl | 3.1.5 | MIT | XLSX representative-cell extraction |
| Pillow | 12.1.0 | HPND | Image metadata and routing |
| ONNX Runtime | 1.27.0 | MIT | CPU inference runtime |
| RapidOCR | 3.5.0 | Apache-2.0 | Local OCR pipeline |
| stop-words | 2025.11.4 | BSD-3-Clause | Verified multilingual stopword lists for content tokenization |
| pytest | 9.1.1 | MIT | Development tests |
| Ultralytics | 8.4.56 | AGPL-3.0 | Development-only YOLO export |
| ONNX | 1.22.0 | Apache-2.0 | Development-only ONNX export support |

## Model artifacts

| Artifact | Official source | SHA-256 | Committed? |
| --- | --- | --- | --- |
| `data/models/yolov8n.pt` | Ultralytics assets v8.4.0 | `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` | No (dev-only export input) |
| `data/models/yolov8n.onnx` | Locally exported at 640 px, opset 17 | `9A7B7B813051D0C529B41E229FF1FF799EC93286618AC51533EF15DA3E51B2E5` | **Yes** (~13MB, under GitHub's 100MB limit) |
| `gemma-3-1b-it-Q4_K_M.gguf` | `ggml-org/gemma-3-1b-it-GGUF` (Google Gemma terms) | `8CCC5CD1F1B3602548715AE25A66ED73FD5DC68A210412EEA643EB20EB75A135` | Downloaded after consent (not committed) |
| `llama-b10405-bin-win-cpu-x64.zip` | `ggml-org/llama.cpp` release `b10405` (MIT) | `31F3BCC3F7645715B3ED8E845AB338D94659AA0E512B2211B8D94B9C8EB24758` | Downloaded at setup (not committed) |

ONNX export is not bit-reproducible across toolchains, so `yolov8n.onnx`'s hash reflects this repository's own committed bytes, not a value anyone re-exporting the checkpoint should expect to match — `yolov8n.pt`'s hash is what verifies you have the authentic upstream weights.

The first-use model dialog links the current Gemma Terms and records consent for the exact model before downloading. `LocalModelInstaller` verifies the pinned size and SHA-256 values above before making either artifact available to inference.
