from __future__ import annotations

from sort_pilot.classifier_engine.ocr import install_korean_ocr_assets


def main() -> int:
    assets = install_korean_ocr_assets()
    print(f"KOREAN_OCR_MODEL={assets.recognizer}")
    print(f"KOREAN_OCR_DICTIONARY={assets.dictionary}")
    print("KOREAN_OCR_INSTALL=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
