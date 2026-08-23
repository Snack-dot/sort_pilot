from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pymupdf
from PIL import Image

from sort_pilot.classifier_engine.extract import (
    IMAGE_OCR_SUFFIXES,
    _pdf_image_ratio,
    _pdf_page_indices,
    extract,
)
from sort_pilot.sandbox import default_sandbox_root, require_sandbox_file


def _has_korean(value: str) -> bool:
    return any("가" <= character <= "힣" for character in value)


def _pdf_candidates(paths: list[Path]) -> tuple[list[tuple[int, Path]], int, int]:
    candidates: list[tuple[int, Path]] = []
    sampled_pages = 0
    routed_pages = 0
    for path in paths:
        source = require_sandbox_file(path, default_sandbox_root())
        with pymupdf.open(source) as document:
            needs_ocr = False
            for index in _pdf_page_indices(document.page_count):
                page = document.load_page(index)
                sampled_pages += 1
                text = (page.get_text("text") or "").strip()
                route = len(text) < 40 or _pdf_image_ratio(page) >= 0.70
                routed_pages += int(route)
                needs_ocr = needs_ocr or route
            if needs_ocr:
                candidates.append((document.page_count, source))
    return sorted(candidates, key=lambda value: value[0]), sampled_pages, routed_pages


def audit() -> dict:
    """Read sandbox samples and return aggregate-only OCR evidence without raw text or names."""
    root = default_sandbox_root().resolve()
    images = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.casefold() in IMAGE_OCR_SUFFIXES
    )
    pdfs = sorted(path for path in root.iterdir() if path.is_file() and path.suffix.casefold() == ".pdf")
    camera_paths: list[Path] = []
    for path in images:
        with Image.open(path) as image:
            exif = image.getexif()
            if exif.get(271) or exif.get(272):
                camera_paths.append(path)

    selected_images: list[Path] = []
    for suffix in sorted({path.suffix.casefold() for path in images}):
        selected_images.extend(
            [path for path in images if path.suffix.casefold() == suffix][:3]
        )
    selected_images.extend(camera_paths)
    selected_images = list(dict.fromkeys(selected_images))
    image_quality = Counter()
    image_routes = Counter()
    korean_results = 0
    confidence_values: list[float] = []
    camera_results = []
    for path in selected_images:
        vector = extract(require_sandbox_file(path, root))
        image_quality[vector.extraction_quality] += 1
        image_routes[vector.route] += 1
        korean_results += int(_has_korean(vector.natural_text))
        if vector.ocr_confidence is not None:
            confidence_values.append(vector.ocr_confidence)
        if path in camera_paths:
            camera_results.append(
                {
                    "quality": vector.extraction_quality,
                    "route": vector.route,
                    "has_korean": _has_korean(vector.natural_text),
                    "confidence": vector.ocr_confidence,
                }
            )

    candidates, sampled_pages, routed_pages = _pdf_candidates(pdfs)
    tested_pdfs = []
    if candidates:
        vector = extract(candidates[0][1])
        tested_pdfs.append(
            {
                "page_count": vector.numeric_features.get("pdf_page_count"),
                "sampled_page_count": vector.numeric_features.get("pdf_sampled_page_count"),
                "scan_ratio": vector.numeric_features.get("pdf_scan_ratio"),
                "image_ratio": vector.numeric_features.get("pdf_image_ratio"),
                "text_characters_per_page": vector.numeric_features.get(
                    "pdf_text_characters_per_page"
                ),
                "quality": vector.extraction_quality,
                "confidence": vector.ocr_confidence,
                "has_korean": _has_korean(vector.natural_text),
            }
        )
    return {
        "privacy": {
            "raw_ocr_printed": False,
            "raw_ocr_persisted": False,
            "filenames_printed": False,
        },
        "images": {
            "available": len(images),
            "formats": dict(Counter(path.suffix.casefold() for path in images)),
            "camera_exif_available": len(camera_paths),
            "tested": len(selected_images),
            "quality": dict(image_quality),
            "routes": dict(image_routes),
            "korean_results": korean_results,
            "mean_confidence": (
                None
                if not confidence_values
                else sum(confidence_values) / len(confidence_values)
            ),
            "camera_results": camera_results,
        },
        "pdf": {
            "available": len(pdfs),
            "sampled_pages_inspected": sampled_pages,
            "ocr_route_pages": routed_pages,
            "scan_candidates": len(candidates),
            "tested": tested_pdfs,
        },
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
