from __future__ import annotations

import json
import math
import mimetypes
import re
import sys
import threading
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from stop_words import get_stop_words

from .types import Feature, FeatureVector

IN_PROGRESS = {".crdownload", ".part", ".tmp", ".download"}
KO_PARTICLES = ("에서는", "으로", "에게", "에서", "부터", "까지", "처럼", "보다", "은", "는", "이", "가", "을", "를", "에", "의", "도", "와", "과")
STOP = frozenset(get_stop_words("en")) | frozenset(get_stop_words("ko")) | {"그리고", "합니다", "있는", "없는"}
MAX_BODY_TERMS = 160
MAX_COLLOCATIONS = 40
MIN_COLLOCATION_COUNT = 2
MIN_COLLOCATION_PMI = 2.0
COLLOCATION_PREFIXES = {2: "bi:", 3: "tri:"}
SEMANTIC_FEATURE_SOURCES = frozenset({"body", "ocr", "obj", "pair"})
CONTENT_ANALYSIS_SUFFIXES = frozenset({
    ".txt", ".md", ".csv", ".rtf", ".ipynb", ".pdf", ".docx", ".odt", ".pptx", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic",
})
_KIWI = None
_OCR_LOCAL = threading.local()


def supports_content_analysis(path: Path) -> bool:
    """Return whether the bundled extractors can derive semantic content evidence."""
    return path.suffix.casefold() in CONTENT_ANALYSIS_SUFFIXES


def tokenize(text: str) -> list[str]:
    """Tokenize Korean and Latin text using Kiwi with a regex fallback."""
    global _KIWI
    try:
        if _KIWI is None:
            from kiwipiepy import Kiwi
            _KIWI = Kiwi()
        result = []
        for token in _KIWI.tokenize(text):
            if token.tag.startswith(("NN", "VV", "VA")) or token.tag in {"SL"}:
                form = token.form.lower()
                if form not in STOP and (len(form) >= 2 or re.search(r"[가-힣]", form)):
                    result.append(form)
        return result
    except ImportError:
        pass
    raw = re.findall(r"[가-힣]+|[A-Za-z][A-Za-z0-9]*", text.lower())
    result = []
    for token in raw:
        if re.search(r"[가-힣]", token):
            for particle in KO_PARTICLES:
                if token.endswith(particle) and len(token) > len(particle) + 1:
                    token = token[:-len(particle)]; break
        if token not in STOP and (len(token) >= 2 or re.search(r"[가-힣]", token)):
            result.append(token)
    return result


def collocations(tokens: list[str], n: int) -> Counter[str]:
    """Extract adjacent n-grams whose joint frequency exceeds chance (pointwise mutual information)."""
    if len(tokens) < n:
        return Counter()
    unigram_counts = Counter(tokens)
    total = len(tokens)
    ngram_counts = Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    total_ngrams = sum(ngram_counts.values())
    kept: Counter[str] = Counter()
    for ngram, count in ngram_counts.items():
        if count < MIN_COLLOCATION_COUNT:
            continue
        joint = count / total_ngrams
        independent = 1.0
        for word in ngram:
            independent *= unigram_counts[word] / total
        pmi = math.log(joint / independent) if independent > 0 else 0.0
        if pmi >= MIN_COLLOCATION_PMI:
            kept[COLLOCATION_PREFIXES[n] + " ".join(ngram)] = count
    return kept


def _read_text(path: Path, limit: int) -> str:
    """Read bounded plain text using common Korean and Unicode encodings."""
    for encoding in ("utf-8-sig", "cp949", "utf-16"):
        try: return path.read_text(encoding=encoding)[:limit]
        except (UnicodeError, OSError): continue
    return ""


def _ipynb(path: Path, limit: int) -> str:
    """Extract bounded Markdown and code cell sources without reading notebook outputs."""
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    chunks: list[str] = []
    length = 0
    for cell in document.get("cells", [])[:200]:
        if not isinstance(cell, dict) or cell.get("cell_type") not in {"markdown", "code"}:
            continue
        source = cell.get("source", "")
        text = "".join(str(part) for part in source) if isinstance(source, list) else str(source)
        if not text:
            continue
        remaining = limit - length
        if remaining <= 0:
            break
        bounded = text[:remaining]
        chunks.append(bounded)
        length += len(bounded)
    return "\n".join(chunks)


def _docx(path: Path, limit: int) -> str:
    """Extract bounded text directly from a DOCX document XML payload."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return " ".join(node.text or "" for node in root.iter())[:limit]


def _odt(path: Path, limit: int) -> str:
    """Extract bounded paragraph and table text from an ODT content payload."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("content.xml"))
    return " ".join(node.text or "" for node in root.iter())[:limit]


def _pdf(path: Path, max_chars: int, max_pages: int = 5) -> str:
    """Extract bounded text from the first pages of a PDF."""
    import pymupdf
    with pymupdf.open(path) as document:
        return " ".join(page.get_text() for page in list(document)[:max_pages])[:max_chars]


def _pptx(path: Path, limit: int) -> str:
    """Extract bounded text from PowerPoint slide text frames."""
    from pptx import Presentation
    deck = Presentation(path)
    return " ".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text_frame"))[:limit]


def _xlsx(path: Path, limit: int) -> str:
    """Extract bounded sheet names and cell values from a workbook."""
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=True)
    values = []
    try:
        for sheet in book.worksheets:
            values.append(sheet.title)
            for row in sheet.iter_rows(max_row=50, max_col=20, values_only=True):
                values.extend(str(value) for value in row if value is not None)
                if sum(map(len, values)) >= limit: break
    finally: book.close()
    return " ".join(values)[:limit]


def _image_route(path: Path) -> str:
    """Determine whether an image is a photo, screenshot, or ambiguous."""
    from PIL import Image
    with Image.open(path) as image:
        exif = image.getexif()
        has_camera = bool(exif.get(271) or exif.get(272))
        known = {(1920, 1080), (2560, 1440), (1366, 768), (3840, 2160)}
        return "photo" if has_camera else "screenshot" if image.size in known or path.suffix.lower() == ".png" else "ambiguous"


def _ocr_engine():
    """Return one lazily initialized RapidOCR engine per worker thread."""
    from rapidocr import RapidOCR

    engine = getattr(_OCR_LOCAL, "engine", None)
    if engine is None:
        engine = RapidOCR()
        _OCR_LOCAL.engine = engine
    return engine


def _ocr(path: Path) -> list[Feature]:
    """Extract at most forty OCR tokens while reusing the thread's engine."""
    result = _ocr_engine()(str(path))
    texts = getattr(result, "txts", None) or []
    return [Feature(token, "ocr") for token in tokenize(" ".join(texts))[:40]]


def extract(path: Path, max_content_mb=200, max_chars=20_000) -> FeatureVector:
    """Build a bounded local feature vector from filename, content, and media."""
    stat = path.stat(); features = []
    partial = stat.st_size > max_content_mb * 1024 * 1024
    text = ""; suffix = path.suffix.lower()
    if not partial:
        try:
            if suffix in {".txt", ".md", ".csv", ".rtf"}: text = _read_text(path, max_chars)
            elif suffix == ".ipynb": text = _ipynb(path, max_chars)
            elif suffix == ".pdf": text = _pdf(path, max_chars)
            elif suffix == ".docx": text = _docx(path, max_chars)
            elif suffix == ".odt": text = _odt(path, max_chars)
            elif suffix == ".pptx": text = _pptx(path, max_chars)
            elif suffix == ".xlsx": text = _xlsx(path, max_chars)
        except Exception:
            partial = True
    body_tokens = tokenize(text) if text else []
    for token, count in Counter(body_tokens).most_common(MAX_BODY_TERMS):
        features.append(Feature(token, "body", float(count)))
    for n in (2, 3):
        for ngram, count in collocations(body_tokens, n).most_common(MAX_COLLOCATIONS):
            features.append(Feature(ngram, "body", float(count)))
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if mime.startswith("image/"):
        try:
            route = _image_route(path)
            if route in {"screenshot", "ambiguous"}: features.extend(_ocr(path))
            model_path = Path(__file__).parents[2] / "data" / "models" / "yolov8n.onnx"
            # onnxruntime 1.27 can terminate CPython 3.14 on Windows while creating
            # this optional YOLO session. Keep image metadata/OCR and skip only YOLO.
            if model_path.exists() and sys.version_info < (3, 14):
                from .vision import infer
                vision_features, _ = infer(path, model_path); features.extend(vision_features)
        except Exception:
            partial = True
    return FeatureVector(features=features, partial=partial)


def is_processable(path: Path, exclusions=()) -> bool:
    """Reject directories, partial downloads, office locks, and excluded paths."""
    import fnmatch
    return path.is_file() and path.suffix.lower() not in IN_PROGRESS and not path.name.startswith("~$") and not any(fnmatch.fnmatch(str(path), p) for p in exclusions)


__all__ = ["extract", "is_processable", "supports_content_analysis"]
